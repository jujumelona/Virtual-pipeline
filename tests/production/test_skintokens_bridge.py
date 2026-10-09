"""CPU-only production tests for real glTF SkinTokens handoff contracts."""
from pathlib import Path
import json
import shutil

import numpy as np
import pytest
import trimesh
from PIL import Image
from pygltflib import GLTF2

from vtuber_pipeline.avatar.rigging import (
    compute_skin_weights, create_gltf_with_skin, create_humanoid_skeleton,
)
from vtuber_pipeline.avatar.skintokens_bridge import (
    graft_weights, _read, runtime_identity, check_gpu_compatibility,
)


def _model(tmp_path, *, hair=False):
    mesh = trimesh.creation.box(extents=(1, 2, .5))
    bones = create_humanoid_skeleton(mesh.bounds)
    joints, weights = compute_skin_weights(
        np.asarray(mesh.vertices), bones,
        hair_vertex_start=(len(mesh.vertices) - 3 if hair else None),
    )
    texture = tmp_path / "texture.png"
    Image.new("RGB", (8, 8), (24, 56, 99)).save(texture)
    uv = tmp_path / "uv.npy"
    np.save(uv, np.tile(np.array([[.25, .5]], dtype=np.float32), (len(mesh.vertices), 1)))
    base = tmp_path / "canonical.glb"
    create_gltf_with_skin(
        mesh, bones, joints, weights, str(base),
        texture_path=str(texture), uv_path=str(uv),
        hair_vertex_start=(len(mesh.vertices) - 3 if hair else None),
    )
    predicted = tmp_path / "tokenrig.glb"
    shutil.copy2(base, predicted)
    return base, predicted


def _replace_accessor(file, name, matrix):
    gltf = GLTF2().load_binary(str(file))
    accessor_index = getattr(gltf.meshes[0].primitives[0].attributes, name)
    access = gltf.accessors[accessor_index]
    view = gltf.bufferViews[access.bufferView]
    payload = np.asarray(matrix, dtype="<f4" if name in {"POSITION", "WEIGHTS_0"} else "<u2").tobytes()
    assert len(payload) == view.byteLength
    blob = bytearray(gltf.binary_blob())
    off = (view.byteOffset or 0) + (access.byteOffset or 0)
    blob[off:off + len(payload)] = payload
    gltf.set_binary_blob(bytes(blob))
    gltf.save_binary(str(file))


def test_upstream_skin_grafted_without_losing_canonical_mesh_uv_texture(tmp_path):
    baseline, predicted = _model(tmp_path)
    baseline_gltf = GLTF2().load_binary(str(baseline))
    prediction = GLTF2().load_binary(str(predicted))
    attrs = prediction.meshes[0].primitives[0].attributes
    n = len(_read(prediction, attrs.POSITION))
    _replace_accessor(predicted, "JOINTS_0", np.tile([[5, 0, 0, 0]], (n, 1)))
    _replace_accessor(predicted, "WEIGHTS_0", np.tile([[1., 0, 0, 0]], (n, 1)))
    output = tmp_path / "skin.glb"
    result = graft_weights(str(baseline), str(predicted), str(output))
    assert result["status"] == "complete"
    assert result["vertices"] == n
    actual = GLTF2().load_binary(str(output))
    assert actual.nodes == baseline_gltf.nodes
    assert actual.materials == baseline_gltf.materials
    assert actual.images == baseline_gltf.images
    assert actual.meshes[0].extras == baseline_gltf.meshes[0].extras
    assert np.array_equal(_read(actual, attrs.POSITION),
                          _read(baseline_gltf, attrs.POSITION))
    assert np.array_equal(_read(actual, attrs.TEXCOORD_0),
                          _read(baseline_gltf, attrs.TEXCOORD_0))
    assert np.allclose(_read(actual, attrs.WEIGHTS_0)[:, 0], 1.)
    assert np.all(_read(actual, attrs.JOINTS_0)[:, 0] == 5)
    assert not np.array_equal(_read(baseline_gltf, attrs.WEIGHTS_0),
                              _read(actual, attrs.WEIGHTS_0))


