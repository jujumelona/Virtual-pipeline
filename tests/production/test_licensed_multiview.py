"""Commercial-only 3D reference fusion and physically observed side texels."""
import json
from pathlib import Path

import numpy as np
import pytest
import trimesh

from vtuber_pipeline.avatar.licensed_multiview import (
    register_observed_geometry, reconstruct_licensed_multiview,
)
from vtuber_pipeline.avatar.uv_projection import rasterize_multiview_texture


def test_3d_pipeline_succeeds_with_only_real_front_reference(tmp_path):
    source = tmp_path / "front.obj"
    trimesh.creation.icosphere(subdivisions=2).export(source)
    output = reconstruct_licensed_multiview(str(source), {
        "back": None, "left": None, "right": None,
    }, str(tmp_path / "fused"))
    assert output["status"] == "complete"
    assert Path(output["mesh_obj"]).is_file()
    manifest = json.loads(Path(output["provenance_json"]).read_text())
    assert manifest["front_only"] is True
    assert manifest["registered_views"] == []
    assert manifest["noncommercial_checkpoints_used"] is False
    assert manifest["views"]["back"]["status"] == "unobserved"
    assert "TripoSR" in manifest["geometry_provider"]


def test_known_camera_orientation_registers_the_same_surface():
    mesh = trimesh.creation.icosphere(subdivisions=2)
    xyz = np.asarray(mesh.vertices).copy()
    for role, theta in (("left", -np.pi / 2),
                        ("right", np.pi / 2), ("back", -np.pi)):
        c, s = np.cos(theta), np.sin(theta)
        r = np.array([[c, 0., -s], [0., 1., 0.], [s, 0., c]])
        aligned, report = register_observed_geometry(xyz, xyz @ r, role)
        assert report["accepted"] is True
        assert report["normalized_registration_error"] < 1e-5
        assert np.allclose(np.sort(aligned[:, 1]), np.sort(xyz[:, 1]))


def test_side_pixels_only_cover_correct_visible_normals():
    vertices = np.array([[.5, 0, -.5], [.5, 1., -.5], [.5, 0, .5]])
    faces = np.array([[0, 1, 2]])
    uv = np.array([[.1, .1], [.85, .1], [.1, .85]])
    rgb = np.zeros((64, 64, 4), dtype=np.uint8)
    rgb[..., 0] = 180
    rgb[..., 3] = 255
    blank = np.zeros_like(rgb)
    projected = np.array([[10, 10], [50, 10], [10, 50]], float)
    empty, count = rasterize_multiview_texture(
        vertices, faces, uv, blank, projected, 64
    )
    assert not np.any(empty[..., 3])
    assert count["painted_texels"] == 0
    painted, stats = rasterize_multiview_texture(
        vertices, faces, uv, blank, projected, 64,
        right_pixels=rgb, right_xy=projected,
    )
    assert stats["view_texel_samples"]["right"] > 150
    assert np.count_nonzero(painted[..., 0] == 180) > 150


def test_rejects_unlabelled_or_nonfinite_registration():
    target = np.zeros((50, 3))
    target[:, 1] = np.linspace(-1, 1, 50)
    with pytest.raises(ValueError, match="camera roles"):
        register_observed_geometry(target, target, "invented_back")
    invalid = target.copy()
    invalid[0, 0] = np.nan
    with pytest.raises(ValueError, match="finite"):
        register_observed_geometry(target, invalid, "left")


def test_product_mainline_uses_only_permissive_reconstructor():
    import inspect
    from vtuber_pipeline.avatar.build import AvatarPipeline
    source = inspect.getsource(AvatarPipeline.build)
    assert '"licensed_multiview"' in source
    assert "reconstruct_licensed_multiview" in source
    assert '"instantmesh"' not in source
    assert "reconstruct_multiview(" not in source
