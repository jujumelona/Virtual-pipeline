"""Reject SAM outputs that cannot represent a finite full-resolution mask."""
import json
import sys
from types import SimpleNamespace

import numpy as np
from PIL import Image
import pytest


@pytest.mark.parametrize("invalid", ["shape", "mask_nan", "score_nan"])
def test_sam_refuses_invalid_single_mask_predictions(monkeypatch, tmp_path, invalid):
    from tools.model_workers import sam_worker
    from vtuber_pipeline.common import model_assets
    source, alpha, boxes = [tmp_path / name for name in ("source.png", "alpha.png", "boxes.json")]
    Image.new("RGB", (8, 6)).save(source)
    Image.new("L", (8, 6), 255).save(alpha)
    boxes.write_text(json.dumps({"parts": [{"semantic_id": "head", "bbox_xyxy": [0, 0, 8, 6]}]}))
    masks = np.ones((1, 6, 8), dtype=float)
    scores = np.asarray([0.9])
    if invalid == "shape":
        masks = np.ones((1, 1, 8))  # previously broadcast to the entire image
    elif invalid == "mask_nan":
        masks[0, 2, 3] = np.nan
    else:
        scores[0] = np.nan  # previously serialized as nonstandard JSON NaN

    class Predictor:
        def __init__(self, model):
            pass
        def set_image(self, image):
            pass
        def predict(self, **kwargs):
            return masks, scores, None

    from contextlib import nullcontext
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(
        cuda=SimpleNamespace(is_available=lambda: False), inference_mode=nullcontext))
    monkeypatch.setitem(sys.modules, "sam2.sam2_image_predictor", SimpleNamespace(SAM2ImagePredictor=Predictor))
    monkeypatch.setitem(sys.modules, "sam2.build_sam", SimpleNamespace(build_sam2=lambda *args, **kwargs: None))
    monkeypatch.setattr(model_assets, "resolve_snapshot", lambda _: str(tmp_path))
    with pytest.raises(RuntimeError, match="SAM2.*prediction"):
        sam_worker.infer({"image_path": str(source), "person_alpha_png": str(alpha),
                          "boxes_json": str(boxes), "output_dir": str(tmp_path / "output")})
