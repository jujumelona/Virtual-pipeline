"""FLUX.2 Klein denoising phase; outputs latents only and exits to free weights.

VAE decoding is intentionally moved to flux_decode_worker.py after this
process is gone, avoiding a RAM/VRAM peak at the final 4/4 diffusion step.
"""
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from flux_worker import PROMPT, prepare_masked_edit, memory_snapshot


def run(plan_file: str, manifest_file: str) -> None:
    from _entry import require_cuda
    require_cuda()
    import torch
    from PIL import Image
    from diffusers import Flux2KleinPipeline
    from safetensors.torch import save_file
    from vtuber_pipeline.common.model_assets import resolve_snapshot
    from tools.vts_quantization import select_compute_dtype

    plan = json.loads(Path(plan_file).read_text(encoding="utf-8"))
    work = Path(manifest_file).parent
    rows = plan["repairs"]
    if not rows:
        raise ValueError("FLUX denoise plan has no hidden holes")
    snapshot = resolve_snapshot("flux2_klein_4b")
    dtype = select_compute_dtype(torch)
    memory_snapshot("before_denoise_checkpoint_load")
    pipe = Flux2KleinPipeline.from_pretrained(
        snapshot, torch_dtype=dtype, low_cpu_mem_usage=True,
    )
    pipe.enable_model_cpu_offload()
    memory_snapshot("after_denoise_checkpoint_load")
    original = Image.open(plan["image_path"]).convert("RGB")
    produced = []

    for item in rows:
        mask = Image.open(item["mask_png"]).convert("L")
        marked, box = prepare_masked_edit(original, mask)
        prompt = PROMPT + (
            f" Target layer: {item['semantic_id']}. "
            "Restore the gray missing region only."
        )
        index = int(item["index"])
        memory_snapshot(f"before_denoise_part_{index}")

        def _step(_pipeline, step, timestep, kwargs):
            if step == 3:
                memory_snapshot(f"after_final_denoise_step_part_{index}")
            return kwargs

        with torch.inference_mode():
            latents = pipe(
                image=marked, prompt=prompt, num_inference_steps=4,
                guidance_scale=1.0, width=marked.width, height=marked.height,
                output_type="latent", callback_on_step_end=_step,
            ).images
        if not isinstance(latents, torch.Tensor) or latents.ndim != 4:
            raise RuntimeError(
                f"FLUX2 latent output contract broken: "
                f"{type(latents).__name__}, ndim={getattr(latents, 'ndim', None)}"
            )
        latent_file = work / f"flux_latent_{index:03d}.safetensors"
        save_file({"latents": latents.detach().to("cpu").contiguous()},
                  str(latent_file))
        produced.append({
            "index": index, "semantic_id": item["semantic_id"],
            "latent_path": str(latent_file), "box": list(box),
            "input_wh": list(marked.size),
        })
        memory_snapshot(f"after_latent_save_part_{index}")
    manifest = Path(manifest_file)
    tmp = manifest.with_suffix(".tmp")
    tmp.write_text(json.dumps({"repairs": produced},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(manifest)
    print("[flux-phase] denoising finished; process exiting before VAE decode",
          flush=True)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: flux_latent_worker.py plan.json latents.json")
    run(sys.argv[1], sys.argv[2])
