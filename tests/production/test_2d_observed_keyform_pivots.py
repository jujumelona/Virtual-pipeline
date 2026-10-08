"""Observed HRNet part coordinates must affect genuine mesh deformation."""
import json
import numpy as np
from vtuber_pipeline.two_d.keyforms import build_keyforms


def test_eye_closure_uses_measured_eye_pivot_not_fabricated_center(tmp_path):
    vertices = [[10, 10], [30, 10], [30, 20], [10, 20]]
    mesh = tmp_path / "mesh.json"
    mesh.write_text(json.dumps({"meshes": [
        {"semantic_id": "eye.left.iris", "vertices_xy": vertices}
    ]}))
    parts = tmp_path / "parts.json"
    parts.write_text(json.dumps({"parts": [{
        "semantic_id": "eye.left.iris", "landmarks_xy": [[18, 13], [22, 13]]
    }]}))
    result = build_keyforms(str(mesh), str(parts), "unused", str(tmp_path))
    data = json.loads(open(result["keyforms_json"]).read())["keyforms"][0]
    assert data["pivot_source"] == "observed_hrnet"
    assert np.allclose(data["pivot_xy"], [20, 13])
    closed = np.asarray(vertices) + np.asarray(data["deltas"]["eye.left.open"]["min"])
    assert np.allclose(closed[:, 1], 13)


def test_out_of_frame_landmarks_cannot_move_a_part(tmp_path):
    vertices = [[10, 10], [30, 10], [30, 20], [10, 20]]
    mesh = tmp_path / "mesh.json"
    mesh.write_text(json.dumps({"meshes": [
        {"semantic_id": "eye.left.iris", "vertices_xy": vertices}
    ]}))
    parts = tmp_path / "parts.json"
    parts.write_text(json.dumps({"parts": [{
        "semantic_id": "eye.left.iris", "landmarks_xy": [[5000, 7000]]
    }]}))
    result = build_keyforms(str(mesh), str(parts), "unused", str(tmp_path))
    item = json.loads(open(result["keyforms_json"]).read())["keyforms"][0]
    assert item["pivot_source"] == "mesh_centroid"
    assert np.allclose(item["pivot_xy"], [20, 15])
