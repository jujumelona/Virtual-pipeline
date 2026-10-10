"""Real child-process wall-timeout tests; no CUDA or GPU downloads."""
import sys
import time
from pathlib import Path

import pytest

from tools.vts_subprocess import run_logged


def test_silent_hang_stops_at_deadline(tmp_path):
    start = time.monotonic()
    with pytest.raises(TimeoutError, match="wall-clock timeout"):
        run_logged([sys.executable, "-c", "import time; time.sleep(10)"],
                   log_path=tmp_path / "silent.log", timeout_seconds=0.35)
    assert time.monotonic() - start < 5.0


def test_streaming_output_keeps_full_log(tmp_path, capsys):
    path = tmp_path / "stdout.log"
    code = run_logged([sys.executable, "-u", "-c",
                       "print('layer start'); print('layer complete')"],
                      log_path=path, timeout_seconds=8)
    assert code == 0
    assert "layer start" in path.read_text()
    assert "layer complete" in capsys.readouterr().out


def test_nonzero_exit_retained(tmp_path):
    code = run_logged([sys.executable, "-c", "raise SystemExit(12)"],
                      log_path=tmp_path / "failed.log", timeout_seconds=5)
    assert code == 12

def test_weight_progress_is_not_written_or_echoed_but_errors_remain(tmp_path, capsys):
    path = tmp_path / "weights.log"
    program = (
        "print('Loading checkpoint shards: 25%|██ | 1/4', flush=True);"
        "print('Loading checkpoint shards: 50%|████ | 2/4', flush=True);"
        "print('face model loaded', flush=True);"
        "print('RuntimeError: CUDA allocation failed', flush=True);"
        "raise SystemExit(7)"
    )
    exitcode = run_logged([sys.executable, "-u", "-c", program],
                          log_path=path, timeout_seconds=8)
    assert exitcode == 7
    stored = path.read_text()
    displayed = capsys.readouterr().out
    for text in (stored, displayed):
        assert "checkpoint shards" not in text
        assert "face model loaded" in text
        assert "RuntimeError: CUDA allocation failed" in text
