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


def test_production_runner_uses_namespace_tsr_source_in_real_runpy(
    tmp_path, monkeypatch,
):
    """Replicate actual Colab CLI wrapper + run.py instead of direct import."""
    import sys
    import pathlib
    import vtuber_pipeline.avatar.triposr_runner as runner

    root = tmp_path / "PinnedTripoSR"
    (root / "tsr").mkdir(parents=True)
    # Official pinned repo has NO tsr/__init__.py (namespace package).
    (root / "tsr" / "system.py").write_text(
        "CHECKPOINT_MARKER = 'system-imported'\n",
        encoding="utf-8",
    )
    result_path = tmp_path / "resolved"
    (root / "run.py").write_text(
        "from tsr.system import CHECKPOINT_MARKER\n"
        f"from pathlib import Path; Path({str(result_path)!r}).write_text(CHECKPOINT_MARKER)\n",
        encoding="utf-8",
    )
    import vtuber_pipeline.avatar.marching_cubes_backend as marching
    monkeypatch.setattr(marching, "install_triposr_marching_cubes", lambda: None)
    monkeypatch.setattr(runner, "_install_hf_revision_guard", lambda: None)
    monkeypatch.setattr(
        sys, "argv", ["triposr_runner.py", str(root / "run.py"), "--no-remove-bg"]
    )
    # Validate actual runpy semantics with no root on sys.path in advance.
    assert str(root) not in sys.path
    original = list(sys.path)
    try:
        runner.main()
        assert result_path.read_text() == "system-imported"
        assert sys.path[0] == str(root)
    finally:
        sys.path[:] = original
        for name in ("tsr", "tsr.system"):
            sys.modules.pop(name, None)


def test_runtime_error_text_does_not_blame_gpu_for_module_not_found():
    import subprocess
    from vtuber_pipeline.avatar.reconstruction import (
        _describe_triposr_process_failure,
    )

    output = (
        "[GPU] CUDA 사용 가능: True\n[GPU] 장치: Tesla T4\n"
        "Traceback (most recent call last):\n"
        "ModuleNotFoundError: No module named 'tsr'\n"
    )
    error = _describe_triposr_process_failure(
        subprocess.CompletedProcess(["python", "run.py"], 1, "", output)
    )
    assert "Python dependency/import error" in error
    assert "No module named 'tsr'" in error
    assert "GPU unavailability" not in error
    assert "CUDA inference error" not in error


def test_actual_cuda_out_of_memory_still_classified_as_gpu_failure():
    import subprocess
    from vtuber_pipeline.avatar.reconstruction import (
        _describe_triposr_process_failure,
    )

    output = "[GPU] CUDA 사용 가능: True\ntorch.OutOfMemoryError: CUDA out of memory\n"
    error = _describe_triposr_process_failure(
        subprocess.CompletedProcess(["python", "run.py"], 1, "", output)
    )
    assert "CUDA inference error" in error
