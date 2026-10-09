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
import threading
import venv
from collections import deque

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
    # SAM2's upstream setup.py requires iopath>=0.1.10, which imports portalocker.
    # The old SAM2 --no-deps editable install skipped these runtime requirements.
    "portalocker==2.10.1",
)
SAM2_RUNTIME_PACKAGES = ("iopath==0.1.10",)

# This must execute Hydra's configured backbone, not merely import build_sam2.
# An import-only smoke misses missing imports inside hieradet.py (e.g. iopath).
SAM2_CONSTRUCTION_SMOKE = (
    "from iopath.common.file_io import g_pathmgr; "
    "from sam2.modeling.backbones.hieradet import Hiera; "
    "from sam2.build_sam import build_sam2; "
    "from sam2.sam2_image_predictor import SAM2ImagePredictor; "
    "model=build_sam2('configs/sam2.1/sam2.1_hiera_t.yaml', "
    "ckpt_path=None, device='cpu', apply_postprocessing=False); "
    "assert model is not None; "
    "predictor=SAM2ImagePredictor(model); "
    "assert predictor is not None; "
    "print('[2d-env] sam2.1-hiera-t-hydra-construction-ok', flush=True)"
)

# The pinned Diffusers source requires Hub >=1.32. Keep these newer
# packages ONLY in the FLUX worker, not in the shared Colab/3D runtime.
FLUX_PYTHON_PACKAGES = (
    "accelerate==1.10.1",
    "huggingface-hub==1.33.0",
    "transformers==5.0.0",
    "torchao==0.16.0",
    "sentencepiece>=0.2.0",
    "protobuf>=5,<7",
)
FLUX_SMOKE = (
    "import importlib.metadata as md, huggingface_hub; "
    "assert md.version('huggingface-hub')=='1.33.0'; "
    "assert md.version('transformers')=='5.0.0'; "
    "assert md.version('torchao')=='0.16.0'; "
    "assert callable(huggingface_hub.resolve_revision); "
    "from torchao.quantization import FqnToConfig, quantize_; "
    "from transformers import Qwen2TokenizerFast, Qwen3ForCausalLM; "
    "from diffusers import Flux2KleinPipeline; "
    "print('[2d-env] flux-transformers-hub-import-ok', flush=True)"
)


def _exec(args: list[str], *, cwd: Path | None = None, timeout: int = 600,
          env: dict | None = None) -> None:
    """Show the *actual* failing pip/git output, including the final error.

    Called from the Gradio worker, so a bare CalledProcessError with only the
    command is not actionable. Persist full output even when setup times out.
    """
    log_path = WORK / "logs" / "dependency_setup.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    command = subprocess.list2cmdline(args)
    print("[2d-env] $ " + command, flush=True)
    tail: deque[str] = deque(maxlen=140)
    with log_path.open("a", encoding="utf-8") as logfile:
        logfile.write("\n[2d-env] $ " + command + "\n")
        logfile.flush()
        process = subprocess.Popen(
            args, cwd=str(cwd) if cwd else None, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, errors="replace", bufsize=1,
        )

        def relay() -> None:
            assert process.stdout is not None
            for line in process.stdout:
                tail.append(line)
                logfile.write(line)
                logfile.flush()
                print(line, end="", flush=True)

        reader = threading.Thread(target=relay, daemon=True)
        reader.start()
        try:
            result = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            process.kill()
            process.wait(timeout=10)
            reader.join(timeout=10)
            raise RuntimeError(
                f"[2d-env] setup timed out after {timeout}s: {command}\n"
                f"Full output: {log_path}\n" + "".join(tail)[-8000:]
            ) from exc
        reader.join(timeout=10)
        if result:
            raise RuntimeError(
                f"[2d-env] dependency command failed (exit={result}): {command}\n"
                + "".join(tail)[-8000:] + f"\nFull output: {log_path}"
            )


def _prepare_venv(folder: str) -> Path:
    """Reuse Colab's preinstalled pip, without the broken ensurepip bootstrap.

    EnvBuilder(with_pip=True) invokes ensurepip --upgrade --default-pip in
    each new environment, which can fail before any model dependency is
    installed. Retrying the setup also repairs a partially created venv.
    The workers deliberately inherit the existing CUDA-enabled site packages.
    """
    location = WORK / folder
    venv.EnvBuilder(with_pip=False, system_site_packages=True).create(str(location))
    python = location / "bin" / "python"
    _exec([str(python), "-m", "pip", "--version"], timeout=45)
    return python


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


def _flux_python() -> Path:
    # Diffusers has a different and faster-moving dependency tree than SAM2.
    return WORK / "venv_flux" / "bin" / "python"


