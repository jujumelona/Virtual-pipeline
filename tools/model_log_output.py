"""Keep repeated model weight progress out of notebook and stored logs.

Only identified transfer/checkpoint progress bars are suppressed. Exceptions,
linker diagnostics and other ordinary worker output remain fully visible.
"""
from __future__ import annotations

import os
import re
from collections.abc import Mapping

_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_PROGRESS = re.compile(r"\b\d{1,3}%\s*[|▏▎▍▌▋▊▉█]")
_WEIGHT_HINTS = (
    "loading checkpoint shards",
    "loading pipeline components",
    "loading weights",
    "loading model weights",
    "fetching ",
    "downloading ",
    ".safetensors",
    ".gguf",
    ".ckpt",
    ".onnx",
    ".bin:",
)
_DIAGNOSTICS = ("error", "traceback", "exception", "failed", "warning", "fatal")


def is_weight_progress(line: str) -> bool:
    """Identify only repetitive model-loading progress, never an error line."""
    if os.environ.get("VTUBER_MODEL_PROGRESS_VERBOSE") == "1":
        return False
    value = _ANSI.sub("", line).strip().casefold()
    if any(term in value for term in _DIAGNOSTICS):
        return False
    return bool(_PROGRESS.search(value) and
                any(term in value for term in _WEIGHT_HINTS))


def quiet_model_environment(base: Mapping[str, str] | None = None) -> dict[str, str]:
    """Disable model-library progress output in *children* only.

    Do not silence stderr, Python warnings generally, or the real error logs.
    Callers can explicitly override individual environment variables.
    """
    env = dict(os.environ if base is None else base)
    if env.get("VTUBER_MODEL_PROGRESS_VERBOSE") == "1":
        return env
    for key, value in (
        ("HF_HUB_DISABLE_PROGRESS_BARS", "1"),
        ("TQDM_DISABLE", "1"),
        ("TRANSFORMERS_VERBOSITY", "error"),
        ("DIFFUSERS_VERBOSITY", "error"),
    ):
        env.setdefault(key, value)
    return env
