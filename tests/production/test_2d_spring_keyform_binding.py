"""Spring physics must animate real triangles, not reference undefined parameters."""
import json

import numpy as np
import pytest

from vtuber_pipeline.two_d.keyforms import build_keyforms
from vtuber_pipeline.two_d.physics2d import build_physics
from vtuber_pipeline.two_d.rig_spec import build_puppet_spec


def _prepare(tmp_path, *, with_mesh=True):
    parts = tmp_path / "parts.json"
    meshes = tmp_path / "meshes.json"
    quad = [[20, 10], [40, 10], [40, 80], [20, 80]]
    parts.write_text(json.dumps({
        "width": 128, "height": 128,
        "parts": [
            {"semantic_id": "hair.front", "bbox_xyxy": [20, 10, 40, 80],
             "z_order": 50, "rgba_png": "art-hair.png"},
            {"semantic_id": "eye.left.iris", "bbox_xyxy": [40, 20, 55, 31],
             "z_order": 70, "rgba_png": "art-eye.png"},
        ]}))
    mesh_parts = [
        {"semantic_id": "hair.front", "vertices_xy": quad},
        {"semantic_id": "eye.left.iris",
         "vertices_xy": [[40, 20], [55, 20], [55, 31], [40, 31]]},
    ]
    meshes.write_text(json.dumps({"width": 128, "height": 128,
                                  "meshes": mesh_parts if with_mesh else []}))
    keys = build_keyforms(str(meshes), str(parts), "unused", str(tmp_path))
    return parts, meshes, keys


def test_spring_parameter_is_bound_to_real_hair_mesh_delta(tmp_path):
    parts, meshes, keys = _prepare(tmp_path)
    physics = build_physics(keys["keyforms_json"], str(parts), str(tmp_path),
                            meshes_json=str(meshes))
    puppet = build_puppet_spec(str(parts), str(meshes), keys["keyforms_json"],
                               physics["physics_json"], str(tmp_path),
                               str(tmp_path / "puppet_spec.json"))
    result = json.loads(open(puppet).read())
    param = "physics.hair.front.sway"
    assert result["parameters"][param] == [-1.0, 0.0, 1.0]
    assert len(result["physics"]) == 1
    assert result["physics"][0]["target_parameter"] == param
    assert result["physics"][0]["deformation_keyforms_bound"] is True
    hair = next(p for p in result["keyforms"] if p["semantic_id"] == "hair.front")
    eye = next(p for p in result["keyforms"] if p["semantic_id"] == "eye.left.iris")
    assert param not in eye["deltas"]
    sway = hair["deltas"][param]
    assert np.max(np.abs(np.asarray(sway["max"]))) > 0
    assert np.max(np.abs(np.asarray(sway["min"]))) > 0
    assert not np.any(np.asarray(sway["default"]))
    vertices = np.array([[20, 10], [40, 10], [40, 80], [20, 80]])
    displacement = np.asarray(sway["max"])
    # Ribbon pivot sits on the top center: symmetrical top points deform
    # but have less motion than the long, freely hanging lower ends.
    assert np.linalg.norm(displacement[2]) > np.linalg.norm(displacement[1])


def test_no_inert_physics_is_written_when_mesh_contract_missing(tmp_path):
    parts, meshes, keys = _prepare(tmp_path, with_mesh=False)
    with pytest.raises(ValueError, match="cannot bind spring"):
        build_physics(keys["keyforms_json"], str(parts), str(tmp_path),
                      meshes_json=str(meshes))
    assert not (tmp_path / "physics2d.json").exists()
