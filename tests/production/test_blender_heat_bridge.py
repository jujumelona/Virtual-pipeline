"""CPU contracts for true Blender heat-group -> canonical VRM skin transfer.

These tests use the real pygltflib writer/readback. The Blender operator
itself is an explicitly separate native-runtime (not mocked GPU) gate.
"""
import numpy as np
import pytest
from pygltflib import GLTF2

from tests.production.test_skintokens_bridge import _model
from vtuber_pipeline.avatar.skintokens_bridge import _read
from vtuber_pipeline.avatar.blender_heat_bridge import (
    _neck_height, graft_blender_weight_groups,
)


def _groups(tmp_path, n, names, *, weight=1.):
    path = tmp_path / "blender_groups.npz"
    indices = np.full((n, 4), -1, dtype=np.int32)
    indices[:, 0] = 0
    weights = np.zeros((n, 4), dtype=np.float32)
    weights[:, 0] = weight
    np.savez_compressed(
        path, group_names=np.asarray(names, dtype="U128"),
        group_indices=indices, group_weights=weights,
    )
    return str(path)


def test_blender_heat_graft_preserves_head_hair_uv_and_all_other_glb_data(tmp_path):
    base, _ = _model(tmp_path, hair=True)
    before = GLTF2().load_binary(str(base))
    attr = before.meshes[0].primitives[0].attributes
    vertices = _read(before, attr.POSITION)
    n = len(vertices)
    path = _groups(tmp_path, n, ["leftUpperLeg"])
    out = tmp_path / "blender_heat.glb"
    result = graft_blender_weight_groups(str(base), path, str(out))
    assert result["status"] == "complete"
    assert result["changed_body_vertices"] >= 1
    after = GLTF2().load_binary(str(out))
    assert after.nodes == before.nodes
    assert after.meshes[0].extras == before.meshes[0].extras
    assert after.images == before.images
    assert np.array_equal(_read(after, attr.POSITION), vertices)
    assert np.array_equal(_read(after, attr.TEXCOORD_0),
                          _read(before, attr.TEXCOORD_0))
    before_j = _read(before, attr.JOINTS_0)
    after_j = _read(after, attr.JOINTS_0)
    before_w = _read(before, attr.WEIGHTS_0)
    after_w = _read(after, attr.WEIGHTS_0)
    eligible = np.arange(n) < before.meshes[0].extras["hairVertexStart"]
    eligible &= vertices[:, 1] < _neck_height(before) - .01
    np.testing.assert_array_equal(after_j[~eligible], before_j[~eligible])
    np.testing.assert_array_equal(after_w[~eligible], before_w[~eligible])
    np.testing.assert_array_equal(after_j[eligible, 0],
                                  [before.skins[0].joints.index(next(
                                      i for i in before.skins[0].joints
                                      if before.nodes[i].name == "leftUpperLeg"))
                                   ] * int(eligible.sum()))
    np.testing.assert_allclose(after_w[eligible, 0], 1.)


def test_blender_heat_rejects_unweighted_body(tmp_path):
    base, _ = _model(tmp_path)
    gltf = GLTF2().load_binary(str(base))
    n = len(_read(gltf, gltf.meshes[0].primitives[0].attributes.POSITION))
    path = _groups(tmp_path, n, ["unrecognized_blender_joint"])
    with pytest.raises(ValueError, match="unweighted"):
        graft_blender_weight_groups(str(base), path, str(tmp_path / "rejected.glb"))


def test_blender_heat_rejects_invalid_group_indices(tmp_path):
    base, _ = _model(tmp_path)
    gltf = GLTF2().load_binary(str(base))
    n = len(_read(gltf, gltf.meshes[0].primitives[0].attributes.POSITION))
    path = _groups(tmp_path, n, ["leftUpperLeg"])
    with np.load(path, allow_pickle=False) as x:
        i, w, names = x["group_indices"].copy(), x["group_weights"], x["group_names"]
    i[0, 0] = 99
    np.savez(path, group_indices=i, group_weights=w, group_names=names)
    with pytest.raises(ValueError, match="invalid weights/groups"):
        graft_blender_weight_groups(str(base), path, str(tmp_path / "rejected.glb"))