def test_changed_geometry_fails_closed(tmp_path):
    baseline, predicted = _model(tmp_path)
    obj = GLTF2().load_binary(str(predicted))
    vertices = _read(obj, obj.meshes[0].primitives[0].attributes.POSITION)
    vertices[0, 0] += .1
    _replace_accessor(predicted, "POSITION", vertices)
    with pytest.raises(ValueError, match="topology/order/positions"):
        graft_weights(str(baseline), str(predicted), str(tmp_path / "rejected.glb"))
    assert not (tmp_path / "rejected.glb").exists()


def test_foreign_skeleton_fails_closed(tmp_path):
    baseline, predicted = _model(tmp_path)
    gltf = GLTF2().load_binary(str(predicted))
    gltf.nodes[gltf.skins[0].joints[1]].name = "NotAVRMBone"
    gltf.save_binary(str(predicted))
    with pytest.raises(ValueError, match="outside canonical"):
        graft_weights(str(baseline), str(predicted), str(tmp_path / "rejected.glb"))


def test_changed_bind_pose_fails_closed(tmp_path):
    baseline, predicted = _model(tmp_path)
    gltf = GLTF2().load_binary(str(predicted))
    attr_index = gltf.skins[0].inverseBindMatrices
    assert attr_index is not None
    original = _read(gltf, attr_index)
    original[0, 12] += .1
    access = gltf.accessors[attr_index]
    view = gltf.bufferViews[access.bufferView]
    blob = bytearray(gltf.binary_blob())
    offset = (view.byteOffset or 0) + (access.byteOffset or 0)
    payload = original.astype("<f4").tobytes()
    blob[offset:offset + len(payload)] = payload
    gltf.set_binary_blob(bytes(blob))
    gltf.save_binary(str(predicted))
    with pytest.raises(ValueError, match="rest-pose bind matrix"):
        graft_weights(str(baseline), str(predicted), str(tmp_path / "rejected.glb"))


def test_hair_cannot_be_rigged_to_torso(tmp_path):
    baseline, predicted = _model(tmp_path, hair=True)
    gltf = GLTF2().load_binary(str(predicted))
    n = len(_read(gltf, gltf.meshes[0].primitives[0].attributes.POSITION))
    _replace_accessor(predicted, "JOINTS_0", np.tile([[1, 0, 0, 0]], (n, 1)))
    _replace_accessor(predicted, "WEIGHTS_0", np.tile([[1., 0, 0, 0]], (n, 1)))
    with pytest.raises(ValueError, match="hair"):
        graft_weights(str(baseline), str(predicted), str(tmp_path / "no-hair.glb"))


def test_runtime_requires_explicit_isolated_install(monkeypatch):
    monkeypatch.delenv("VTUBER_SKINTOKENS_DIR", raising=False)
    with pytest.raises(RuntimeError, match="VTUBER_SKINTOKENS_DIR"):
        runtime_identity()


def test_t4_detected_and_rejected_before_inference(monkeypatch):
    import vtuber_pipeline.avatar.skintokens_bridge as bridge

    def fake_run(*args, **kwargs):
        class Completed:
            returncode = 0
            stdout = json.dumps({
                "device": "Tesla T4", "major": 7, "minor": 5,
                "total_bytes": 16 * 1024**3, "free_bytes": 15 * 1024**3,
                "bf16": False,
            }) + "\n"
            stderr = ""
        return Completed()

    monkeypatch.setattr(bridge.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="sm75"):
        check_gpu_compatibility({"python": "/env/python", "repo": "/tokenrig"})


def test_ampere_works_only_with_sufficient_free_memory(monkeypatch):
    import vtuber_pipeline.avatar.skintokens_bridge as bridge

    probe = {
        "device": "A100", "major": 8, "minor": 0,
        "total_bytes": 40 * 1024**3, "free_bytes": 3 * 1024**3,
        "bf16": True,
    }

    def fake_run(*args, **kwargs):
        class Completed:
            returncode = 0
            stdout = json.dumps(probe) + "\n"
            stderr = ""
        return Completed()

    monkeypatch.setattr(bridge.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="14 GiB free"):
        check_gpu_compatibility({"python": "/env/python", "repo": "/tokenrig"})
    probe["free_bytes"] = 36 * 1024**3
    assert check_gpu_compatibility({"python": "/env/python", "repo": "/tokenrig"})["device"] == "A100"
