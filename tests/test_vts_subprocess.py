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
