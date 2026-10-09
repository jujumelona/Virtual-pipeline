"""Isolated crop/alpha regression: no FLUX weights or GPU needed."""
import numpy as np
from PIL import Image

from tools.model_workers.flux_worker import prepare_masked_edit
from vtuber_pipeline.perception.compose import masked_repair


def test_model_sees_bounded_crop_with_explicit_gray_hole():
    source = Image.new("RGB", (1536, 2048), (11, 22, 33))
    mask = Image.new("L", source.size)
    data = np.zeros((2048, 1536), dtype=np.uint8)
    data[960:973, 720:731] = 255
    mask = Image.fromarray(data, "L")
    patch, box = prepare_masked_edit(source, mask)
    assert patch.size[0] <= 1024 and patch.size[1] <= 1024
    assert patch.width % 16 == 0 and patch.height % 16 == 0
    assert 720 >= box[0] and 731 <= box[2]
    assert 960 >= box[1] and 973 <= box[3]
    pixels = np.asarray(patch)
    assert np.any(np.all(pixels == [128, 128, 128], axis=-1))
    assert np.any(np.all(pixels == [11, 22, 33], axis=-1))


def test_masked_crop_composition_preserves_visible_pixels_exactly():
    source = np.full((32, 48, 4), (15, 25, 35, 255), dtype=np.uint8)
    mask = np.zeros((32, 48), dtype=np.uint8)
    mask[12:20, 22:28] = 255
    generated = np.full((32, 48, 3), (200, 100, 50), dtype=np.uint8)
    result = masked_repair(source, generated, mask)
    assert np.array_equal(result[mask == 0], source[mask == 0])
    assert np.all(result[mask > 0, :3] == (200, 100, 50))


def test_restored_pixels_extend_rig_mask_and_mesh_not_only_rgba(tmp_path):
    """An occluded layer must retain the repair in downstream triangulation."""
    import json
    from vtuber_pipeline.common.schemas import Part, PartsDocument
    from vtuber_pipeline.two_d.mesh2d import generate_meshes
    from tools.model_workers.flux_worker import commit_repaired_part

    observed = np.zeros((64, 64, 4), dtype=np.uint8)
    observed[16:40, 18:42, :3] = [10, 20, 30]
    observed[16:40, 18:42, 3] = 255
    source = tmp_path / "observed.png"
    Image.fromarray(observed, "RGBA").save(source)
    old_mask = tmp_path / "observed_mask.png"
    Image.fromarray(observed[:, :, 3], "L").save(old_mask)
    hidden = np.zeros((64, 64), dtype=np.uint8)
    hidden[10:16, 20:35] = 255
    hidden_file = tmp_path / "hidden.png"
    Image.fromarray(hidden, "L").save(hidden_file)
    part = Part("hair.front", str(source), str(old_mask), str(hidden_file),
                [18, 16, 42, 40], 70, [], "sam2.1")

    patch = np.full((6, 15, 3), [220, 60, 70], dtype=np.uint8)
    report = commit_repaired_part(
        part, Image.fromarray(hidden, "L"), patch, (20, 10, 35, 16),
        tmp_path / "repaired", 0,
    )
    rgba = np.asarray(Image.open(part.rgba_png).convert("RGBA"))
    repaired_mask = np.asarray(Image.open(part.mask_png).convert("L"))
    assert (rgba[12, 25] == [220, 60, 70, 255]).all()
    assert (rgba[20, 25] == [10, 20, 30, 255]).all()
    assert np.array_equal(rgba[:, :, 3], repaired_mask)
    assert part.bbox_xyxy == [18, 10, 42, 40]
    assert part.hidden_fill_mask_png is None
    assert report["mask_png"] == part.mask_png
    assert report["semantic_hole_pixels"] == 6 * 15

    doc = PartsDocument(64, 64, [part], None, "")
    parts_json = doc.write(str(tmp_path / "parts.json"))
    result = generate_meshes(parts_json, str(tmp_path / "mesh"))
    mesh = json.loads(open(result["meshes_json"], encoding="utf-8").read())["meshes"][0]
    vertices = np.asarray(mesh["vertices_xy"])
    assert mesh["connected_components"] == 1
    assert vertices[:, 1].min() <= 10  # restored area became rig geometry


def test_repair_rejects_misaligned_hidden_mask_before_writing(tmp_path):
    import pytest
    from vtuber_pipeline.common.schemas import Part
    from tools.model_workers.flux_worker import commit_repaired_part

    source = tmp_path / "part.png"
    Image.new("RGBA", (32, 32), (1, 2, 3, 255)).save(source)
    part = Part("face", str(source), str(source), "hidden.png",
                [0, 0, 32, 32], 50, [], "sam2.1")
    with pytest.raises(ValueError, match="canvas mismatch"):
        commit_repaired_part(
            part, Image.new("L", (16, 16), 255),
            np.zeros((4, 4, 3), dtype=np.uint8), (0, 0, 4, 4),
            tmp_path / "repaired", 0,
        )


