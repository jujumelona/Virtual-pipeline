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

    transformer_q4 = QwenImageTransformer2DModel.from_pretrained(
        """ + repr(quant_dir) + """, torch_dtype=torch.float16, device_map="auto",
    )
    pipe = DiffusionPipeline.from_pretrained(
        args.base_model, torch_dtype=torch.float16,
        transformer=transformer_q4,
        trust_remote_code=True, cache_dir=args.cache_dir,
    )
    transformer = pipe.transformer.eval()
    vae = pipe.vae.to(device).eval()"""
    if code.count(before)!=1:
        raise RuntimeError("Stable-Layers upstream model loader changed: refuse unverified patch")
    code=code.replace(before,after)
    if code.count('text_encoder = text_encoder.to(device).eval()')!=1:
        raise RuntimeError("Stable-Layers text encoder binding changed")
    code=code.replace('text_encoder = text_encoder.to(device).eval()',
                      'text_encoder = text_encoder.to("cpu").eval()')
    # T4 has native fp16 and no native BF16. Preserve the Heun denoiser and
    # trained LoRA, but make all generated latent/embedding dtypes float16.
    code=code.replace('torch.bfloat16','torch.float16')
    if code.count('torch.bfloat16'):
        raise RuntimeError("BF16 GPU operation remains")
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
    if not input_image.is_file():
        raise FileNotFoundError(input_image)
    script=third_party/"Stable-Layers"/"decompose.py"
    if not script.is_file():
        raise RuntimeError("Stable-Layers pinned source absent: run model setup cell ③")
    output_dir.mkdir(parents=True,exist_ok=True)
    quant_path=Path(snapshot_download(QUANT,local_files_only=True))
    lora_path=Path(snapshot_download(ADAPTER,local_files_only=True))/"model"
    base_path=Path(snapshot_download(BASE,local_files_only=True))
    if not (lora_path/"adapter_model.safetensors").is_file():
        raise FileNotFoundError("Stable-Layers adapter was not prepared in cell ③")
    patched=output_dir/"stable_layers_qwen_nf4_runtime.py"
    patched.write_text(_patch_pinned_official(
        script.read_text(encoding="utf-8"),
        quant_dir=str(quant_path),lora_dir=str(lora_path)),encoding="utf-8")
    cmd=[
        python or sys.executable, "-u", str(patched),
        "--input",str(input_image.resolve()),"--output",str(output_dir/"qwen_layers"),
        "--base-model",str(base_path),"--lora",str(lora_path),
        "--steps","50","--guidance-scale","1.0","--num-layers",str(layer_count),
        "--size","640","--transparent","--device","cuda",
    ]
    log=output_dir/"stable_layers_full.log"
    runtime_env=os.environ.copy()
    runtime_env["HF_HUB_OFFLINE"]="1"
    runtime_env["TRANSFORMERS_OFFLINE"]="1"
    from tools.vts_subprocess import run_logged
    exitcode=run_logged(cmd,cwd=third_party/"Stable-Layers",env=runtime_env,
                        log_path=log,timeout_seconds=timeout)
    if exitcode:
        raise RuntimeError(f"Qwen NF4/Stable-Layers exited {exitcode}; log={log}")
    folder=output_dir/"qwen_layers"/input_image.stem
    produced=[folder/f"layer_{i}.png" for i in range(layer_count)]
    if not all(f.is_file() for f in produced):
        raise RuntimeError(f"Qwen reported success but didn't provide {layer_count} RGBA layers")
    for f in produced:
        with Image.open(f) as im:
            im.load()
            if im.mode!="RGBA":raise ValueError(f"Not an RGBA layer: {f}")
    result={"status":"complete_qwen_candidate_layers","quantized_transformer":QUANT,
            "lora":ADAPTER,"layers":[str(x) for x in produced],
            "layer_count":layer_count,
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
