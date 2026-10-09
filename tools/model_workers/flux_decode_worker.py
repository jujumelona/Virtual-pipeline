"""Decode FLUX.2 Klein latents only AFTER the denoiser process has exited."""
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from flux_worker import configure_low_memory_decode, memory_snapshot


def run(latents_manifest: str, outputs_manifest: str) -> None:
    from _entry import require_cuda
    require_cuda()
    import torch
    from diffusers.models.autoencoders.autoencoder_kl_flux2 import AutoencoderKLFlux2
    from diffusers.pipelines.flux2.image_processor import Flux2ImageProcessor
    from safetensors.torch import load_file
    from vtuber_pipeline.common.model_assets import resolve_snapshot
    from tools.vts_quantization import select_compute_dtype

    items = json.loads(Path(latents_manifest).read_text(encoding="utf-8"))["repairs"]
    if not items:
        raise ValueError("FLUX VAE decode manifest contains no latents")
    snapshot = resolve_snapshot("flux2_klein_4b")
    dtype = select_compute_dtype(torch)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    memory_snapshot("before_vae_only_checkpoint_load")
    vae = AutoencoderKLFlux2.from_pretrained(
        snapshot, subfolder="vae", torch_dtype=dtype, low_cpu_mem_usage=True,
    )
    configure_low_memory_decode(type("Pipeline", (), {"vae": vae})())
    vae = vae.to(device).eval()
    scale = 2 ** (len(vae.config.block_out_channels) - 1) * 2
    processor = Flux2ImageProcessor(vae_scale_factor=scale)
    memory_snapshot("after_vae_only_checkpoint_load")
    work = Path(outputs_manifest).parent
    results = []

    for item in items:
        index = int(item["index"])
        tensors = load_file(item["latent_path"], device="cpu")
        latents = tensors["latents"]
        if latents.ndim != 4 or latents.shape[0] != 1:
            raise ValueError(f"FLUX latent shape invalid for part {index}: "
                             f"{tuple(latents.shape)}")
        memory_snapshot(f"before_vae_only_decode_part_{index}")
        with torch.inference_mode():
            pixels = vae.decode(latents.to(device=device, dtype=dtype),
                                return_dict=False)[0]
            images = processor.postprocess(pixels, output_type="pil")
        if len(images) != 1:
            raise RuntimeError(f"FLUX VAE produced {len(images)} images, expected one")
        edited = images[0].convert("RGB")
        expected = tuple(item["input_wh"])
        if edited.size != expected:
            raise RuntimeError(
                f"FLUX VAE output shape mismatch: {edited.size} expected {expected}"
            )
        destination = work / f"flux_decoded_{index:03d}.png"
        edited.save(destination)
        results.append({
            "index": index, "semantic_id": item["semantic_id"],
            "decoded_png": str(destination), "box": item["box"],
            "input_wh": item["input_wh"],
        })
        del pixels, latents, tensors, images
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        memory_snapshot(f"after_vae_only_decode_part_{index}")

    manifest = Path(outputs_manifest)
    tmp = manifest.with_suffix(".tmp")
    tmp.write_text(json.dumps({"repairs": results}, ensure_ascii=False,
                              indent=2), encoding="utf-8")
    tmp.replace(manifest)
    print("[flux-phase] VAE-only decoding finished; process exiting", flush=True)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: flux_decode_worker.py latents.json outputs.json")
    run(sys.argv[1], sys.argv[2])
