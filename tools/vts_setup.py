"""Explicit Colab cell-3 setup for the optional GPU VTS artwork tools.

No model installation is triggered during production. Fail closed and retain
stdout/stderr in full, with explicit process wall-timeouts.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

SEE_THROUGH_SHA = "df019de5129d6c4b406587a14c3501669441a783"
STABLE_LAYERS_SHA = "b826314b34b12d7c7cce9f0de7f49a330bd8e011"
ROOT = Path("/content/vtuber_builder/third_party")
TIMEOUT = 5400

def checked(args, *, cwd=None, timeout=TIMEOUT, env=None):
    print("[VTS setup]", " ".join(map(str,args)), flush=True)
    proc = subprocess.Popen(list(map(str,args)), cwd=cwd, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, bufsize=1)
    begin = time.monotonic()
    try:
        for line in proc.stdout:
            print(line, end="", flush=True)
            if time.monotonic() - begin > timeout:
                raise TimeoutError(f"Command timed out after {timeout}s")
        code = proc.wait(timeout=10)
    except BaseException:
        proc.kill()
        proc.wait(timeout=20)
        raise
    if code:
        raise RuntimeError(f"Command failed exit={code}: {args}")
    return proc


def checkout(url: str, dest: Path, sha: str):
    if not (dest / ".git").exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        checked(["git", "clone", "--filter=blob:none", url, str(dest)], timeout=900)
    checked(["git", "fetch", "--depth", "1", "origin", sha], cwd=dest, timeout=900)
    checked(["git", "checkout", "--detach", sha], cwd=dest, timeout=120)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=dest,
                                     text=True, timeout=20).strip()
    if commit != sha:
        raise RuntimeError(f"Unpinned third-party checkout: {commit}")
    return dest


def prepare(*, qwen: bool = False, install: bool = True):
    from huggingface_hub import snapshot_download
    see = checkout("https://github.com/shitagaki-lab/see-through.git",
                   ROOT / "see-through", SEE_THROUGH_SHA)
    python = sys.executable
    if install:
        venv = ROOT / "see-through-venv"
        if not (venv / "bin/python").exists():
            checked([sys.executable, "-m", "venv", "--system-site-packages", str(venv)], timeout=120)
        python = str(venv / "bin/python")
        checked([python, "-m", "pip", "install", "--disable-pip-version-check",
                 "-r", str(see/"requirements.txt")], cwd=see, timeout=5400)
        checked([python, "-m", "pip", "install", "--disable-pip-version-check",
                 "-r", str(see/"requirements-inference-bnb.txt")], cwd=see, timeout=5400)
        checked([python, "-c", "import torch,bitsandbytes,psd_tools; "
                 "print('torch',torch.__version__,'bf16',torch.cuda.is_bf16_supported() "
                 "if torch.cuda.is_available() else 'cpu')"], timeout=120)
    # Pre-download the published NF4 weights that the V3 inference program requests.
    weights = [
        "24yearsold/seethroughv0.0.2_layerdiff3d_nf4",
        "24yearsold/seethroughv0.0.1_marigold_nf4",
        "24yearsold/l2d_sam_iter2",
        "facebook/sam2.1-hiera-large",
    ]
    if qwen:
        checkout("https://github.com/Stability-AI/Stable-Layers.git",
                 ROOT / "Stable-Layers", STABLE_LAYERS_SHA)
        if install:
            checked([python, "-m", "pip", "install", "--disable-pip-version-check",
                     "peft", "accelerate", "bitsandbytes"], timeout=3600)
        weights.extend([
            "OzzyGT/qwen-image-layered-bnb-4bit-transformer",
            "StabilityLabs/Stable-Layers",
        ])
        # Official non-transformer auxiliary components are required in addition
        # to the 4-bit transformer; avoid downloading the full BF16 transformer.
        weights.append("Qwen/Qwen-Image-Layered")
    manifests=[]
    for model in weights:
        print(f"[VTS model download] {model}",flush=True)
        kw = {}
        if model == "Qwen/Qwen-Image-Layered":
            kw["ignore_patterns"] = ["transformer/*.safetensors",
                                     "transformer/diffusion_pytorch_model*"]
        loc = snapshot_download(repo_id=model, **kw)
        manifests.append({"model":model,"snapshot":str(loc)})
    output=ROOT/"vts_setup_manifest.json"
    output.write_text(json.dumps({
        "see_through_revision": SEE_THROUGH_SHA,
        "stable_layers_revision": STABLE_LAYERS_SHA if qwen else None,
        "see_through_python": python,
        "qwen_weights_prefetched": qwen,
        "snapshots":manifests,
        "gpu_inference_verified": False,
    },ensure_ascii=False,indent=2),encoding="utf-8")
    return output


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--with-qwen",action="store_true")
    ap.add_argument("--skip-install",action="store_true")
    a=ap.parse_args()
    print(prepare(qwen=a.with_qwen,install=not a.skip_install))


if __name__=="__main__":
    main()
