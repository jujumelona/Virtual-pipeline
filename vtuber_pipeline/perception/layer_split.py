"""Maintain original-canvas RGBA part pixels and explicitly label unknown occlusions."""
from pathlib import Path
from PIL import Image, ImageFilter
import json
import numpy as np
from vtuber_pipeline.common.schemas import PartsDocument, Part
from vtuber_pipeline.common.part_taxonomy import z_order

def split_semantic_layers(original_rgba: str, masks_json: str,
                          landmarks_json: str, output_dir: str) -> PartsDocument:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    base = Image.open(original_rgba).convert("RGBA")
    w, h = base.size
    masks = json.loads(Path(masks_json).read_text(encoding="utf-8"))
    if not masks.get("parts"):
        raise ValueError("SAM produced no semantic part masks")
    entries = sorted(masks["parts"], key=lambda d: z_order(d["semantic_id"]))
    parts = []
    for index, entry in enumerate(entries):
        identity = entry["semantic_id"]
        mask = Image.open(entry["mask_png"]).convert("L")
        if mask.size != (w, h):
            raise ValueError("mask not in original image coordinates: " + identity)
        mask_np = np.asarray(mask)
        if not np.any(mask_np):
            continue
        ys, xs = np.nonzero(mask_np > 0)
        px = np.asarray(base.copy())
        px[:, :, 3] = np.minimum(px[:, :, 3], mask_np)
        path = out / ("part_%03d.png" % index)
        Image.fromarray(px, "RGBA").save(path)
        # An edge-expansion band is a proposal for hidden artwork, not observed source.
        grown = mask.filter(ImageFilter.MaxFilter(15))
        hidden = np.maximum(0, np.asarray(grown, dtype=np.int16) - mask_np.astype(np.int16)).astype("uint8")
        hidden_path = out / ("hidden_%03d.png" % index)
        Image.fromarray(hidden, "L").save(hidden_path)
        parts.append(Part(identity, str(path), entry["mask_png"], str(hidden_path),
                          [int(xs.min()), int(ys.min()), int(xs.max()+1), int(ys.max()+1)],
                          z_order(identity), [], "sam2.1"))
    if not parts:
        raise ValueError("empty segmented character")
    doc = PartsDocument(w, h, parts, None, "")
    doc.write(str(out / "parts.json"))
    return doc
