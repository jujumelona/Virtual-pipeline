"""Validate public request and worker boundaries before any expensive model call."""
from pathlib import Path
import sys
from types import SimpleNamespace
import pytest
from PIL import Image
from tools import vts_production as production


@pytest.mark.parametrize("layers,passes", [(1, 8), (11, 8), (6, -1), (6, 13)])
def test_bad_recursion_budget_rejected_before_decomposition(tmp_path, monkeypatch, layers, passes):
    master = tmp_path / "master.png"
    Image.new("RGBA", (256, 384)).save(master)
    monkeypatch.setattr(production, "run_see_through",
                        lambda *a, **kw: pytest.fail("invalid request reached model inference"))
    with pytest.raises(ValueError, match="Qwen"):
        production.make_cubism_handoff(master, tmp_path / "out", edition="free", scope="upper",
                                       qwen_layers=layers, qwen_passes=passes)
    assert not (tmp_path / "out").exists()


def test_see_through_relative_paths_survive_worker_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = Path("master.png"); Image.new("RGBA", (256, 384)).save(source)
    repo = Path("see")
    scripts = repo / "inference/scripts"; scripts.mkdir(parents=True)
    script = scripts / "inference_psd_quantized.py"
    script.write_text("# " + "torch.bfloat16 " * 8 + '''
import argparse
import sys
from pathlib import Path
def unused_pinned_cache_contract():
        pipeline.cache_tag_embeds()
        pipeline.cache_tag_embeds()
        marigold_pipe.cache_tag_embeds()
        marigold_pipe.cache_tag_embeds()
def unused_layerdiff_pass_boundaries():
    pipeline(
        group_index=0
    )
    pipeline(
        group_index=1
    )
def unused_offload_rng_contract():
    return torch.Generator(device=pipeline.unet.device)
def unused_nf4_marigold_branch():
        marigold_pipe.vae.to(device='cuda')
        marigold_pipe.unet.to(device='cuda')
        # Text encoder may be quantized (from pre-quantized repo) — only move device, not dtype
        if not getattr(marigold_pipe.text_encoder, 'is_quantized', False) and \\
           not getattr(marigold_pipe.text_encoder, 'quantization_method', None):
            marigold_pipe.text_encoder.to(device='cuda')
        if getattr(args, 'group_offload', False):
            marigold_pipe.enable_group_offload('cuda', num_blocks_per_group=1)
p=argparse.ArgumentParser(); p.add_argument('--srcp'); p.add_argument('--save_dir')
a, _=p.parse_known_args()
assert '--cpu_offload' in sys.argv, 'T4 must use model CPU offload'
assert Path(a.srcp).is_file()
folder=Path(a.save_dir); folder.mkdir(parents=True, exist_ok=True)
(folder/(Path(a.srcp).stem+'.psd')).write_bytes(b'8BPS CPU wrapper fixture')
print('CPU wrapper fixture completed')
''')
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(cuda=SimpleNamespace(
        is_available=lambda: True, get_device_capability=lambda *a: (7, 5))))
    monkeypatch.setattr(production, "_safe_refine_psd", lambda src, **kw: src)
    result = production.run_see_through(source, Path("out"), third_party=repo, timeout=20)
    assert result.is_absolute() and result.is_file()
    assert result.read_bytes().startswith(b"8BPS")
    assert (Path("out") / "see_through_full.log").read_text().strip() == "CPU wrapper fixture completed"
    # T4 always requests real component offload, not only an FP16 dtype edit.
    patched = (repo / "inference/scripts/inference_psd_quantized_vts_fp16.py").read_text()
    assert 'if args.cpu_offload:' in patched
    assert "Marigold NF4: GPU/group offload" in patched
    # Never call unsupported custom Marigold CPU offload in its NF4 branch.
    assert "marigold_pipe.enable_model_cpu_offload()" not in patched.split(
        "# NF4: load from pre-quantized repo (auto-selected by REPO_MAP)", 2)[-1].split(
        "return marigold_pipe", 1)[0]
    assert patched.count("align_offload_prompt_encoder_device(pipeline, 'layerdiff')") == 2
    assert patched.count("align_offload_prompt_encoder_device(marigold_pipe, 'marigold')") == 0
    assert "device = self._execution_device" in patched
    assert "text_inputs.input_ids.to(self._execution_device)" in patched
    assert "torch.Generator(device=pipeline._execution_device)" in patched
    assert patched.count("align_offload_image_devices(pipeline, 'layerdiff')") == 2
    assert patched.count("align_offload_image_devices(marigold_pipe, 'marigold')") == 0
    assert patched.count("            align_offloaded_transparent_decoder(pipeline)") == 2
    assert patched.count("pipeline.trans_vae.decoder.cpu()") == 2


def test_non_srgb_profile_is_rejected_before_model_inference(tmp_path, monkeypatch):
    from PIL import ImageCms
    master = tmp_path / 'non_srgb.png'
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile('LAB')).tobytes()
    Image.new('RGB', (256, 384)).save(master, icc_profile=profile)
    monkeypatch.setattr(production, 'run_see_through', lambda *a, **k: pytest.fail('model called'))
    with pytest.raises(ValueError, match='sRGB'):
        production.make_cubism_handoff(master, tmp_path / 'out', edition='free', scope='upper')
    assert not (tmp_path / 'out').exists()


def test_valid_srgb_profile_retains_original_dimensions(tmp_path):
    from PIL import Image, ImageCms
    from tools.vts_production import _image
    path = tmp_path / "srgb.png"
    Image.new("RGBA", (256, 384), (15, 80, 120, 128)).save(path,
        icc_profile=ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes())
    assert _image(path) == (256, 384)
