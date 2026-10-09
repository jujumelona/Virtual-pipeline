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


def test_inferred_colors_cover_unobserved_uv_only():
    # Two separate triangle islands: front is measured; back is unobserved.
    vertices = np.array([
        [0, 0, 0], [1, 0, 0], [0, 1, 0],
        [0, 0, 1], [0, 1, 1], [1, 0, 1],
    ], float)
    faces = np.array([[0, 1, 2], [3, 4, 5]])
    uv = np.array([
        [.1, .1], [.45, .1], [.1, .45],
        [.6, .6], [.9, .6], [.6, .9],
    ])
    front = np.zeros((64, 64, 4), dtype=np.uint8)
    front[..., 0] = 130
    front[..., 3] = 255
    xy = np.array([[10, 10], [50, 10], [10, 50],
                   [10, 10], [10, 50], [50, 10]], float)
    texture, stats = rasterize_multiview_texture(
        vertices, faces, uv, front, xy, 64, fill_unobserved=True
    )
    assert stats["painted_texels"] > 0
    assert stats["inferred_fill_texels"] > 0
    assert stats["inferred_colors_are_observed"] is False
    assert stats["surface_coverage_observed"] < 1
    assert texture[45, 45, 3] == 255
    assert texture[0, 0, 3] == 0


def test_registered_views_cannot_be_rotated_again_by_global_icp(tmp_path):
    from vtuber_pipeline.avatar.multiview_fitting import align_sources

    front = trimesh.creation.icosphere(subdivisions=2)
    coarse_path = tmp_path / "front.obj"
    front.export(coarse_path)
    observed = front.copy()
    observed.apply_translation((.04, 0, 0))
    combined = trimesh.util.concatenate((front, observed))
    candidate = tmp_path / "combined.obj"
    combined.export(candidate)
    source = tmp_path / "original-view.png"
    from PIL import Image
    Image.new("RGB", (64, 64), "white").save(source)
    depth_file = tmp_path / "depth.npy"
    np.save(depth_file, np.ones((64, 64), dtype=np.float32))
    depth_manifest = {
        "units": "relative/no-metric-scale",
        "views": {
            role: {
                "depth_npy": str(depth_file),
                "image_size": [64, 64],
                "observed_view": True,
                "relative_depth": True,
            } for role in ("front", "back")
        },
    }
    references = {
        "images": {role: {"path": str(source), "size": [64, 64]}
                   for role in ("front", "back")}
    }
    provenance = {
        "contract": "vtuber-commercial-triposr-multiview-v1",
        "geometry_provider": "TripoSR",
        "noncommercial_checkpoints_used": False,
        "geometry_mesh": str(candidate.resolve()),
        "registered_views": ["back"],
        "views": {
            "back": {
                "status": "registered",
                "input_view_observed": True,
                "input_image": str(source.resolve()),
            }
        },
    }
    source_meta = tmp_path / "provenance.json"
    source_meta.write_text(json.dumps(provenance))
    out = align_sources(
        str(coarse_path), str(candidate), depth_manifest,
        references, str(tmp_path / "aligned"), source_metadata=str(source_meta),
    )
    report = json.loads(Path(out["constraints_json"]).read_text())
    assert report["registration"]["source_frame_identity_verified"] is True
    assert report["transform"]["scale"] == 1.0
    assert np.allclose(report["transform"]["rotation_row_vector"], np.eye(3))
    assert np.allclose(report["transform"]["translation"], [0, 0, 0])
    assert report["independently_observed_roles"] == ["back"]
    assert report["front_only_reconstruction"] is False

    altered = combined.copy()
    altered.apply_translation((.1, 0, 0))
    altered.export(candidate)
    with pytest.raises(ValueError, match="original front camera frame"):
        align_sources(
            str(coarse_path), str(candidate), depth_manifest,
            references, str(tmp_path / "reject"), source_metadata=str(source_meta),
        )


def test_real_observed_view_records_and_reuses_foreground_cutout(
    tmp_path, monkeypatch,
):
    from PIL import Image
    import vtuber_pipeline.avatar.reconstruction as reconstruction
    import vtuber_pipeline.perception.anime_alpha as alpha_worker

    main = trimesh.creation.icosphere(subdivisions=2)
    main_path = tmp_path / "front.obj"
    main.export(main_path)
    reference = tmp_path / "back.png"
    Image.new("RGBA", (256, 256), (245, 245, 245, 255)).save(reference)
    cutout = tmp_path / "person_alpha.png"
    Image.new("RGBA", (256, 256), (30, 60, 90, 255)).save(cutout)
    calls = []

    def masked(image_path, output_dir):
        assert image_path == str(reference.resolve())
        calls.append("alpha")
        return {"status": "complete", "rgba_png": str(cutout)}

    def reconstructed(image, output_dir, *, profile, model_save_format,
                      remove_background):
        assert image == str(cutout)
        assert profile == "commercial"
        assert model_save_format == "obj"
        assert remove_background is False
        calls.append("triposr")
        result = tmp_path / "back_model.obj"
        main.export(result)
        return str(result)

    monkeypatch.setattr(alpha_worker, "create_person_alpha", masked)
    monkeypatch.setattr(reconstruction, "reconstruct_avatar", reconstructed)
    output = reconstruct_licensed_multiview(
        str(main_path), {"back": str(reference)}, str(tmp_path / "fused"),
    )
    assert output["status"] == "complete"
    assert output["registered_views"] == ["back"]
    assert calls == ["alpha", "triposr"]
    report = json.loads(Path(output["provenance_json"]).read_text())
    assert report["views"]["back"]["segmented_rgba"] == str(cutout.resolve())
    assert report["views"]["back"]["status"] == "registered"
    from vtuber_pipeline.avatar.build import AvatarPipeline
    import inspect
    orchestrator = inspect.getsource(AvatarPipeline.build)
    assert 'observed_texture_sources[role] = normalized' in orchestrator
    assert 'observed_texture_sources.get("back")' in orchestrator
