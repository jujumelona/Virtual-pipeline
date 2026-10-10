"""Execute the inference wrapper with a CPU worker; no GPU quality claim."""
from pathlib import Path
import sys
import types
from PIL import Image
import pytest

from tools import vts_qwen_refine as qwen


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repo = tmp_path / "third/Stable-Layers"
    repo.mkdir(parents=True)
    (repo / "decompose.py").write_text("pinned source checked separately")
    snapshot = tmp_path / "snapshot"
    (snapshot / "model").mkdir(parents=True)
    (snapshot / "model/adapter_model.safetensors").write_bytes(b"fixture")
    monkeypatch.setitem(sys.modules, "huggingface_hub", types.SimpleNamespace(
        snapshot_download=lambda *a, **kw: str(snapshot)))
    Image.new("RGBA", (64, 96), (50, 60, 70, 255)).save("input.png")
    return repo


def worker_source(write_layers=True, size=(432, 640), require_prepared=False):
    return '''import argparse
from pathlib import Path
from PIL import Image
p=argparse.ArgumentParser()
p.add_argument('--input'); p.add_argument('--output'); p.add_argument('--num-layers', type=int)
a, _=p.parse_known_args()
folder=Path(a.output)/Path(a.input).stem
folder.mkdir(parents=True, exist_ok=True)
print('CPU wrapper fixture completed')
''' + (f"assert Image.open(a.input).size == {size!r}, 'inference input not prepared'\n"
       if require_prepared else "") + (f'''for i in range(a.num_layers):
    Image.new('RGBA', {size!r}, (50,60,70,255)).save(folder/f'layer_{{i}}.png')
''' if write_layers else "")


def test_relative_runtime_paths_survive_worker_cwd(runtime, monkeypatch):
    monkeypatch.setattr(qwen, "_patch_pinned_official", lambda *a, **kw: worker_source())
    result = qwen.infer(Path("input.png"), Path("output"), third_party=Path("third"),
                        layer_count=3, timeout=20)
    assert result["layer_count"] == 3
    assert all(Path(p).is_absolute() and Path(p).is_file() for p in result["layers"])
    assert Path(result["log"]).read_text().strip() == "CPU wrapper fixture completed"


def test_successful_worker_cannot_reuse_stale_candidate_pngs(runtime, monkeypatch):
    monkeypatch.setattr(qwen, "_patch_pinned_official", lambda *a, **kw: worker_source(False))
    output = Path("output").resolve()
    stale = output / "qwen_layers/input"
    stale.mkdir(parents=True)
    for i in range(3):
        Image.new("RGBA", (64, 96)).save(stale / f"layer_{i}.png")
    with pytest.raises(RuntimeError, match="didn't provide"):
        qwen.infer(Path("input.png").resolve(), output, third_party=runtime.parent,
                   layer_count=3, timeout=20)


def test_successful_worker_must_emit_official_resized_dimensions(runtime, monkeypatch):
    monkeypatch.setattr(qwen, "_patch_pinned_official",
                        lambda *a, **kw: worker_source(size=(64, 96)))
    with pytest.raises(ValueError, match="dimensions"):
        qwen.infer(Path("input.png"), Path("output"), third_party=runtime.parent,
                   timeout=20)


@pytest.mark.parametrize("original_size,expected", [
    ((64, 96), (432, 640)), ((96, 64), (640, 432)), ((4, 100), (32, 640)),
])
def test_model_receives_prepared_official_canvas_without_changing_original(
    runtime, monkeypatch, original_size, expected,
):
    Image.new("RGBA", original_size, (50, 60, 70, 128)).save("input.png")
    original = Path("input.png").read_bytes()
    monkeypatch.setattr(qwen, "_patch_pinned_official",
                        lambda *a, **kw: worker_source(size=expected, require_prepared=True))
    result = qwen.infer(Path("input.png"), Path("output"), third_party=runtime.parent,
                        timeout=20)
    assert result["candidate_canvas"] == list(expected)
    assert result["source_canvas"] == list(original_size)
    assert Path("input.png").read_bytes() == original


