"""Deterministic wrapper around the pinned upstream TripoSR CLI.

Upstream TripoSR downloads facebook/dino-vitb16/config.json without a revision.
This wrapper intercepts that single Hugging Face download and forces the pinned
revision before executing upstream run.py unchanged.
"""

from __future__ import annotations

import hashlib
import pathlib
import runpy
import os
import sys
from typing import Any


DINO_MODEL_ID = "facebook/dino-vitb16"
DINO_MODEL_REVISION = "f205d5d8e640a89a2b8ef0369670dfc37cc07fc2"
REMBG_MODEL_NAME = "u2net"
REMBG_U2NET_MD5 = "60024c5c889badc19c04ad937298a77b"


def _install_hf_revision_guard() -> None:
    try:
        import huggingface_hub
    except ImportError as exc:
        raise RuntimeError(
            "huggingface-hub is required by the pinned TripoSR runner"
        ) from exc

    original = huggingface_hub.hf_hub_download

    def pinned_hf_hub_download(
        repo_id: str,
        filename: str,
        *args: Any,
        **kwargs: Any,
    ):
        if repo_id != DINO_MODEL_ID:
            raise RuntimeError(
                "Unexpected Hugging Face repository requested by pinned "
                f"TripoSR runtime: {repo_id!r}"
            )
        if filename != "config.json":
            raise RuntimeError(
                "Unexpected DINO artifact requested by pinned TripoSR runtime: "
                f"{filename!r}"
            )
        requested = kwargs.get("revision")
        if requested not in (None, DINO_MODEL_REVISION):
            raise RuntimeError(
                "TripoSR DINO revision override rejected: "
                f"{requested!r} != {DINO_MODEL_REVISION}"
            )
        kwargs["revision"] = DINO_MODEL_REVISION
        return original(repo_id, filename, *args, **kwargs)

    huggingface_hub.hf_hub_download = pinned_hf_hub_download




def _file_md5(path: pathlib.Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _install_rembg_model_guard() -> None:
    """Force TripoSR's no-argument rembg session onto commercial-safe u2net."""
    try:
        import rembg
    except ImportError as exc:
        raise RuntimeError("rembg is required by TripoSR background removal") from exc

    original = rembg.new_session

    def pinned_new_session(
        model_name: str = REMBG_MODEL_NAME,
        *args: Any,
        **kwargs: Any,
    ):
        if model_name != REMBG_MODEL_NAME:
            raise RuntimeError(
                "Unexpected rembg model requested by TripoSR: "
                f"{model_name!r}; required={REMBG_MODEL_NAME!r}"
            )
        return original(REMBG_MODEL_NAME, *args, **kwargs)

    rembg.new_session = pinned_new_session


def _verify_rembg_u2net() -> str:
    """Download/resolve u2net and verify cached bytes before inference."""
    try:
        from rembg.sessions.u2net import U2netSession
    except ImportError as exc:
        raise RuntimeError("rembg u2net session is unavailable") from exc

    model_path = pathlib.Path(U2netSession.download_models()).expanduser().resolve()
    if not model_path.is_file() or model_path.stat().st_size <= 0:
        raise RuntimeError(f"rembg u2net model is missing or empty: {model_path}")

    actual = _file_md5(model_path)
    if actual != REMBG_U2NET_MD5:
        raise RuntimeError(
            "rembg u2net MD5 mismatch: "
            f"expected {REMBG_U2NET_MD5}, got {actual}"
        )
    return str(model_path)


def prepare_no_bg_image(image_path, target, *, resize_foreground):
    """Use the pinned upstream resize function and its neutral RGB background."""
    import numpy as np
    from PIL import Image
    image_path, target = pathlib.Path(image_path), pathlib.Path(target)
    with Image.open(image_path) as source:
        image = source.convert("RGBA")
    if image.getchannel("A").getextrema() == (255, 255):
        return image_path  # --no-remove-bg already requires prepared opaque input.
    image = resize_foreground(image, 0.85)
    values = np.asarray(image).astype(np.float32) / 255.0
    rgb = values[:, :, :3] * values[:, :, 3:4] + (1 - values[:, :, 3:4]) * 0.5
    target.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray((rgb * 255.0).astype(np.uint8)).save(target)
    print(f"[TripoSR] segmented alpha: official foreground ratio=0.85, gray=0.5 -> {target}",
          flush=True)
    return target


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: triposr_runner.py RUN_PY [TripoSR args...]")

    run_script = pathlib.Path(sys.argv[1]).expanduser().resolve()
    if not run_script.is_file():
        raise FileNotFoundError(f"TripoSR run.py not found: {run_script}")

    # runpy.run_path executes run.py as __main__, but unlike
    # 'python /path/to/TripoSR/run.py' it DOES NOT prepend the script's
    # directory to sys.path. The wrapper is inside vtuber_pipeline, so the
    # upstream 'from tsr.system import TSR' otherwise raises
    # ModuleNotFoundError despite a correct pinned checkout and CUDA GPU.
    source_root = run_script.parent
    # Upstream TripoSR is an implicit namespace package: there is NO
    # tsr/__init__.py in the immutable pinned checkout. Verify its real entry.
    if not (source_root / "tsr" / "system.py").is_file():
        raise RuntimeError(
            f"Pinned TripoSR source is incomplete: missing {source_root / 'tsr' / 'system.py'}"
        )
    if str(source_root) not in sys.path:
        sys.path.insert(0, str(source_root))
    print(f"[TripoSR] source import root: {source_root}", flush=True)

    upstream_args = sys.argv[2:]

    # The pinned TripoSR isosurface helper imports only marching_cubes.
    # Supply that API from a prebuilt scikit-image wheel rather than forcing
    # a PyTorch/CUDA native extension build in Colab.
    from vtuber_pipeline.avatar.marching_cubes_backend import (
        install_triposr_marching_cubes,
    )

    install_triposr_marching_cubes()
    _install_hf_revision_guard()

    if "--no-remove-bg" not in upstream_args:
        _install_rembg_model_guard()
        _verify_rembg_u2net()
    else:
        # Our caller submits one already-segmented view. Upstream's no-bg
        # branch converts directly to RGB, discarding alpha without compositing.
        from tsr.utils import resize_foreground
        output = pathlib.Path(upstream_args[upstream_args.index("--output-dir") + 1])
        upstream_args[0] = str(prepare_no_bg_image(
            upstream_args[0], output / "prepared_foreground.png",
            resize_foreground=resize_foreground))

    # Upstream argparse must see its own script as argv[0].
    if os.environ.get("VTUBER_REQUIRE_CUDA") == "1":
        import torch
        available = bool(torch.cuda.is_available())
        print(f"[GPU] CUDA 사용 가능: {available}", flush=True)
        if not available:
            raise RuntimeError("CUDA GPU 없음 — CPU 자동 전환 금지")
        print(f"[GPU] 장치: {torch.cuda.get_device_name(0)}", flush=True)
        print("[GPU] TripoSR 모델 로드 및 추론 시작", flush=True)
        if "--device" not in upstream_args:
            upstream_args.extend(["--device", "cuda:0"])

    sys.argv = [str(run_script), *upstream_args]
    runpy.run_path(str(run_script), run_name="__main__")


if __name__ == "__main__":
    main()
