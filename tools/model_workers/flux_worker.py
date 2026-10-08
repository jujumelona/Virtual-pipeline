"""FLUX.2 Klein localized occlusion restoration.

One checkpoint is loaded per worker. Each semantic hole is edited in a
bounded crop and copied only under its original explicit fill mask.
The pipeline intentionally does not invent unsupported mask_image kwargs.
"""
from pathlib import Path
import json
import math
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _entry import execute

PROMPT = (
    "Restore only the missing pixels of the specified original anime character "
    "layer. Preserve exact identity, outline, face details, costume colors "
    "and alignment. Extend occluded anatomy naturally. Do not change visible "
    "pixels. No text or background."
)


def prepare_masked_edit(original: Image.Image, mask: Image.Image, *,
                        margin: int = 96, max_size: int = 1024):
    """Return marked RGB crop, target rectangle and native crop pixel shape.

    The gray region is the ONLY unknown content; everything else remains
    source context and will be restored bit-for-bit during compositing.
    """
    if original.size != mask.size:
        raise ValueError("occlusion mask and original image dimensions differ")
    if max_size < 256 or max_size % 16:
        raise ValueError("max_size must be >=256 and divisible by 16")
    bounds = mask.getbbox()
    if bounds is None:
        raise ValueError("empty repair mask")
    left, top, right, bottom = bounds
    box = (max(0, left - margin), max(0, top - margin),
           min(original.width, right + margin),
           min(original.height, bottom + margin))
    cropped = np.asarray(original.convert("RGB").crop(box)).copy()
    cropped_mask = np.asarray(mask.convert("L").crop(box))
    cropped[cropped_mask > 0] = [128, 128, 128]
    patch = Image.fromarray(cropped, "RGB")
    width = min(max_size, max(256, math.ceil(patch.width / 16) * 16))
    height = min(max_size, max(256, math.ceil(patch.height / 16) * 16))
    if patch.size != (width, height):
        patch = patch.resize((width, height), Image.Resampling.LANCZOS)
    return patch, box


def infer(req):
    from vtuber_pipeline.common.model_assets import resolve_snapshot
    from vtuber_pipeline.common.schemas import PartsDocument
    from vtuber_pipeline.perception.compose import masked_repair

    doc = PartsDocument.read(req["parts_json"])
    original = Image.open(req["image_path"]).convert("RGB")
    out = Path(req["output_dir"])
    out.mkdir(parents=True, exist_ok=True)
    planned = []
    for part in doc.parts:
        if not part.hidden_fill_mask_png:
            continue
        mask = Image.open(part.hidden_fill_mask_png).convert("L")
        if mask.size != original.size:
            raise ValueError(f"{part.semantic_id}: hidden mask dimensions mismatch")
        if mask.getbbox():
            planned.append((part, mask))
    if not planned:
        saved = doc.write(str(out / "repaired_parts.json"))
        return {"parts_json": saved}

    import torch
    from diffusers import Flux2KleinPipeline
    snapshot = resolve_snapshot("flux2_klein_4b")
    dtype = torch.bfloat16 if torch.cuda.is_available() and torch.cuda.is_bf16_supported() else torch.float16
    pipe = Flux2KleinPipeline.from_pretrained(snapshot, torch_dtype=dtype)
    pipe.enable_model_cpu_offload()
    reports = []
    for index, (part, mask) in enumerate(planned):
        marked, box = prepare_masked_edit(original, mask)
        prompt = PROMPT + f" Target layer: {part.semantic_id}. Restore the gray missing region only."
        edited = pipe(
            image=marked, prompt=prompt, num_inference_steps=4,
            guidance_scale=1.0, width=marked.width, height=marked.height,
        ).images[0].convert("RGB")
        x0, y0, x1, y1 = box
        restored_patch = np.asarray(
            edited.resize((x1 - x0, y1 - y0), Image.Resampling.LANCZOS),
            dtype=np.uint8,
        )
        original_part = np.asarray(Image.open(part.rgba_png).convert("RGBA")).copy()
        if original_part.shape[:2] != (original.height, original.width):
            raise ValueError(f"{part.semantic_id}: part is not on the original canvas")
        region = original_part[y0:y1, x0:x1]
        mask_region = np.asarray(mask.crop(box), dtype=np.uint8)
        original_part[y0:y1, x0:x1] = masked_repair(
            region, restored_patch, mask_region,
        )
        dest = out / f"repaired_{index:03d}.png"
        Image.fromarray(original_part, "RGBA").save(dest)
        part.rgba_png = str(dest)
        part.source_stage = "sam2.1+flux2-klein-4b"
        reports.append({
            "part": part.semantic_id,
            "source_crop_xyxy": list(box),
            "model_input_wh": list(marked.size),
            "semantic_hole_pixels": int(np.count_nonzero(mask_region)),
            "reduced_input_resolution": (x1 - x0) > marked.width or (y1 - y0) > marked.height,
        })
    saved = doc.write(str(out / "repaired_parts.json"))
    stats = out / "occlusion_repair_report.json"
    stats.write_text(json.dumps({"repairs": reports, "model": "FLUX.2-klein-4B"},
                                indent=2), encoding="utf-8")
    return {"parts_json": saved, "repair_stats_json": str(stats)}


if __name__ == "__main__":
    execute(infer)
