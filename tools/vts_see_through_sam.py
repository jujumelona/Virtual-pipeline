"""Official See-through SemanticSam 19-part body parsing.

This is an independent GPU worker. It loads the published model *once* and
writes masks, not synthetic RGB layers. Python process exits before the NF4
second-pass batch begins, so the two model families never share T4 VRAM.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

SAM_REPO = "24yearsold/l2d_sam_iter2"
SAM_FILE = "checkpoint-18000.pt"
SAM_PART_COUNT = 19


def find_checkpoint(manifest: Path) -> Path:
    data = json.loads(manifest.read_text(encoding="utf-8"))
    snapshots = [x for x in data.get("snapshots", []) if x.get("model") == SAM_REPO]
    if len(snapshots) != 1:
        raise RuntimeError("Official See-through SAM checkpoint not prepared: " + SAM_REPO)
    checkpoint = (Path(snapshots[0]["snapshot"]) / SAM_FILE).resolve()
    if not checkpoint.is_file() or checkpoint.stat().st_size < 1_000_000:
        raise RuntimeError("Official SAM checkpoint missing/corrupt: " + str(checkpoint))
    return checkpoint


def check_masks(masks, size: tuple[int, int]):
    import numpy as np
    result = np.asarray(masks)
    w, h = size
    if result.ndim != 3 or result.shape != (SAM_PART_COUNT, h, w):
        raise RuntimeError(f"Official SAM returned invalid mask tensor: {result.shape}")
    return result.astype(np.uint8, copy=False)


def run_worker(*, third_party: Path, manifest: Path, source: Path, output: Path):
    # Import exactly the official pinned See-through classes/initializer.
    # The SAM module lives in its common/ subdirectory, not inference/.
    checkpoint = find_checkpoint(manifest)
    sys.path.insert(0, str(third_party / "common"))
    import numpy as np
    import torch
    from PIL import Image
    from modules.semanticsam import SemanticSam
    from utils.torch_utils import init_model_from_pretrained
    from live2d.scrap_model import VALID_BODY_PARTS_V2

    if len(VALID_BODY_PARTS_V2) != SAM_PART_COUNT:
        raise RuntimeError("Pinned See-through SAM part-label contract changed")
    if not torch.cuda.is_available():
        raise RuntimeError("Official SemanticSam requires CUDA")
    model = init_model_from_pretrained(
        pretrained_model_name_or_path=str(checkpoint),
        module_cls=SemanticSam,
        download_from_hf=False,
        model_args=dict(class_num=SAM_PART_COUNT),
    ).to(device="cuda").eval()
    image = Image.open(source).convert("RGB")
    with torch.inference_mode():
        logits = model.inference(np.array(image))[0]
        masks = (logits > 0).to(device="cpu", dtype=torch.bool).numpy()
    result = check_masks(masks, image.size)
    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output, masks=result)
    output.with_suffix(".json").write_text(
        json.dumps({"source": source.name, "model": SAM_REPO,
                    "checkpoint": SAM_FILE, "class_count": SAM_PART_COUNT,
                    "labels": list(VALID_BODY_PARTS_V2),
                    "size": list(image.size)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[VTS SAM] PASS {SAM_PART_COUNT} masks {image.size}", flush=True)


def run_sam_from_package(layers: list[dict], canvas: tuple[int, int],
                         *, output: Path, third_party: Path):
    """Run the published 19-mask parser once on the composite source image."""
    import numpy as np
    from PIL import Image
    from tools.vts_subprocess import run_logged

    output.mkdir(parents=True, exist_ok=True)
    source = Image.new("RGBA", canvas, (0, 0, 0, 0))
    for layer in reversed(layers):
        source.alpha_composite(layer["image"].convert("RGBA"))
    src = output / "sam_source.png"
    source.save(src)
    model_root = third_party.parent
    manifest = model_root / "vts_setup_manifest.json"
    find_checkpoint(manifest)  # fail before starting expensive worker
    result = output / "sam19.npz"
    log = output / "sam19.log"
    import os
    import sys
    worker_python = os.environ.get("VTUBER_SEETHROUGH_PYTHON", sys.executable)
    command = [worker_python, "-u", str(Path(__file__).resolve()),
               "--third-party", str(third_party), "--manifest", str(manifest),
               "--source", str(src), "--output", str(result)]
    code = run_logged(command, cwd=third_party, log_path=log,
                      timeout_seconds=3600)
    if code or not result.is_file():
        raise RuntimeError(f"Official SAM body parsing failed exit={code}; log={log}")
    with np.load(result, allow_pickle=False) as data:
        masks = check_masks(data["masks"], canvas)
    # Every mask remains exactly the original image's full coordinate canvas.
    images = []
    for channel in masks:
        rgba = np.zeros((canvas[1], canvas[0], 4), dtype=np.uint8)
        rgba[..., 3] = channel * 255
        images.append(Image.fromarray(rgba, "RGBA"))
    return images, log


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--third-party", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run_worker(third_party=args.third_party, manifest=args.manifest,
               source=args.source, output=args.output)


if __name__ == "__main__":
    main()
