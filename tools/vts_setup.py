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
import uuid

SEE_THROUGH_SHA = "df019de5129d6c4b406587a14c3501669441a783"
STABLE_LAYERS_SHA = "b826314b34b12d7c7cce9f0de7f49a330bd8e011"
ROOT = Path("/content/vtuber_builder/third_party")
TIMEOUT = 5400

def checked(args, *, cwd=None, timeout=TIMEOUT, env=None):
    if __package__:
        from .vts_subprocess import run_logged
    else:
        from vts_subprocess import run_logged
    print("[VTS setup]", " ".join(map(str, args)), flush=True)
    log = ROOT / "setup_logs" / ("command_" + uuid.uuid4().hex + ".log")
    code = run_logged(args, cwd=cwd, env=env, log_path=log, timeout_seconds=timeout)
    if code:
        raise RuntimeError(f"Command failed exit={code}: {args}")
    return code


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


def download_snapshot(model: str, *, python: str, record_path: Path,
                      timeout: float = TIMEOUT, ignore_patterns=None) -> str:
    """Bound even silent HF downloads; only fresh records prove readiness."""
    if __package__:
        from .vts_subprocess import run_logged
    else:
        from vts_subprocess import run_logged
    record_path = record_path.resolve()
    record_path.parent.mkdir(parents=True, exist_ok=True)
    record_path.unlink(missing_ok=True)
    script = """import json, sys
from pathlib import Path
from huggingface_hub import snapshot_download
model, record, options = sys.argv[1:]
loc = snapshot_download(repo_id=model, **json.loads(options))
Path(record).write_text(json.dumps({'model': model, 'snapshot': loc}), encoding='utf-8')
print('Snapshot prepared:', model, flush=True)
"""
    options = {"ignore_patterns": ignore_patterns} if ignore_patterns else {}
    env = os.environ.copy()
    env["HF_HUB_DOWNLOAD_TIMEOUT"] = "60"
    env["HF_HUB_ETAG_TIMEOUT"] = "30"
    log = record_path.with_suffix(".log")
    code = run_logged([python, "-u", "-c", script, model, str(record_path),
                       json.dumps(options)], env=env, log_path=log,
                      timeout_seconds=timeout)
    if code != 0 or not record_path.is_file():
        raise RuntimeError(f"Model download failed: {model}; exit={code}; log={log}")
    data = json.loads(record_path.read_text(encoding="utf-8"))
    if data.get("model") != model or not data.get("snapshot"):
        raise RuntimeError(f"Invalid snapshot record: {model}; log={log}")
    return data["snapshot"]



def ensure_see_through_python(venv: Path) -> str:
    """Prepare a Colab worker venv without invoking unavailable ensurepip.

    Colab installs pip into its base Python, but its /usr/bin/python3
    ensurepip bootstrap is not guaranteed to work. A system-site-packages
    venv can use that existing pip while keeping worker upgrades local.
    Always check the interpreter as well as pip: a failed standard venv
    may leave bin/python behind and must never count as ready.
    """
    python = venv / "bin" / "python"
    config = venv / "pyvenv.cfg"
    inherited_sites = (
        config.is_file()
        and "include-system-site-packages = true" in
        config.read_text(encoding="utf-8").lower()
    )
    if not python.is_file() or not inherited_sites:
        checked([sys.executable, "-m", "venv", "--without-pip",
                 "--system-site-packages", str(venv)], timeout=120)

    # pip must be importable from the worker interpreter and sys.prefix
    # must point to this exact venv, not silently fall back to base Python.
    check = (
        "import pathlib, pip, sys; "
        f"expected=pathlib.Path({str(venv)!r}).resolve(); "
        "actual=pathlib.Path(sys.prefix).resolve(); "
        "assert actual == expected, f'Not a worker venv: {actual} != {expected}'; "
        "print('[VTS setup] worker-venv-pip-ready', pip.__version__)"
    )
    checked([str(python), "-c", check], timeout=60)
    return str(python)


def prepare(*, qwen: bool = False, install: bool = True):
    ROOT.mkdir(parents=True, exist_ok=True)
    # An interrupted new preparation must not expose an old ready marker.
    output = ROOT / "vts_setup_manifest.json"
    output.unlink(missing_ok=True)
    see = checkout("https://github.com/shitagaki-lab/see-through.git",
                   ROOT / "see-through", SEE_THROUGH_SHA)
    python = sys.executable
    if install:
        venv = ROOT / "see-through-venv"
        python = ensure_see_through_python(venv)
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
    ]
    # Neither parser/SAM2 is called by the pinned quantized PSD entrypoint.
    # Prefetching them adds downloads without refining any output masks.
    if qwen:
        checkout("https://github.com/Stability-AI/Stable-Layers.git",
                 ROOT / "Stable-Layers", STABLE_LAYERS_SHA)
        if install:
            from tools.vts_qwen_refine import validate_qwen_runtime_source
            validate_qwen_runtime_source(ROOT / "Stable-Layers" / "decompose.py")
            print("[VTS setup] Qwen generated runtime preflight PASS", flush=True)
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
    for serial, model in enumerate(weights):
        print(f"[VTS model download] {model}",flush=True)
        kw = {}
        if model == "Qwen/Qwen-Image-Layered":
            kw["ignore_patterns"] = ["transformer/*.safetensors",
                                     "transformer/diffusion_pytorch_model*"]
        loc = download_snapshot(model, python=python,
                                record_path=ROOT / "setup_logs" / f"snapshot_{serial:02d}.json",
                                **kw)
        manifests.append({"model":model,"snapshot":str(loc)})
    temporary = output.with_suffix(".tmp")
    temporary.write_text(json.dumps({
        "see_through_revision": SEE_THROUGH_SHA,
        "stable_layers_revision": STABLE_LAYERS_SHA if qwen else None,
        "see_through_python": python,
        "qwen_weights_prefetched": qwen,
        "snapshots":manifests,
        "gpu_inference_verified": False,
    },ensure_ascii=False,indent=2),encoding="utf-8")
    temporary.replace(output)
    return output


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--with-qwen",action="store_true")
    ap.add_argument("--skip-install",action="store_true")
    a=ap.parse_args()
    print(prepare(qwen=a.with_qwen,install=not a.skip_install))


if __name__=="__main__":
    main()
