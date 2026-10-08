import json

import numpy as np
import pytest
import trimesh

from vtuber_pipeline.accessory.visual_alignment import estimate_visual_alignment


def _fixture(tmp_path):
    path = tmp_path / "hat.glb"
    box = trimesh.creation.box(extents=[0.8, 1.2, 0.5])
    box.apply_translation([3.0, 4.0, 5.0])
    box.export(path)
    manifest = {"anchors": [{
        "name": "HEAD_TOP", "bone": "head", "target_size": 0.18,
        "node_index": 2, "position": [0, 1, 0], "offset": [0, 0.1, 0],
    }]}
    return path, box, manifest


def test_hat_pivot_is_contact_surface_not_center(tmp_path):
    path, box, manifest = _fixture(tmp_path)
    alignment = estimate_visual_alignment(str(path), "HEAD_TOP", manifest, str(tmp_path))
    assert alignment["status"] == "complete"
    assert alignment["pivot_rule"] == "lower_contact"
    assert np.allclose(alignment["source_pivot"], [3, 3.4, 5])
    saved = json.loads((tmp_path / "visual_alignment.json").read_text())
    assert saved["camera_orientation_verified"] is False


def test_missing_anchor_rejected(tmp_path):
    path, _, manifest = _fixture(tmp_path)
    with pytest.raises(ValueError, match="exactly one"):
        estimate_visual_alignment(str(path), "LEFT_EAR", manifest, str(tmp_path))
