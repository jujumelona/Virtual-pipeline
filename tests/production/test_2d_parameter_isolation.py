"""Regression checks for independently driven gaze and common rig frames."""
import json

import numpy as np

from vtuber_pipeline.two_d.keyforms import build_keyforms


def test_gaze_moves_only_iris_pupil_and_glint(tmp_path):
    parts = ("face", "eye.left.white", "eye.left.lid", "eye.left.iris",
             "eye.left.pupil", "eye.right.iris", "eye.right.white")
    m = tmp_path / "mesh.json"
    m.write_text(json.dumps({"meshes": [
        {"semantic_id": name, "vertices_xy": [
            [10 + 30 * i, 10], [20 + 30 * i, 10],
            [20 + 30 * i, 20], [10 + 30 * i, 20]]}
        for i, name in enumerate(parts)]}))
    output = build_keyforms(str(m), "unused", "unused", str(tmp_path))
    result = json.loads(open(output["keyforms_json"]).read())
    by_id = {item["semantic_id"]: item["deltas"] for item in result["keyforms"]}
    for part in ("face", "eye.left.white", "eye.left.lid", "eye.right.white"):
        assert "eye.x" not in by_id[part] and "eye.y" not in by_id[part]
    for part in ("eye.left.iris", "eye.left.pupil", "eye.right.iris"):
        assert np.any(np.asarray(by_id[part]["eye.x"]["max"]))
        assert np.any(np.asarray(by_id[part]["eye.y"]["max"]))


def test_head_rotation_moves_eyes_in_same_head_coordinate_system(tmp_path):
    m = tmp_path / "mesh.json"
    mesh = [
        {"semantic_id": "face", "vertices_xy": [[0, 0], [100, 0], [100, 100], [0, 100]]},
        {"semantic_id": "eye.left.iris", "vertices_xy": [[20, 35], [30, 35], [30, 45], [20, 45]]},
        {"semantic_id": "eye.right.iris", "vertices_xy": [[70, 35], [80, 35], [80, 45], [70, 45]]},
    ]
    m.write_text(json.dumps({"meshes": mesh}))
    result = build_keyforms(str(m), "unused", "unused", str(tmp_path))
    data = json.loads(open(result["keyforms_json"]).read())
    keyed = {item["semantic_id"]: item["deltas"] for item in data["keyforms"]}
    a = np.asarray(keyed["eye.left.iris"]["head.angle_z"]["max"]).mean(axis=0)
    b = np.asarray(keyed["eye.right.iris"]["head.angle_z"]["max"]).mean(axis=0)
    assert a[1] < 0 < b[1], "eyes must orbit a shared head pivot"
    assert data["multiview_reference_keyforms_bound"] is False


def test_body_angle_does_not_stretch_outfit_panels(tmp_path):
    m = tmp_path / "mesh.json"
    m.write_text(json.dumps({"meshes": [
        {"semantic_id": "body", "vertices_xy": [[0, 0], [100, 0], [100, 100], [0, 100]]},
        {"semantic_id": "cloth.front", "vertices_xy": [[20, 20], [80, 20], [80, 90], [20, 90]]},
        {"semantic_id": "cloth.sleeve.left", "vertices_xy": [[0, 20], [20, 20], [20, 70], [0, 70]]},
    ]}))
    result = build_keyforms(str(m), "unused", "unused", str(tmp_path))
    data = json.loads(open(result["keyforms_json"]).read())
    keyed = {item["semantic_id"]: item["deltas"] for item in data["keyforms"]}
    for part in ("body", "cloth.front", "cloth.sleeve.left"):
        for p in ("body.angle_x", "body.angle_y"):
            offset = np.asarray(keyed[part][p]["max"])
            assert np.allclose(offset, offset[0]), (part, p)
