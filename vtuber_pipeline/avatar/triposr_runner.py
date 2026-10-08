"""Deterministic wrapper around the pinned upstream TripoSR CLI.

Upstream TripoSR downloads facebook/dino-vitb16/config.json without a revision.
This wrapper intercepts that single Hugging Face download and forces the pinned
revision before executing upstream run.py unchanged.
"""

from __future__ import annotations

import hashlib
import pathlib
import runpy
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
        if repo_id == DINO_MODEL_ID:
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


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: triposr_runner.py RUN_PY [TripoSR args...]")

    run_script = pathlib.Path(sys.argv[1]).expanduser().resolve()
    if not run_script.is_file():
        raise FileNotFoundError(f"TripoSR run.py not found: {run_script}")

    upstream_args = sys.argv[2:]
    _install_hf_revision_guard()

    if "--no-remove-bg" not in upstream_args:
        _install_rembg_model_guard()
        _verify_rembg_u2net()

    # Upstream argparse must see its own script as argv[0].
    sys.argv = [str(run_script), *upstream_args]
    runpy.run_path(str(run_script), run_name="__main__")


if __name__ == "__main__":
    main()
