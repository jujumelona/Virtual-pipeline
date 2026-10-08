"""Regression tests for the post-install Colab NumPy/SciPy process boundary."""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import types

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _launcher():
    spec = importlib.util.spec_from_file_location(
        "colab_isolated_launcher", ROOT / "tools" / "colab_ui_launcher.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_server_launcher_does_not_load_native_dependencies_into_notebook():
    source = (ROOT / "tools" / "colab_ui_launcher.py").read_text(
        encoding="utf-8"
    )
    import ast

    tree = ast.parse(source)
    imports = [
        name.name.split(".")[0]
        for node in tree.body
        if isinstance(node, ast.Import)
        for name in node.names
    ]
    assert not ({"numpy", "scipy", "torch", "trimesh", "gradio"} & set(imports))
    assert "serve_kernel_port_as_iframe" in source
    assert "VTUBER_COLAB_EXTERNAL_IFRAME" in source
    assert "runtime_abi_probe.py" in source

    probe = (ROOT / "tools" / "runtime_abi_probe.py").read_text(encoding="utf-8")
    assert "from scipy.spatial import cKDTree" in probe
    assert "from scipy.sparse import csr_matrix" in probe
    assert "numpy.testing" in probe


def test_main_spawns_fresh_python_with_live_colab_iframe(tmp_path, monkeypatch):
    launcher = _launcher()
    launcher.WORK = tmp_path
    launcher.PID_PATH = tmp_path / "ui.pid"
    launcher.LOG_PATH = tmp_path / "logs" / "ui.log"

    events = []
    monkeypatch.setattr(
        launcher, "_fresh_python_abi_check",
        lambda: events.append("fresh_abi_probe"),
    )
    monkeypatch.setattr(launcher, "_stop_prior_ui", lambda: events.append("stop_old"))
    monkeypatch.setattr(launcher, "_open_unused_port", lambda: 19876)

    class Process:
        pid = 12345

    def fake_popen(args, **kwargs):
        events.append(("popen", args, kwargs))
        return Process()

    monkeypatch.setattr(launcher.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(
        launcher,
        "_wait_for_http",
        lambda port, process, timeout: events.append(("ready", port, timeout)),
    )
    monkeypatch.setattr(
        launcher, "_follow_server",
        lambda process: events.append(("follow", process.pid)),
    )

    output = types.ModuleType("google.colab.output")
    output.serve_kernel_port_as_iframe = (
        lambda port, **kwargs: events.append(("iframe", port, kwargs))
    )
    colab = types.ModuleType("google.colab")
    colab.output = output
    google = types.ModuleType("google")
    google.colab = colab
    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.colab", colab)
    monkeypatch.setitem(sys.modules, "google.colab.output", output)

    launcher.main()

    assert events[0:2] == ["fresh_abi_probe", "stop_old"]
    action, args, kwargs = events[2]
    assert action == "popen"
    assert args == [
        sys.executable, "-u", str(ROOT / "tools" / "colab_app.py")
    ]
    assert kwargs["start_new_session"] is True
    assert kwargs["env"]["VTUBER_COLAB_EXTERNAL_IFRAME"] == "1"
    assert kwargs["env"]["VTUBER_COLAB_SERVER_PORT"] == "19876"
    assert kwargs["stderr"] == launcher.subprocess.STDOUT
    assert events[3] == ("ready", 19876, launcher.STARTUP_TIMEOUT_SECONDS)
    assert events[4] == ("iframe", 19876, {"height": "1100"})
    assert events[5] == ("follow", 12345)
    assert launcher.PID_PATH.read_text(encoding="utf-8").strip() == "12345"


def test_failed_fresh_server_shows_captured_traceback(tmp_path, monkeypatch):
    launcher = _launcher()
    launcher.LOG_PATH = tmp_path / "server.log"
    launcher.LOG_PATH.write_text(
        "AttributeError: module 'numpy._core._multiarray_umath' "
        "has no attribute '_blas_supports_fpe'",
        encoding="utf-8",
    )

    class Crashed:
        def poll(self):
            return 1

    with pytest.raises(RuntimeError, match="_blas_supports_fpe"):
        launcher._wait_for_http(19876, Crashed(), timeout=10)


def test_abi_probe_uses_fresh_subprocess_with_timeout(monkeypatch):
    launcher = _launcher()
    calls = []
    monkeypatch.setattr(
        launcher.subprocess, "run",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    launcher._fresh_python_abi_check()
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args[0][-1].endswith("tools/runtime_abi_probe.py")
    assert kwargs["check"] is True
    assert kwargs["timeout"] == 120


def test_follow_server_keeps_cell_running_until_process_really_exits(
    tmp_path, monkeypatch, capsys,
):
    launcher = _launcher()
    launcher.PID_PATH = tmp_path / "ui.pid"
    launcher.PID_PATH.write_text("4321", encoding="utf-8")
    launcher.LOG_PATH = tmp_path / "ui.log"
    launcher.LOG_PATH.write_text(
        "model inference started\nModuleNotFoundError: No module named 'tsr'\n",
        encoding="utf-8",
    )
    states = [None, None, None, 1]

    class Server:
        pid = 4321

        def poll(self):
            return states.pop(0)

    sleeps = []
    monkeypatch.setattr(launcher.time, "sleep", lambda seconds: sleeps.append(seconds))
    with pytest.raises(RuntimeError, match="No module named 'tsr'") as exc:
        launcher._follow_server(Server())

    assert "exit=1" in str(exc.value)
    assert "Full server log:" in str(exc.value)
    assert sleeps == [2, 2, 2]  # The cell did NOT return while server was live
    assert not launcher.PID_PATH.exists()
    assert "서버 실행 중" in capsys.readouterr().out


def test_follow_server_cell_interrupt_terminates_server_cleanly(
    tmp_path, monkeypatch,
):
    launcher = _launcher()
    launcher.PID_PATH = tmp_path / "ui.pid"
    launcher.PID_PATH.write_text("4321", encoding="utf-8")
    events = []

    class Server:
        pid = 4321

        def poll(self):
            raise KeyboardInterrupt()

        def terminate(self):
            events.append("terminate")

        def wait(self, timeout):
            events.append(("wait", timeout))

    launcher._follow_server(Server())
    assert events == ["terminate", ("wait", 10)]
    assert not launcher.PID_PATH.exists()
