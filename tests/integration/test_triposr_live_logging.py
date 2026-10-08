"""Colab live inference log forwarding without real GPU/model downloads."""

from __future__ import annotations

import io

from vtuber_pipeline.avatar import reconstruction
from vtuber_pipeline.core.stage_progress import stage_reporter


def test_triposr_subprocess_streams_actual_stdout_and_stderr_to_ui(monkeypatch):
    observed = []
    captured = {}

    class FakePopen:
        def __init__(self, cmd, **kwargs):
            captured["cmd"] = cmd
            captured["kwargs"] = kwargs
            self.stdout = io.StringIO("loading TripoSR model\nGPU inference started\nmesh saved\n")

        def wait(self, timeout):
            captured["timeout"] = timeout
            return 0

    monkeypatch.setattr(reconstruction.subprocess, "Popen", FakePopen)
    with stage_reporter(lambda name, status, detail: observed.append((name, status, detail))):
        result = reconstruction._run_triposr_with_diagnostics(
            ["python", "run.py"],
            timeout=30,
            cwd="/models",
            env={"TRIPOSR_DIR": "/models"},
        )

    assert result.returncode == 0
    assert "mesh saved" in result.stdout
    assert captured["kwargs"]["cwd"] == "/models"
    assert captured["kwargs"]["env"]["PYTHONUNBUFFERED"] == "1"
    assert captured["timeout"] == 30
    assert captured["kwargs"]["env"]["VTUBER_REQUIRE_CUDA"] == "1"
    assert observed == [
        ("gpu_inference", "running", "TripoSR CUDA 프로세스 시작"),
        ("triposr_output", "log", "TripoSR 시작: CUDA 필수, CPU 폴백 금지"),
        ("triposr_output", "log", "loading TripoSR model"),
        ("triposr_output", "log", "GPU inference started"),
        ("triposr_output", "log", "mesh saved"),
        ("gpu_inference", "complete", "TripoSR 종료 코드 0"),
    ]


def test_outside_colab_ui_preserves_existing_subprocess_run_contract(monkeypatch):
    seen = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        seen["kwargs"] = kwargs
        return reconstruction.subprocess.CompletedProcess(
            cmd, 0, stdout="ok", stderr="",
        )

    monkeypatch.setattr(reconstruction.subprocess, "run", fake_run)
    result = reconstruction._run_triposr_with_diagnostics(
        ["python", "run.py"], timeout=17,
        cwd="/triposr", env={},
    )
    assert result.returncode == 0
    assert seen["kwargs"] == {
        "capture_output": True,
        "text": True,
        "timeout": 17,
        "cwd": "/triposr",
        "env": {},
    }


def test_carriage_return_only_gpu_progress_is_forwarded_before_process_exit(monkeypatch):
    observed = []

    class FakePopen:
        def __init__(self, cmd, **kwargs):
            # GPU libraries often report progress with CR and no newline.
            self.stdout = io.StringIO("load 10%\rload 65%\rload 100%\r")

        def wait(self, timeout):
            return 0

    monkeypatch.setattr(reconstruction.subprocess, "Popen", FakePopen)
    with stage_reporter(lambda name, status, detail: observed.append((name, status, detail))):
        result = reconstruction._run_triposr_with_diagnostics(
            ["python", "run.py"], timeout=5, cwd="/models", env={},
        )
    assert result.returncode == 0
    messages = [detail for name, status, detail in observed if name == "triposr_output"]
    assert messages[-3:] == ["load 10%", "load 65%", "load 100%"]
