"""Depth Anything worker must load the exact verified model revision."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PIL import Image
import pytest

from tools.model_workers import depth_worker
from vtuber_pipeline.common import model_assets


def test_real_depth_worker_contract_uses_local_pinned_snapshot(tmp_path, monkeypatch):
    source = tmp_path / "front.png"
    Image.new("RGB", (16, 18), (255, 120, 70)).save(source)
    checkpoint = tmp_path / "pinned-depth-snapshot"
    checkpoint.mkdir()
    observed = []

    def pipeline(*, task, model, device):
        observed.append((task, model, device))
        def infer(image):
            assert image.size == (16, 18)
            return {"predicted_depth": np.ones((18, 16), dtype=np.float32)}
        return infer

    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(
        cuda=SimpleNamespace(is_available=lambda: False)))
    monkeypatch.setitem(sys.modules, "transformers", SimpleNamespace(pipeline=pipeline))
    monkeypatch.setattr(model_assets, "resolve_snapshot", lambda key: (
        str(checkpoint) if key == "depth_anything_v2_small" else None))
    monkeypatch.setattr(model_assets, "model_pin", lambda key: {
        "model_id": "depth-anything/Depth-Anything-V2-Small-hf",
        "revision": "a" * 40,
    })
    output = depth_worker.infer({"output_dir": str(tmp_path / "depth"),
                                 "images": {"front": str(source)}})
    assert observed == [("depth-estimation", str(checkpoint), -1)]
    manifest = json.loads(Path(output["depth_manifest"]).read_text())
    assert manifest["model_revision"] == "a" * 40
    assert manifest["units"] == "relative/no-metric-scale"
    assert np.load(output["depth_front_npy"]).shape == (18, 16)


def test_depth_worker_refuses_mismatched_model_pin(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(
        cuda=SimpleNamespace(is_available=lambda: False)))
    monkeypatch.setitem(sys.modules, "transformers", SimpleNamespace(
        pipeline=lambda **kwargs: pytest.fail("unpinned model should not load")))
    monkeypatch.setattr(model_assets, "model_pin", lambda key: {
        "model_id": "unauthorized/other-model", "revision": "a" * 40,
    })
    with pytest.raises(RuntimeError, match="source pin"):
        depth_worker.infer({"output_dir": str(tmp_path),
                            "images": {"front": str(tmp_path / "unused.png")}})
