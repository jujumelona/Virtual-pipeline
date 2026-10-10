"""Regression checks for compact checkpoint progress and complete diagnostics."""
from __future__ import annotations

from tools.model_log_output import is_weight_progress, quiet_model_environment


def test_only_repetitive_model_weight_progress_is_suppressed(monkeypatch):
    monkeypatch.delenv("VTUBER_MODEL_PROGRESS_VERBOSE", raising=False)
    assert is_weight_progress(
        "Loading checkpoint shards:  50%|█████     | 2/4 [00:02<00:02]"
    )
    assert is_weight_progress(
        "model-00001-of-00004.safetensors:  80%|████    | 3.0G/4.0G"
    )
    assert is_weight_progress(
        "Fetching 8 files:  25%|██        | 2/8"
    )
    for line in (
        "RuntimeError: failed loading checkpoint shards at 50%|..",
        "WARNING downloading model failed at 20%|..",
        "Traceback (most recent call last):",
        "/usr/bin/ld: undefined reference to symbol",
        "Loading layers complete",
        "generated part 03: completed",
        " 50%|█████| inference step",
    ):
        assert not is_weight_progress(line)


def test_model_progress_quiet_child_environment_preserves_user_overrides(monkeypatch):
    monkeypatch.delenv("VTUBER_MODEL_PROGRESS_VERBOSE", raising=False)
    env = quiet_model_environment({"TOKEN": "private", "HF_HUB_DISABLE_PROGRESS_BARS": "0"})
    assert env["HF_HUB_DISABLE_PROGRESS_BARS"] == "0"
    assert env["TQDM_DISABLE"] == "1"
    assert env["TRANSFORMERS_VERBOSITY"] == "error"
    assert env["DIFFUSERS_VERBOSITY"] == "error"
    assert env["TOKEN"] == "private"

    monkeypatch.setenv("VTUBER_MODEL_PROGRESS_VERBOSE", "1")
    assert not is_weight_progress("Loading checkpoint shards: 40%|██|")
    assert quiet_model_environment({"VTUBER_MODEL_PROGRESS_VERBOSE": "1"}) == {
        "VTUBER_MODEL_PROGRESS_VERBOSE": "1"
    }
