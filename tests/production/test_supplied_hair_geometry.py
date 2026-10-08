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


def test_each_independent_ribbon_has_its_own_springbone_chain(tmp_path):
    from vtuber_pipeline.avatar.rigging import _hair_component_vertex_groups
    from vtuber_pipeline.avatar.springbone import classify_springbone_chains

    body, uv, hair_path, _, _ = _inputs(tmp_path)
    strand_a = trimesh.load(hair_path, force="mesh")
    strand_b = strand_a.copy()
    strand_b.apply_translation([.25, 0, 0])
    trimesh.util.concatenate((strand_a, strand_b)).export(hair_path)

    merged, _rig_uv, start = _combine_supplied_hair_geometry(body, uv, hair_path)
    groups = _hair_component_vertex_groups(merged, start)
    assert len(groups) == 2
    skeleton = create_humanoid_skeleton(
        merged.bounds,
        strand_vertex_groups=[np.asarray(merged.vertices)[g] for g in groups],
    )
    joints, weights = compute_skin_weights(
        np.asarray(merged.vertices), skeleton,
        hair_vertex_start=start, strand_vertex_groups=groups,
    )
    for index, group in enumerate(groups):
        own = np.array([
            i for i, name in enumerate(skeleton["names"])
            if name.startswith(f"hairStrand{index:02d}")
        ])
        other = np.array([
            i for i, name in enumerate(skeleton["names"])
            if name.startswith(f"hairStrand{1-index:02d}")
        ])
        assert len(own) == 3
        assert np.any(np.isin(joints[group], own) & (weights[group] > 0))
        assert not np.any(np.isin(joints[group], other) & (weights[group] > 0))

    springs = classify_springbone_chains("no_mesh_read_needed", skeleton)
    strand_springs = [s for s in springs if s["name"].startswith("hairStrand")]
    assert [s["name"] for s in strand_springs] == [
        "hairStrand00", "hairStrand01",
    ]
    assert all(len(s["joints"]) == 3 for s in strand_springs)
    assert all(s["joints"][0]["node"].endswith("Root") for s in strand_springs)