def _smoke(python: Path, anime_source: Path, torch_version: str,
           torchvision_version: str) -> None:
    probe = (
        "import os,sys,torch,torchvision; "
        "assert torch.__version__.split('+')[0]==os.environ['VTUBER_EXPECT_TORCH']; "
        "assert torchvision.__version__.split('+')[0]==os.environ['VTUBER_EXPECT_VISION']; "
        "from train import AnimeSegmentation; "
        "from sam2.build_sam import build_sam2; "
        "from sam2.sam2_image_predictor import SAM2ImagePredictor; "
        "import pytorch_lightning,kornia,timm,accelerate,hydra; "
        "print('[2d-env] worker-import-smoke-ok',flush=True)"
    )
    env = os.environ.copy()
    env["ANIME_SEGMENTATION_REPO"] = str(anime_source)
    env["PYTHONPATH"] = str(anime_source) + os.pathsep + str(ROOT)
    env["VTUBER_EXPECT_TORCH"] = torch_version
    env["VTUBER_EXPECT_VISION"] = torchvision_version
    _exec([str(python), "-c", probe], env=env, timeout=180)
    _exec([str(python), "-c", SAM2_CONSTRUCTION_SMOKE], env=env, timeout=240)


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
        "sam2_runtime_packages": SAM2_RUNTIME_PACKAGES,
        "sam2_construction_smoke": SAM2_CONSTRUCTION_SMOKE,
        "flux_packages": FLUX_PYTHON_PACKAGES,
        "flux_smoke": FLUX_SMOKE,
        "sources": {name: _pinned_source(name, lock) for name in PIN_KEYS},
    }
    fingerprint = hashlib.sha256(json.dumps(stamp_inputs, sort_keys=True).encode()).hexdigest()
    marker = WORK / "environment.ready.json"
    python = _python()
    flux_python = _flux_python()
    source = WORK / "upstream" / "anime"
    if (python.is_file() and flux_python.is_file()
            and source.joinpath("train.py").is_file() and marker.is_file()):
        try:
            saved = json.loads(marker.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            saved = {}
        if saved.get("fingerprint") == fingerprint:
            try:
                _smoke(python, source, torch_version, vision_version)
                _exec([str(flux_python), "-c", FLUX_SMOKE], timeout=180)
            except Exception as exc:
                print(f"[2d-env] stale worker cache failed smoke: {exc}; repairing", flush=True)
                marker.unlink(missing_ok=True)
            else:
                return {"python": str(python), "flux_python": str(flux_python),
                        "anime_source": str(source), "fingerprint": fingerprint}

    WORK.mkdir(parents=True, exist_ok=True)
    _prepare_venv("venv")
    _prepare_venv("venv_flux")
    # Pin the *existing* system-provided CUDA ABI in the worker pip resolver.
    constraints = WORK / "cuda_constraints.txt"
    constraints.write_text(
        f"torch=={torch_version}\ntorchvision=={vision_version}\n", encoding="utf-8"
    )
    env = os.environ.copy()
    env["PIP_CONSTRAINT"] = str(constraints)
    env["SAM2_BUILD_CUDA"] = "0"
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    # Hydra pins antlr4-python3-runtime==4.9.*, which is source-only on
    # PyPI. Keep binary preference, but permit this pure-Python dependency
    # to build. PIP_CONSTRAINT still locks the existing Torch/Torchvision ABI.
    # Distinct venv directories have independent pip databases. Install
    # 2D/SAM and FLUX dependency sets concurrently without ever running two
    # pip resolvers against the *same* Python environment.
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=2) as executor:
        sam_packages = executor.submit(
            _exec, [str(python), "-m", "pip", "install", "--prefer-binary",
                    *PYTHON_PACKAGES], env=env, timeout=1800,
        )
        flux_packages = executor.submit(
            _exec, [str(flux_python), "-m", "pip", "install", "--prefer-binary",
                    "--only-binary=:all:", *FLUX_PYTHON_PACKAGES],
            env=env, timeout=1200,
        )
        # Wait for both dependencies before installing editable sources.
        sam_packages.result()
        flux_packages.result()
    sources = {kind: _checkout_source(kind, lock) for kind in PIN_KEYS}
    # SAM2 requires iopath>=0.1.10, which is sdist-only on PyPI.
    # iopath itself requires typing_extensions, tqdm and portalocker.
    # Install its declared dependencies normally (no --no-deps): limiting
    # them would hide runtime import failures until image generation.
    # PIP_CONSTRAINT locks Torch/Torchvision so resolving this pure-Python
    # package cannot replace the Colab CUDA stack.
    _exec([str(python), "-m", "pip", "install", "--prefer-binary",
           *SAM2_RUNTIME_PACKAGES],
          env=env, timeout=600)
    # Install source packages with dependencies explicitly disabled. The
    # standalone pip above already resolved Python libraries; never let an
    # external pyproject replace torch/torchvision.
    # SAM2 and Diffusers must never share the mutable package environment.
    # In particular FLUX packages must not downgrade SAM2 dependencies.
    _exec([str(python), "-m", "pip", "install", "--no-deps",
           "--no-build-isolation", "--editable", str(sources["sam"])],
          env=env, timeout=1800)
    _exec([str(flux_python), "-m", "pip", "install", "--no-deps",
           "--no-build-isolation", "--editable", str(sources["diffusers"])],
          env=env, timeout=1800)
    if not (sources["anime"] / "train.py").is_file():
        raise RuntimeError("pinned Anime Segmentation train.py is missing")
    _smoke(python, sources["anime"], torch_version, vision_version)
    _exec([str(flux_python), "-c", FLUX_SMOKE], timeout=180)
    marker.write_text(json.dumps({"fingerprint": fingerprint, "base_cuda_preserved": True},
                                 indent=2), encoding="utf-8")
    return {"python": str(python), "flux_python": str(flux_python),
            "anime_source": str(sources["anime"]), "fingerprint": fingerprint}


