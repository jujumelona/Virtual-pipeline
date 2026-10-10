"""Pinned Stable-Layers LoRA inference using a 4-bit Qwen-Image-Layered transformer.

The upstream inference script defaults to full-BF16, which cannot be
executed on NVIDIA T4. We adapt only its *loading/compute dtype* with explicit
assertions against the pinned source bytes, never silently substituting another
model or different LoRA. Keep each run's native RGBA layers and log.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

DEFAULT_ROOT=Path("/content/vtuber_builder/third_party")
BASE="Qwen/Qwen-Image-Layered"
QUANT="OzzyGT/qwen-image-layered-bnb-4bit-transformer"
ADAPTER="StabilityLabs/Stable-Layers"

def _patch_pinned_official(code: str, *, quant_dir: str, lora_dir: str) -> str:
    before="""    from diffusers import DiffusionPipeline

    pipe = DiffusionPipeline.from_pretrained(
        args.base_model, torch_dtype=torch.bfloat16,
        trust_remote_code=True, cache_dir=args.cache_dir,
    )
    transformer = pipe.transformer.to(device).eval()
    vae = pipe.vae.to(device).eval()"""
    after="""    from diffusers import DiffusionPipeline, QwenImageTransformer2DModel
    from transformers import AutoTokenizer, BitsAndBytesConfig, Qwen2_5_VLForConditionalGeneration
    import gc

    # Encode prompts first, then free the 4-bit VL encoder before loading
    # the NF4 image transformer. 16 GiB cannot hold both simultaneously.
    tokenizer = AutoTokenizer.from_pretrained(
        os.path.join(args.base_model, "tokenizer"),
        local_files_only=True, trust_remote_code=True,
    )
    text_encoder = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        os.path.join(args.base_model, "text_encoder"),
        torch_dtype=runtime_dtype,
        quantization_config=BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=runtime_dtype,
        ),
        device_map={"": "cuda:0"}, low_cpu_mem_usage=True,
    ).eval()
    print("[VTS QWEN] prompt encoding stage", flush=True)
    # __VTS_PROMPT_PRECOMPUTE__
    del text_encoder
    gc.collect()
    torch.cuda.empty_cache()
    print("[VTS QWEN] VL encoder released before transformer loading", flush=True)
    transformer_q4 = QwenImageTransformer2DModel.from_pretrained(
        """ + repr(quant_dir) + """, torch_dtype=runtime_dtype,
        device_map={"": "cuda:0"},
    )
    pipe = DiffusionPipeline.from_pretrained(
        args.base_model, torch_dtype=runtime_dtype,
        transformer=transformer_q4, text_encoder=None, tokenizer=None,
        trust_remote_code=True, cache_dir=args.cache_dir,
    )
    transformer = pipe.transformer.eval()
    set_4bit_compute_dtype(transformer, runtime_dtype)
    vae = pipe.vae.eval()  # CPU: avoid competing with the NF4 transformer"""
    if code.count(before)!=1:
        raise RuntimeError("Stable-Layers upstream model loader changed: refuse unverified patch")
    code=code.replace(before,after)
    from inspect import getsource
    from tools.vts_quantization import set_4bit_compute_dtype, select_compute_dtype
    # Move upstream prompt encoding in front of transformer construction.
    first = "    # --- prompt encoding -------------------------------------------------"
    last = "    # scheduler may or may not accept sigmas/mu"
    if code.count(first) != 1 or code.count(last) != 1:
        raise RuntimeError("Stable-Layers prompt block changed: cannot stage offload")
    prefix, rest = code.split(first, 1)
    prompt, suffix = rest.split(last, 1)
    prompt = first + prompt
    if prompt.count("    text_encoder = text_encoder.to(device).eval()") != 1:
        raise RuntimeError("Stable-Layers encoder transfer changed")
    prompt = prompt.replace("    text_encoder = text_encoder.to(device).eval()\\n", "")
    if code.count("    # __VTS_PROMPT_PRECOMPUTE__") != 1:
        raise RuntimeError("Missing prompt precompute boundary")
    code = (prefix + last + suffix).replace(
        "    # __VTS_PROMPT_PRECOMPUTE__", prompt)
    # Quantized transformer stays on GPU while VAE runs on CPU.
    for original, staged in (
        ("    img_t = img_t.unsqueeze(0).to(device)\\n",
         "    img_t = img_t.unsqueeze(0).to('cpu')\\n"),
        ("    condition_latents = encode_condition_image(vae, img_t)\\n",
         "    condition_latents = encode_condition_image(vae, img_t).to(device)\\n"),
        ("    decoded = decode_layers(vae, latents, th, tw, args.num_layers)\\n",
         "    decoded = decode_layers(vae, latents.to('cpu'), th, tw, args.num_layers)\\n"),
    ):
        if code.count(original) != 1:
            raise RuntimeError("Stable-Layers VAE CPU execution contract changed")
        code = code.replace(original, staged)
    # T4 has native fp16 and no native BF16. Preserve the Heun denoiser and
    # trained LoRA, but make all generated latent/embedding dtypes float16.
    code=code.replace('torch.bfloat16','runtime_dtype')
    if code.count('torch.bfloat16'):
        raise RuntimeError("BF16 GPU operation remains")
    if code.count('import torch\n') != 1:
        raise RuntimeError("Stable-Layers dtype initialization contract changed")
    code = code.replace('import torch\n', 'import torch\nruntime_dtype = select_compute_dtype(torch)\n')
    code = getsource(set_4bit_compute_dtype) + "\n" + getsource(select_compute_dtype) + "\n" + code
    if code.count('transformer = PeftModel.from_pretrained(transformer, args.lora)')!=1:
        raise RuntimeError("Stable-Layers upstream LoRA attachment changed")
    if lora_dir not in code:
        # CLI --lora sets actual loaded adapter, no hardcoded substitution.
        pass
    return code


