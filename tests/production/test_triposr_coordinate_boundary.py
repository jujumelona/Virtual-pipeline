"""Pinned TripoSR coordinates must enter the Y-up avatar frame unchanged in scale."""
import numpy as np
import pytest
import trimesh

from vtuber_pipeline.avatar import reconstruction


@pytest.mark.parametrize("extension", ["obj", "glb"])
def test_triposr_adapter_converts_axes_and_preserves_upstream_mesh(tmp_path, extension):
    # Asymmetric coloured mesh distinguishes all axes and catches reflections.
    source = trimesh.creation.box(extents=(0.4, 0.8, 1.6))
    source.apply_translation([0.1, 0.2, 0.3])
    source.visual.vertex_colors = np.tile([40, 90, 180, 255], (len(source.vertices), 1))
    native = tmp_path / f"mesh.{extension}"
    source.export(native)
    original_bytes = native.read_bytes()
    target = tmp_path / f"mesh_canonical.{extension}"
    reconstruction.canonicalize_triposr_mesh(native, target)
    result = trimesh.load(target, force="mesh", process=False)
    expected = np.column_stack((-source.vertices[:, 1], source.vertices[:, 2], -source.vertices[:, 0]))
    # Export/import may reorder vertices, so compare coordinate sets.
    np.testing.assert_allclose(
        np.array(sorted(result.vertices.tolist())), np.array(sorted(expected.tolist())), atol=1e-7,
    )
    assert result.volume == pytest.approx(source.volume)
    assert result.is_winding_consistent
    assert np.ptp(result.vertices, axis=0)[1] == pytest.approx(1.6)
    assert np.all(result.visual.vertex_colors[:, :3] == [40, 90, 180])
    assert native.read_bytes() == original_bytes


def test_converted_triposr_front_receives_actual_front_texture(tmp_path):
    from vtuber_pipeline.avatar.uv_projection import rasterize_multiview_texture
    # Pinned TripoSR front is -X. The source -Y direction is screen-right
    # when looking at that front; Z is up. Winding gives a -X-facing normal.
    source = trimesh.Trimesh(
        vertices=[[-1, .4, .2], [-1, -.4, .2], [-1, .4, 1.2]],
        faces=[[0, 1, 2]], process=False,
    )
    native, target = tmp_path / "native.obj", tmp_path / "canonical.obj"
    source.export(native)
    reconstruction.canonicalize_triposr_mesh(native, target)
    canonical = trimesh.load(target, force="mesh", process=False)
    np.testing.assert_allclose(canonical.face_normals[0], [0, 0, 1])
    assert canonical.vertices[1, 0] > canonical.vertices[0, 0]
    assert canonical.vertices[2, 1] > canonical.vertices[0, 1]
    front = np.full((64, 64, 4), [210, 20, 30, 255], dtype=np.uint8)
    back = np.full((64, 64, 4), [20, 30, 210, 255], dtype=np.uint8)
    projected = np.array([[4, 60], [60, 60], [4, 4]])
    texture, evidence = rasterize_multiview_texture(
        canonical.vertices, canonical.faces, np.array([[.1, .1], [.9, .1], [.1, .9]]),
        front, projected, 64, back_pixels=back, back_xy=projected,
    )
    painted = texture[:, :, 3] > 0
    assert painted.any()
    assert np.all(texture[painted] == [210, 20, 30, 255])


def test_reconstruct_returns_canonical_geometry_and_retains_native_output(tmp_path, monkeypatch):
    import subprocess
    from PIL import Image
    image = tmp_path / "input.png"
    Image.new("RGB", (16, 16), "gray").save(image)
    run_script = tmp_path / "run.py"
    run_script.write_text("# GPU inference supplied separately")
    monkeypatch.setattr(reconstruction, "find_triposr_installation", lambda: str(run_script))
    monkeypatch.setattr(reconstruction, "verify_triposr_revision", lambda *_args: None)
    monkeypatch.setattr(reconstruction, "resolve_triposr_model", lambda: str(tmp_path / "model"))
    native_mesh = trimesh.creation.icosphere(subdivisions=1)
    native_mesh.vertices *= [0.4, 0.8, 1.6]

    def inference(command, **_kwargs):
        output = tmp_path / "out" / "0" / "mesh.obj"
        output.parent.mkdir(parents=True, exist_ok=True)
        native_mesh.export(output)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(reconstruction, "_run_triposr_with_diagnostics", inference)
    result = reconstruction.reconstruct_avatar(str(image), str(tmp_path / "out"))
    assert result.endswith("mesh_canonical.obj")
    canonical = trimesh.load(result, force="mesh", process=False)
    native = trimesh.load(tmp_path / "out" / "0" / "mesh.obj", process=False)
    np.testing.assert_allclose(np.ptp(canonical.vertices, axis=0), [1.6, 3.2, 0.8])
    np.testing.assert_allclose(np.ptp(native.vertices, axis=0), [0.8, 1.6, 3.2])
