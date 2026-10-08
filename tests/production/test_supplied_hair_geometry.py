"""Actual surface-refine hair must reach the rig instead of being ignored."""
import numpy as np
import pytest
import trimesh

from vtuber_pipeline.avatar.rigging import _combine_supplied_hair_geometry, compute_skin_weights, create_humanoid_skeleton


def _inputs(tmp_path):
    body = trimesh.creation.icosphere(subdivisions=3)
    verts = np.asarray(body.vertices)
    uv = np.column_stack((.5 + .35 * verts[:, 0], .5 + .35 * verts[:, 1])).astype(np.float32)
    ribbon = trimesh.Trimesh(
        vertices=np.array([[0., .88, .90], [.05, .88, .90],
                           [0., .70, .91], [.05, .70, .91]], dtype=float),
        faces=np.array([[0, 2, 1], [1, 2, 3]]), process=False,
    )
    hair_path = tmp_path / "hair.glb"
    ribbon.export(hair_path)
    return body, uv, str(hair_path), len(ribbon.vertices), len(ribbon.faces)


def test_real_ribbon_geometry_is_appended_with_skin_restricted_to_head(tmp_path):
    body, uv, hair_path, count, faces = _inputs(tmp_path)
    merged, rig_uv, start = _combine_supplied_hair_geometry(body, uv, hair_path)
    assert start == len(body.vertices)
    assert len(merged.vertices) == start + count
    assert len(merged.faces) == len(body.faces) + faces
    assert np.array_equal(np.asarray(merged.vertices)[:start], np.asarray(body.vertices))
    assert np.array_equal(np.asarray(merged.faces)[:len(body.faces)], np.asarray(body.faces))
    assert rig_uv.shape == (len(merged.vertices), 2)
    skeleton = create_humanoid_skeleton(merged.bounds)
    joints, weights = compute_skin_weights(np.asarray(merged.vertices), skeleton,
                                           hair_vertex_start=start)
    hair_slots = [i for i, name in enumerate(skeleton["names"])
                  if name.lower().startswith("hair")]
    assert hair_slots
    assert not np.any(np.isin(joints[:start], hair_slots) & (weights[:start] > 0))
    assert np.any(np.isin(joints[start:], hair_slots) & (weights[start:] > 0))


def test_distant_unregistered_hair_fails_closed(tmp_path):
    body, uv, hair_path, _, _ = _inputs(tmp_path)
    hair = trimesh.load(hair_path, force="mesh")
    hair.apply_translation([100, 0, 0])
    hair.export(hair_path)
    with pytest.raises(ValueError, match="too far"):
        _combine_supplied_hair_geometry(body, uv, hair_path)
