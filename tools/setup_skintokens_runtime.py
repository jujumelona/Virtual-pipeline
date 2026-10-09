"""Explicit, isolated setup for opt-in TokenRig / SkinTokens (Ampere+ only).

Never install this from avatar generation. The installer is invoked separately,
so a failed CUDA build cannot damage the existing Colab TripoSR/FLUX runtime.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

from vtuber_pipeline.avatar.skintokens_bridge import (
    SOURCE_SHA, runtime_identity, check_gpu_compatibility,
)


SOURCE_URL = "https://github.com/VAST-AI-Research/SkinTokens.git"


def _run(args: list[str], *, cwd: Path | None = None, timeout: int = 3600) -> None:
    print("[skintokens:setup]", " ".join(args), flush=True)
    subprocess.run(args, cwd=str(cwd) if cwd is not None else None,
                   check=True, timeout=timeout)


def _base_gpu_check() -> None:
    """Probe Colab's existing torch before downloading >1 GiB of assets."""
    try:
        import torch
        if not torch.cuda.is_available():
            raise RuntimeError("no CUDA GPU")
        device = torch.cuda.get_device_properties(0)
        free, total = torch.cuda.mem_get_info(0)
        if device.major < 8 or not torch.cuda.is_bf16_supported():
            raise RuntimeError(
                f"{device.name} sm{device.major}{device.minor} cannot execute "
                "upstream BF16/FlashAttention-2; T4 is not supported"
            )
        if total < 14 * 1024**3 or free < 14 * 1024**3:
            raise RuntimeError("SkinTokens requires >=14 GiB total and free GPU VRAM")
    except ImportError as exc:
        raise RuntimeError("Run this setup in an initialized CUDA torch environment") from exc


def install(directory: Path, torch_index: str) -> dict:
    _base_gpu_check()
    uv = shutil.which("uv")
    git = shutil.which("git")
    if not uv or not git:
        raise RuntimeError("git and uv are required; install uv in the setup cell first")
    directory = directory.expanduser().resolve()
    directory.parent.mkdir(parents=True, exist_ok=True)
    if not directory.exists():
        _run([git, "clone", "--filter=blob:none", SOURCE_URL, str(directory)], timeout=600)
    elif not (directory / ".git").is_dir():
        raise RuntimeError("Refusing to replace non-repository SkinTokens directory")

    dirty = subprocess.run([git, "-C", str(directory), "status", "--porcelain", "--untracked-files=no"],
                           capture_output=True, text=True, check=True, timeout=20)
    if dirty.stdout.strip():
        raise RuntimeError("SkinTokens checkout is dirty; refusing destructive source changes")
    _run([git, "-C", str(directory), "fetch", "origin", SOURCE_SHA], timeout=300)
    _run([git, "-C", str(directory), "checkout", "--detach", SOURCE_SHA], timeout=60)

    venv = directory / ".venv"
    interpreter = venv / "bin/python"
    if not interpreter.is_file():
        _run([uv, "venv", "--python", "3.11", str(venv)], timeout=360)
    _run([uv, "pip", "install", "--python", str(interpreter),
          "torch==2.7.0", "torchvision==0.22.0", "torchaudio==2.7.0",
          "--index-url", torch_index], timeout=3600)
    _run([uv, "pip", "install", "--python", str(interpreter),
          "-r", str(directory / "requirements.txt")], timeout=3600)
    _run([uv, "pip", "install", "--python", str(interpreter),
          "flash-attn", "--no-build-isolation"], timeout=3600)
    _run([str(interpreter), "-u", str(directory / "download.py"), "--model"],
         cwd=directory, timeout=3600)
    old_dir = os.environ.get("VTUBER_SKINTOKENS_DIR")
    old_python = os.environ.get("VTUBER_SKINTOKENS_PYTHON")
    os.environ["VTUBER_SKINTOKENS_DIR"] = str(directory)
    os.environ["VTUBER_SKINTOKENS_PYTHON"] = str(interpreter)
    try:
        identity = runtime_identity()
        gpu = check_gpu_compatibility(identity)
    finally:
        if old_dir is None:
            os.environ.pop("VTUBER_SKINTOKENS_DIR", None)
        else:
            os.environ["VTUBER_SKINTOKENS_DIR"] = old_dir
        if old_python is None:
            os.environ.pop("VTUBER_SKINTOKENS_PYTHON", None)
        else:
            os.environ["VTUBER_SKINTOKENS_PYTHON"] = old_python
    print("[skintokens:setup] isolated runtime ready:", gpu, flush=True)
    print("export VTUBER_SKINTOKENS_DIR=" + str(directory), flush=True)
    print("export VTUBER_SKINTOKENS_PYTHON=" + str(interpreter), flush=True)
    return identity


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", default=os.environ.get(
        "VTUBER_SKINTOKENS_DIR", "/content/third_party/SkinTokens"))
    parser.add_argument("--torch-index",
                        default="https://download.pytorch.org/whl/cu128")
    args = parser.parse_args()
    if not args.torch_index.startswith("https://download.pytorch.org/whl/cu"):
        parser.error("Specify an official PyTorch CUDA wheel index")
    install(Path(args.directory), args.torch_index)


if __name__ == "__main__":
    main()