def infer(input_image: Path, output_dir: Path, *, third_party: Path = DEFAULT_ROOT,
          timeout: int = 9000, python: str | None = None,
          layer_count: int = 4) -> dict:
    if not 2 <= layer_count <= 10:
        raise ValueError("Qwen per-pass layer count must be between 2 and 10")
    from huggingface_hub import snapshot_download
    from PIL import Image
    input_image = input_image.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    third_party = third_party.expanduser().resolve()
    if not input_image.is_file():
        raise FileNotFoundError(input_image)
    script=third_party/"Stable-Layers"/"decompose.py"
    if not script.is_file():
        raise RuntimeError("Stable-Layers pinned source absent: run model setup cell ③")
    output_dir.mkdir(parents=True,exist_ok=True)
    # Prepare the model canvas before loading models. This is the pinned
    # official compute_aspect_resize + RGB/LANCZOS preprocessing, not a
    # corrective stretch of generated layers. Retain original artwork.
    with Image.open(input_image) as source_image:
        source_image.load()
        ow, oh = source_image.size
        scale = 640 / max(ow, oh)
        expected_size = tuple(max(int(round(dim * scale / 16)) * 16, 16)
                              for dim in (ow, oh))
        prepared = source_image.convert("RGB").resize(expected_size, Image.Resampling.LANCZOS)
    prepared_input = output_dir / "qwen_input" / (input_image.stem + ".png")
    prepared_input.parent.mkdir(parents=True, exist_ok=True)
    prepared.save(prepared_input)
    quant_path=Path(snapshot_download(QUANT,local_files_only=True))
    lora_path=Path(snapshot_download(ADAPTER,local_files_only=True))/"model"
    base_path=Path(snapshot_download(BASE,local_files_only=True))
    if not (lora_path/"adapter_model.safetensors").is_file():
        raise FileNotFoundError("Stable-Layers adapter was not prepared in cell ③")
    patched=output_dir/"stable_layers_qwen_nf4_runtime.py"
    patched.write_text(_patch_pinned_official(
        script.read_text(encoding="utf-8"),
        quant_dir=str(quant_path),lora_dir=str(lora_path)),encoding="utf-8")
    # Keep previous runs for inspection; only this fresh directory can
    # satisfy the current worker's output contract.
    candidate_root = output_dir / "qwen_layers" / ("run_" + uuid.uuid4().hex)
    cmd=[
        python or sys.executable, "-u", str(patched),
        "--input",str(prepared_input),"--output",str(candidate_root),
        "--base-model",str(base_path),"--lora",str(lora_path),
        "--steps","50","--guidance-scale","1.0","--num-layers",str(layer_count),
        "--size","640","--transparent","--device","cuda",
    ]
    log=output_dir/"stable_layers_full.log"
    runtime_env=os.environ.copy()
    runtime_env["HF_HUB_OFFLINE"]="1"
    runtime_env["TRANSFORMERS_OFFLINE"]="1"
    from tools.vts_subprocess import run_logged
    from tools.colab_gpu_warmup import available_face_worker, stop_face_worker
    from vtuber_pipeline.common.stage_runner import _process_gpu_lock
    # Qwen is launched directly, outside run_stage(); the resident face
    # prewarm must exit before this GPU stage acquires the same lock.
    if available_face_worker():
        stop_face_worker()
    from tools.vts_handoff_process import memory_snapshot
    before_memory = memory_snapshot()
    with _process_gpu_lock(timeout_sec=timeout):
        exitcode=run_logged(cmd,cwd=third_party/"Stable-Layers",env=runtime_env,
                            log_path=log,timeout_seconds=timeout)
    if exitcode:
        after_memory = memory_snapshot()
        diagnostic = {
            "event": "VTS_QWEN_WORKER_FAILED",
            "returncode": exitcode,
            "signal": "SIGKILL" if exitcode == -9 else None,
            "memory_before": before_memory,
            "memory_after": after_memory,
            "log_path": str(log),
            "log_tail": log.read_text(encoding="utf-8", errors="replace")[-6000:]
                if log.is_file() else "",
            "note": "SIGKILL may be memory pressure; inspect memory.events "
                    "oom_kill and CUDA allocation logs before classifying cause.",
        }
        details_path = output_dir / "qwen_failure.json"
        details_path.write_text(json.dumps(diagnostic, indent=2), encoding="utf-8")
        print("[VTS QWEN FAILURE] " + json.dumps(diagnostic), flush=True)
        raise RuntimeError(
            f"Qwen NF4/Stable-Layers exited {exitcode}; "
            f"diagnostics={details_path}; log={log}")
    folder=candidate_root/input_image.stem
    produced=[folder/f"layer_{i}.png" for i in range(layer_count)]
    if not all(f.is_file() for f in produced):
        raise RuntimeError(f"Qwen reported success but didn't provide {layer_count} RGBA layers")
    for f in produced:
        with Image.open(f) as im:
            im.load()
            if im.mode!="RGBA":raise ValueError(f"Not an RGBA layer: {f}")
            if im.size != expected_size:
                raise ValueError(f"Stable-Layers output dimensions {im.size} differ "
                                 f"from official resize {expected_size}: {f}")
    result={"status":"complete_qwen_candidate_layers","quantized_transformer":QUANT,
            "lora":ADAPTER,"layers":[str(x) for x in produced],
            "layer_count":layer_count,
            "candidate_canvas":list(expected_size),
            "source_canvas":[ow, oh],
            "prepared_input":str(prepared_input),
            "settings":{"steps":50,"guidance_scale":1.0,"sampler":"heun",
                        "max_side":640,"dimension_multiple":16,"transparent":True,
                        "official_default_layers":4,"requested_layers":layer_count},
            "log":str(log),"not_cubism_artmeshes":True,
            "warning":f"These are {layer_count} candidate layers; Live2D semantic rigging accuracy not guaranteed."}
    (output_dir/"qwen_stage.json").write_text(
        json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    return result


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input",required=True,type=Path)
    ap.add_argument("--output",required=True,type=Path)
    ap.add_argument("--timeout",type=int,default=9000)
    args=ap.parse_args()
    result=infer(args.input,args.output,timeout=args.timeout)
    print(json.dumps(result,ensure_ascii=False))


if __name__=="__main__":
    main()
