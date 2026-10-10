"""True SAM2.1 Hiera-large construction, checkpoint loading, mask inference.

Runs without a Colab GPU using the same pinned upstream SAM2 source.
The previous CI only imported build_sam2 and missed required iopath imports.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import torch
from PIL import Image, ImageDraw

from tools.install_2d_workers import SAM2_CONSTRUCTION_SMOKE
from vtuber_pipeline.common.model_assets import resolve_snapshot


def run():
    # Instantiate the *actual* Hydra model graph, not just import its names.
    exec(compile(SAM2_CONSTRUCTION_SMOKE, "<sam2-construction>", "exec"))
    from sam2.sam2_image_predictor import SAM2ImagePredictor
    from sam2.build_sam import build_sam2

    checkpoint = Path(resolve_snapshot("sam2_1_hiera_large")) / "sam2.1_hiera_large.pt"
    assert checkpoint.is_file() and checkpoint.stat().st_size > 1024, checkpoint
    model = build_sam2("configs/sam2.1/sam2.1_hiera_l.yaml",
                       ckpt_path=str(checkpoint), device="cpu",
                       apply_postprocessing=False)
    predictor = SAM2ImagePredictor(model)
    img = Image.new("RGB", (256, 256), (250, 250, 250))
    draw = ImageDraw.Draw(img)
    draw.ellipse((40, 30, 215, 210), fill=(20, 60, 180))
    predictor.set_image(np.asarray(img))
    with torch.inference_mode():
        masks, scores, _ = predictor.predict(
            box=np.array([35, 25, 220, 215], dtype=np.float32),
            multimask_output=False,
        )
    assert masks.shape == (1, 256, 256), masks.shape
    assert scores.shape == (1,), scores.shape
    assert np.isfinite(scores).all() and np.isfinite(masks).all()
    print(json.dumps({
        "SAM2_NATIVE_HIERA_LARGE_E2E": "PASS",
        "checkpoint_bytes": checkpoint.stat().st_size,
        "mask_shape": list(masks.shape),
        "scores": scores.tolist(),
    }, indent=2), flush=True)


if __name__ == "__main__":
    run()