def test_pinned_flux2_vae_decoder_uses_real_small_tiles():
    """Merely enable_tiling() leaves Flux2's ineffective 1024px default."""
    from types import SimpleNamespace
    from tools.model_workers.flux_worker import configure_low_memory_decode

    class VAE:
        config = SimpleNamespace(block_out_channels=[128, 256, 512, 512])
        tile_sample_min_size = 1024
        tile_latent_min_size = 128
        tile_overlap_factor = 0.25
        use_tiling = False
        use_slicing = False

        def enable_tiling(self):
            self.use_tiling = True

        def enable_slicing(self):
            self.use_slicing = True

    vae = VAE()
    configure_low_memory_decode(SimpleNamespace(vae=vae))
    assert vae.use_tiling
    assert vae.use_slicing
    assert vae.tile_sample_min_size == 256
    assert vae.tile_latent_min_size == 32
    # A 1024px image is divided into smaller decode tiles rather than one
    # full VAE activation tensor. No output resolution was reduced.
    assert (1024 // 8) > vae.tile_latent_min_size


def test_low_memory_decoder_does_not_accept_unbounded_tiles():
    from types import SimpleNamespace
    import pytest
    from tools.model_workers.flux_worker import configure_low_memory_decode

    with pytest.raises(ValueError, match="multiple of 16"):
        configure_low_memory_decode(SimpleNamespace(vae=None), tile_pixels=255)


def test_flux_decode_boundary_is_a_real_process_exit_not_empty_cache():
    import inspect
    from tools.model_workers import flux_worker, flux_latent_worker, flux_decode_worker

    parent = inspect.getsource(flux_worker.infer)
    denoiser = inspect.getsource(flux_latent_worker.run)
    decoder = inspect.getsource(flux_decode_worker.run)
    assert "flux_latent_worker.py" in parent
    assert "flux_decode_worker.py" in parent
    assert parent.index("flux_latent_worker.py") < parent.index("flux_decode_worker.py")
    assert "low_cpu_mem_usage=True" in denoiser
    assert "pipe.enable_model_cpu_offload()" in denoiser
    assert 'output_type="latent"' in denoiser
    assert "after_final_denoise_step_part_" in denoiser
    assert "from_pretrained(" in decoder
    assert 'subfolder="vae"' in decoder
    assert "configure_low_memory_decode(" in decoder
    assert "before_vae_only_decode_part_" in decoder
    assert "edited.resize(" in parent


def test_flux_split_process_handoff_preserves_visible_pixels(tmp_path, monkeypatch):
    """The heavy denoiser must finish before VAE starts; no synthetic fill mask."""
    import json
    from vtuber_pipeline.common.schemas import Part, PartsDocument
    from tools.model_workers import flux_worker

    input_image = tmp_path / "reference.png"
    Image.new("RGB", (64, 64), (10, 30, 50)).save(input_image)
    pixels = np.zeros((64, 64, 4), np.uint8)
    pixels[20:45, 15:40] = (10, 30, 50, 255)
    source = tmp_path / "layer.png"
    Image.fromarray(pixels, "RGBA").save(source)
    old_mask = tmp_path / "layer-mask.png"
    Image.fromarray(pixels[:, :, 3], "L").save(old_mask)
    hidden = np.zeros((64, 64), np.uint8)
    hidden[14:20, 20:28] = 255
    hidden_png = tmp_path / "hidden.png"
    Image.fromarray(hidden, "L").save(hidden_png)
    part = Part("hair.front", str(source), str(old_mask), str(hidden_png),
                [15, 20, 40, 45], 70, [], "sam2.1")
    doc = PartsDocument(64, 64, [part], None, "")
    plan = doc.write(str(tmp_path / "parts.json"))
    calls = []

    def fake_phase(script, source, destination):
        calls.append(script)
        assert calls == ["flux_latent_worker.py"] if len(calls) == 1 else (
            calls == ["flux_latent_worker.py", "flux_decode_worker.py"])
        if script == "flux_latent_worker.py":
            destination.write_text(json.dumps({"repairs": [
                {"index": 0, "semantic_id": "hair.front",
                 "latent_path": str(tmp_path / "latent.safetensors"),
                 "box": [18, 12, 30, 22], "input_wh": [256, 256]},
            ]}))
            return
        restored = tmp_path / "restored.png"
        Image.new("RGB", (256, 256), (200, 80, 40)).save(restored)
        destination.write_text(json.dumps({"repairs": [
            {"index": 0, "semantic_id": "hair.front",
             "decoded_png": str(restored), "box": [18, 12, 30, 22],
             "input_wh": [256, 256]},
        ]}))

    monkeypatch.setattr(flux_worker, "_run_isolated_flux_phase", fake_phase)
    result = flux_worker.infer({
        "parts_json": plan, "image_path": str(input_image),
        "output_dir": str(tmp_path / "repaired"),
    })
    assert calls == ["flux_latent_worker.py", "flux_decode_worker.py"]
    finished = PartsDocument.read(result["parts_json"])
    after = np.asarray(Image.open(finished.parts[0].rgba_png).convert("RGBA"))
    assert (after[17, 24] == [200, 80, 40, 255]).all()
    assert (after[24, 24] == [10, 30, 50, 255]).all()
    report = json.loads((tmp_path / "repaired" /
                         "occlusion_repair_report.json").read_text())
    assert report["decode_mode"] == "isolated-tiled-VAE-after-denoiser-exit"
