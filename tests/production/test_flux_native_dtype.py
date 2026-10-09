"""Exercise both FLUX checkpoint loaders without GPU or model downloads."""
import json
import sys
import types

import pytest


@pytest.mark.parametrize("worker_name", ["flux_latent_worker", "flux_decode_worker"])
@pytest.mark.parametrize("capability,expected", [((7, 5), "fp16"), ((8, 0), "bf16")])
def test_flux_loader_requires_native_bf16(monkeypatch, tmp_path, worker_name,
                                         capability, expected):
    # PyTorch can report emulated BF16 as supported on T4. The checkpoint
    # loader must still receive FP16 there and preserve BF16 on Ampere.
    torch = types.SimpleNamespace(
        float16="fp16", bfloat16="bf16",
        cuda=types.SimpleNamespace(is_available=lambda: True,
                                  is_bf16_supported=lambda: True,
                                  get_device_capability=lambda: capability),
    )
    monkeypatch.setitem(sys.modules, "torch", torch)
    captured = {}

    class LoaderReached(Exception):
        pass

    class Loader:
        @staticmethod
        def from_pretrained(*args, **kwargs):
            captured.update(kwargs)
            raise LoaderReached

    monkeypatch.setitem(sys.modules, "diffusers", types.SimpleNamespace(
        Flux2KleinPipeline=Loader))
    monkeypatch.setitem(sys.modules,
                        "diffusers.models.autoencoders.autoencoder_kl_flux2",
                        types.SimpleNamespace(AutoencoderKLFlux2=Loader))
    monkeypatch.setitem(sys.modules, "diffusers.pipelines.flux2.image_processor",
                        types.SimpleNamespace(Flux2ImageProcessor=object))
    monkeypatch.setitem(sys.modules, "safetensors.torch", types.SimpleNamespace(
        save_file=lambda *args: None, load_file=lambda *args: None))
    from vtuber_pipeline.common import model_assets
    monkeypatch.setattr(model_assets, "resolve_snapshot", lambda _: "checkpoint")
    from tools.model_workers import flux_latent_worker, flux_decode_worker
    worker = {"flux_latent_worker": flux_latent_worker,
              "flux_decode_worker": flux_decode_worker}[worker_name]
    monkeypatch.setattr(worker, "memory_snapshot", lambda _: None)
    request = tmp_path / "request.json"
    request.write_text(json.dumps({"repairs": [{"index": 0}]}))
    with pytest.raises(LoaderReached):
        worker.run(str(request), str(tmp_path / "manifest.json"))
    assert captured["torch_dtype"] == expected


@pytest.mark.parametrize("worker_name", ["flux_latent_worker", "flux_decode_worker"])
def test_flux_phase_rejects_missing_required_cuda_before_loading(monkeypatch,
                                                               worker_name):
    monkeypatch.setenv("VTUBER_REQUIRE_CUDA", "1")
    monkeypatch.setitem(sys.modules, "torch", types.SimpleNamespace(
        cuda=types.SimpleNamespace(is_available=lambda: False)))
    from tools.model_workers import flux_latent_worker, flux_decode_worker
    worker = {"flux_latent_worker": flux_latent_worker,
              "flux_decode_worker": flux_decode_worker}[worker_name]
    with pytest.raises(RuntimeError, match="CUDA"):
        worker.run("unused-request.json", "unused-manifest.json")
