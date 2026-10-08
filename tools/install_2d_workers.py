"""Isolated, pinned Colab 2D worker dependencies; preserve the base CUDA stack.

Only called after choosing a 2D workflow. No model weights are loaded here.
External source trees are pinned to commits recorded in third_party.lock.json.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parents[1]
WORK = Path("/content/vtuber_builder/worker_envs/two_d")
PIN_KEYS = {"anime": "anime_segmentation", "sam": "sam2_1_hiera_tiny",
            "diffusers": "flux2_klein_4b"}
WORKERS = ("ANIME_ALPHA", "FLORENCE", "SAM", "FLUX")
# Binary wheels, resolved in the isolated venv against the base torch ABI.
# Do not add a second CUDA-enabled torch or change Colab's torchvision.
PYTHON_PACKAGES = (
    "pytorch-lightning==2.5.6", "kornia==0.8.2",
    "timm==1.0.20", "accelerate==1.10.1",
    "hydra-core==1.3.2", "psd-tools==1.11.0",
)


def _exec(args: list[str], *, cwd: Path | None = None, timeout: int = 600,
          env: dict | None = None) -> None:
    print("[2d-env] $ " + subprocess.list2cmdline(args), flush=True)
    subprocess.run(args, cwd=str(cwd) if cwd else None, timeout=timeout,
                   env=env, check=True)


def _pinned_source(kind: str, lock: dict) -> tuple[str, str]:
    entry = lock["tools"][PIN_KEYS[kind]]
    url, commit = entry["source_url"], entry["source_commit"]
    if not url.startswith("https://github.com/") or len(commit) != 40 or any(
        char not in "0123456789abcdef" for char in commit
    ):
        raise ValueError("upstream source URL/commit must be an immutable GitHub pin")
    return url, commit


def _checkout_source(kind: str, lock: dict) -> Path:
    url, commit = _pinned_source(kind, lock)
    folder = WORK / "upstream" / kind
    if not (folder / ".git").is_dir():
        folder.mkdir(parents=True, exist_ok=True)
        _exec(["git", "init", "-q", str(folder)], timeout=60)
        _exec(["git", "-C", str(folder), "remote", "add", "origin", url], timeout=60)
    else:
        _exec(["git", "-C", str(folder), "remote", "set-url", "origin", url], timeout=30)
    _exec(["git", "-C", str(folder), "fetch", "--depth", "1", "origin", commit], timeout=360)
    _exec(["git", "-C", str(folder), "checkout", "--detach", "-f", "FETCH_HEAD"], timeout=90)
    _exec(["git", "-C", str(folder), "reset", "--hard", commit], timeout=60)
    _exec(["git", "-C", str(folder), "clean", "-ffd"], timeout=60)
    actual = subprocess.check_output(
        ["git", "-C", str(folder), "rev-parse", "HEAD"], text=True, timeout=30
    ).strip()
    if actual != commit:
        raise RuntimeError(f"upstream {kind} source is not at the pinned commit")
    return folder


def _python() -> Path:
    return WORK / "venv" / "bin" / "python"


def _smoke(python: Path, anime_source: Path, torch_version: str,
           torchvision_version: str) -> None:
    probe = (
        "import os,sys,torch,torchvision; "
        "assert torch.__version__.split('+')[0]==os.environ['VTUBER_EXPECT_TORCH']; "
        "assert torchvision.__version__.split('+')[0]==os.environ['VTUBER_EXPECT_VISION']; "
        "from train import AnimeSegmentation; "
        "from sam2.build_sam import build_sam2; "
        "from sam2.sam2_image_predictor import SAM2ImagePredictor; "
        "from diffusers import Flux2KleinPipeline; "
        "import pytorch_lightning,kornia,timm,accelerate,hydra; "
        "print('[2d-env] worker-import-smoke-ok',flush=True)"
    )
    env = os.environ.copy()
    env["ANIME_SEGMENTATION_REPO"] = str(anime_source)
    env["PYTHONPATH"] = str(anime_source) + os.pathsep + str(ROOT)
    env["VTUBER_EXPECT_TORCH"] = torch_version
    env["VTUBER_EXPECT_VISION"] = torchvision_version
    _exec([str(python), "-c", probe], env=env, timeout=180)


def install_2d_environment() -> dict:
    import torch
    import torchvision

    lock_path = ROOT / "third_party.lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    torch_version = torch.__version__.split("+")[0]
    vision_version = torchvision.__version__.split("+")[0]
    stamp_inputs = {
        "torch": torch_version, "torchvision": vision_version,
        "packages": PYTHON_PACKAGES,
        "sources": {name: _pinned_source(name, lock) for name in PIN_KEYS},
    }
    fingerprint = hashlib.sha256(json.dumps(stamp_inputs, sort_keys=True).encode()).hexdigest()
    marker = WORK / "environment.ready.json"
    python = _python()
    source = WORK / "upstream" / "anime"
    if python.is_file() and source.joinpath("train.py").is_file() and marker.is_file():
        try:
            saved = json.loads(marker.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            saved = {}
        if saved.get("fingerprint") == fingerprint:
            _smoke(python, source, torch_version, vision_version)
            return {"python": str(python), "anime_source": str(source), "fingerprint": fingerprint}

    WORK.mkdir(parents=True, exist_ok=True)
    if not python.is_file():
        venv.EnvBuilder(with_pip=True, system_site_packages=True).create(str(WORK / "venv"))
    # Pin the *existing* system-provided CUDA ABI in the worker pip resolver.
    constraints = WORK / "cuda_constraints.txt"
    constraints.write_text(
        f"torch=={torch_version}\ntorchvision=={vision_version}\n", encoding="utf-8"
    )
    env = os.environ.copy()
    env["PIP_CONSTRAINT"] = str(constraints)
    env["SAM2_BUILD_CUDA"] = "0"
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    _exec([str(python), "-m", "pip", "install", "--prefer-binary",
           "--only-binary=:all:", *PYTHON_PACKAGES],
          env=env, timeout=1800)
    sources = {kind: _checkout_source(kind, lock) for kind in PIN_KEYS}
    # Install source packages with dependencies explicitly disabled. The
    # standalone pip above already resolved Python libraries; never let an
    # external pyproject replace torch/torchvision.
    for kind in ("sam", "diffusers"):
        # SAM2's pyproject declares torch as a build dependency. Disabling
        # build isolation is essential: installing build dependencies into an
        # isolated environment could download a second CUDA PyTorch build.
        _exec([str(python), "-m", "pip", "install", "--no-deps",
               "--no-build-isolation", "--editable", str(sources[kind])],
              env=env, timeout=1800)
    if not (sources["anime"] / "train.py").is_file():
        raise RuntimeError("pinned Anime Segmentation train.py is missing")
    _smoke(python, sources["anime"], torch_version, vision_version)
    marker.write_text(json.dumps({"fingerprint": fingerprint, "base_cuda_preserved": True},
                                 indent=2), encoding="utf-8")
    return {"python": str(python), "anime_source": str(sources["anime"]),
            "fingerprint": fingerprint}


def activate_2d_environment() -> dict:
    """Called by the UI server, not an inference process."""
    info = install_2d_environment()
    for worker in WORKERS:
        os.environ["VTUBER_WORKER_" + worker] = info["python"]
    os.environ["ANIME_SEGMENTATION_REPO"] = info["anime_source"]
    return info


if __name__ == "__main__":
    print(json.dumps(install_2d_environment(), ensure_ascii=False))