def test_pinned_qwen_worker_stages_encoder_before_transformer():
    """Enforce staged VRAM residency rather than two 4-bit models together."""
    from tools.vts_qwen_refine import _patch_pinned_official
    code = (
        "import torch\n"
        "    from diffusers import DiffusionPipeline\n\n"
        "    pipe = DiffusionPipeline.from_pretrained(\n"
        "        args.base_model, torch_dtype=torch.bfloat16,\n"
        "        trust_remote_code=True, cache_dir=args.cache_dir,\n"
        "    )\n"
        "    transformer = pipe.transformer.to(device).eval()\n"
        "    vae = pipe.vae.to(device).eval()\n"
        "    scheduler = pipe.scheduler\n"
        "    tokenizer = getattr(pipe, \"tokenizer\", None)\n"
        "    text_encoder = getattr(pipe, \"text_encoder\", None)\n"
        "    del pipe\n"
        "    transformer.requires_grad_(False)\n"
        "    vae.requires_grad_(False)\n"
        "    transformer = PeftModel.from_pretrained(transformer, args.lora)\n"
        "    # --- prompt encoding -------------------------------------------------\n"
        "    text_encoder = text_encoder.to(device).eval()\n"
        "    prompt_embeds, prompt_mask = encode_prompt(args.prompt)\n"
        "    neg_embeds, neg_mask = encode_prompt('')\n"
        "    # scheduler may or may not accept sigmas/mu\n"
        "    img_t = img_t.unsqueeze(0).to(device)\n"
        "    condition_latents = encode_condition_image(vae, img_t)\n"
        "    decoded = vae.decode(layer_latents.reshape(b * num_layers, c, 1, h, w).to(dtype=vae.dtype),\n"
        "                         return_dict=False)[0]\n"
        "    decoded = decode_layers(vae, latents, th, tw, args.num_layers)\n"
    )
    patched = _patch_pinned_official(
        code, quant_dir="/tmp/quant", lora_dir="/tmp/adapter")
    assert patched.count("scheduler = pipe.scheduler") == 1
    assert "getattr(pipe, \"text_encoder\"" not in patched
    assert "getattr(pipe, \"tokenizer\"" not in patched
    assert "load_in_4bit=True" in patched
    assert patched.index("prompt_embeds, prompt_mask") < patched.index(
        "del text_encoder") < patched.index(
        "QwenImageTransformer2DModel.from_pretrained")
    assert 'device_map={"": "cuda:0"}' in patched
    assert "text_encoder=None" in patched
    assert "for i in range(packed.shape[0])" in patched
    assert "vae.decode(packed[i:i+1]" in patched
    assert "layer_latents.reshape(b * num_layers, c, 1, h, w).to(dtype=vae.dtype)" not in patched
    assert "encode_condition_image(vae, img_t).to(device)" in patched
    assert "decode_layers(vae, latents.to('cpu')" in patched
    assert "text_encoder = text_encoder.to(device).eval()" not in patched


def test_sigkill_keeps_memory_and_log_diagnostics(runtime, monkeypatch):
    import json
    from tools import vts_subprocess
    monkeypatch.setattr(qwen, "_patch_pinned_official", lambda *a, **kw: worker_source())
    def killed(*args, **kwargs):
        Path(kwargs["log_path"]).write_text("Loading base model: fixture\n", encoding="utf-8")
        return -9
    monkeypatch.setattr(vts_subprocess, "run_logged", killed)
    with pytest.raises(RuntimeError, match="exited -9; diagnostics="):
        qwen.infer(Path("input.png"), Path("output"), third_party=runtime.parent, timeout=20)
    evidence = json.loads(Path("output/qwen_failure.json").read_text(encoding="utf-8"))
    assert evidence["returncode"] == -9
    assert evidence["signal"] == "SIGKILL"
    assert "memory_before" in evidence and "memory_after" in evidence
    assert "Loading base model" in evidence["log_tail"]


def test_generated_qwen_preflight_rejects_stale_refs(tmp_path, monkeypatch):
    source = tmp_path / "decompose.py"
    source.write_text("# pinned source fixture", encoding="utf-8")
    valid = (
        "def main():\\n"
        "    text_encoder = object()\\n"
        "    del text_encoder\\n"
        "    pipe = object()\\n"
        "    scheduler = pipe\\n"
        "    del pipe\\n"
        "    return scheduler\\n"
    )
    monkeypatch.setattr(qwen, "_patch_pinned_official", lambda *args, **kw: valid)
    status = qwen.validate_qwen_runtime_source(source)
    assert status["syntax"] == "PASS"
    assert status["deleted_reference_check"] == "PASS"
    assert status["gpu_inference_verified"] is False
    monkeypatch.setattr(qwen, "_patch_pinned_official",
                        lambda *args, **kw: valid.replace(
                            "    return scheduler", "    return pipe.scheduler"))
    with pytest.raises(RuntimeError, match="reads deleted pipe"):
        qwen.validate_qwen_runtime_source(source)
    monkeypatch.setattr(qwen, "_patch_pinned_official",
                        lambda *args, **kw: "def main(:\\n    pass\\n")
    with pytest.raises(SyntaxError):
        qwen.validate_qwen_runtime_source(source)
