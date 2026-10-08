"""CPU-only tests for real two-source similarity registration."""
import json

import numpy as np
import pytest
import trimesh

from vtuber_pipeline.avatar.multiview_fitting import align_sources


def _inputs(tmp_path):
    coarse = trimesh.creation.icosphere(subdivisions=2, radius=1.0)
    coarse.vertices *= np.array([0.7, 1.8, 0.52])
    generated = coarse.copy()
    generated.apply_scale(0.4)
    generated.apply_translation([2.0, -3.0, 1.0])
    coarse_path, inferred_path = tmp_path / "coarse.obj", tmp_path / "multiview.obj"
    coarse.export(coarse_path)
    generated.export(inferred_path)
    np.save(tmp_path / "depth_front.npy", np.ones((12, 8), dtype=np.float32))
    (tmp_path / "depth.json").write_text(json.dumps({
        "units": "relative/no-metric-scale",
        "views": {"front": {
            "observed_view": True, "relative_depth": True,
            "depth_npy": str(tmp_path / "depth_front.npy"), "image_size": [8, 12],
        }}
    }))
    (tmp_path / "reference.json").write_text(json.dumps({
        "images": {"front": {"path": str(tmp_path / "front.png")}}
    }))
    return coarse_path, inferred_path, tmp_path / "depth.json", tmp_path / "reference.json"


def test_align_sources_writes_actual_registered_glb(tmp_path):
    paths = _inputs(tmp_path)
    result = align_sources(*map(str, paths), str(tmp_path / "aligned"))
    assert result["status"] == "complete"
    registration = json.loads((tmp_path / "aligned" / "constraints.json").read_text())
    assert registration["registration"]["normalized_residual"] < 0.1
    assert not registration["registration"]["orientation_verified_by_calibrated_camera"]
    assert registration["observed_views"]["front"]["relative_depth_only"]
    aligned = trimesh.load(result["aligned_multiview_glb"], force="mesh")
    assert len(aligned.vertices) > 10


def test_rejects_claimed_generated_observation(tmp_path):
    paths = _inputs(tmp_path)
    manifest = json.loads(paths[2].read_text())
    manifest["views"]["front"]["observed_view"] = False
    paths[2].write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="generated data"):
        align_sources(*map(str, paths), str(tmp_path / "aligned"))
