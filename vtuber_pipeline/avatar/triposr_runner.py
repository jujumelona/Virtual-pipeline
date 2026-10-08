"""Deterministic wrapper around the pinned upstream TripoSR CLI.

Upstream TripoSR downloads facebook/dino-vitb16/config.json without a revision.
This wrapper intercepts that single Hugging Face download and forces the pinned
revision before executing upstream run.py unchanged.
"""

from __future__ import annotations

import pathlib
import runpy
import sys
from typing import Any


DINO_MODEL_ID = "facebook/dino-vitb16"
DINO_MODEL_REVISION = "f205d5d8e640a89a2b8ef0369670dfc37cc07fc2"


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


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: triposr_runner.py RUN_PY [TripoSR args...]")

    run_script = pathlib.Path(sys.argv[1]).expanduser().resolve()
    if not run_script.is_file():
        raise FileNotFoundError(f"TripoSR run.py not found: {run_script}")

    upstream_args = sys.argv[2:]
    _install_hf_revision_guard()

    # Upstream argparse must see its own script as argv[0].
    sys.argv = [str(run_script), *upstream_args]
    runpy.run_path(str(run_script), run_name="__main__")


if __name__ == "__main__":
    main()