def install_alpha_environment() -> dict:
    """Install only the image-matting worker required by 3D VRM.

    In particular the 3D workflow does not install SAM2 or FLUX, and does not
    download the large 2D checkpoints just to remove a reference background.
    """
    import torch
    import torchvision

    lock = json.loads((ROOT / "third_party.lock.json").read_text(encoding="utf-8"))
    torch_version = torch.__version__.split("+")[0]
    vision_version = torchvision.__version__.split("+")[0]
    packages = ("pytorch-lightning==2.5.6", "timm==1.0.20",
                "kornia==0.8.2", "huggingface-hub>=0.34.0,<1.0")
    fingerprint = hashlib.sha256(json.dumps({
        "torch": torch_version, "torchvision": vision_version,
        "packages": packages, "source": _pinned_source("anime", lock),
    }, sort_keys=True).encode()).hexdigest()
    python = WORK / "venv_alpha" / "bin" / "python"
    source = WORK / "upstream" / "anime"
    marker = WORK / "alpha.ready.json"
    env = os.environ.copy()
    env["ANIME_SEGMENTATION_REPO"] = str(source)
    env["PYTHONPATH"] = str(source) + os.pathsep + str(ROOT)
    env["VTUBER_EXPECT_TORCH"] = torch_version
    env["VTUBER_EXPECT_VISION"] = vision_version
    smoke = (
        "import os,torch,torchvision; "
        "assert torch.__version__.split('+')[0]==os.environ['VTUBER_EXPECT_TORCH']; "
        "assert torchvision.__version__.split('+')[0]==os.environ['VTUBER_EXPECT_VISION']; "
        "from train import AnimeSegmentation; "
        "print('[alpha-env] source-and-cuda-abi-ok',flush=True)"
    )
    if python.is_file() and (source / "train.py").is_file() and marker.is_file():
        try:
            ready = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            ready = {}
        if ready.get("fingerprint") == fingerprint:
            try:
                _exec([str(python), "-c", smoke], env=env, timeout=180)
            except Exception as exc:
                print(f"[alpha-env] stale 3D alpha cache failed smoke: {exc}; repairing", flush=True)
                marker.unlink(missing_ok=True)
            else:
                return {"python": str(python), "anime_source": str(source),
                        "fingerprint": fingerprint}
    WORK.mkdir(parents=True, exist_ok=True)
    _prepare_venv("venv_alpha")
    constraints = WORK / "alpha_cuda_constraints.txt"
    constraints.write_text(f"torch=={torch_version}\ntorchvision=={vision_version}\n",
                           encoding="utf-8")
    install_env = dict(env, PIP_CONSTRAINT=str(constraints),
                       PIP_DISABLE_PIP_VERSION_CHECK="1")
    # Never allow a model package to replace Colab's CUDA-enabled torch.
    _exec([str(python), "-m", "pip", "install", "--prefer-binary",
           "--only-binary=:all:", *packages], env=install_env, timeout=1800)
    source = _checkout_source("anime", lock)
    if not (source / "train.py").is_file():
        raise RuntimeError("Pinned anime-segmentation source is missing train.py")
    _exec([str(python), "-c", smoke], env=env, timeout=180)
    marker.write_text(json.dumps({
        "fingerprint": fingerprint, "source": str(source),
        "base_cuda_preserved": True, "model_scope": "alpha_only",
    }, indent=2), encoding="utf-8")
    return {"python": str(python), "anime_source": str(source),
            "fingerprint": fingerprint}


def activate_alpha_environment() -> dict:
    """Make the 3D image-matting stage executable without loading 2D AI stacks."""
    info = install_alpha_environment()
    os.environ["VTUBER_WORKER_ANIME_ALPHA"] = info["python"]
    os.environ["ANIME_SEGMENTATION_REPO"] = info["anime_source"]
    return info


def activate_2d_environment() -> dict:
    """Called by the UI server, not an inference process."""
    info = install_2d_environment()
    for worker in ("ANIME_ALPHA", "FLORENCE", "SAM"):
        os.environ["VTUBER_WORKER_" + worker] = info["python"]
    os.environ["VTUBER_WORKER_FLUX"] = info["flux_python"]
    os.environ["ANIME_SEGMENTATION_REPO"] = info["anime_source"]
    return info


if __name__ == "__main__":
    print(json.dumps(install_2d_environment(), ensure_ascii=False))
