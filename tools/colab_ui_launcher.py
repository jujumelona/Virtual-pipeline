"""Start the Gradio UI in a clean Python process after Colab pip installs.

Only standard-library modules are imported in the notebook kernel. This is
essential: a Colab kernel may retain pre-install NumPy native modules even when
pip has replaced NumPy/SciPy wheels on disk.
"""

from __future__ import annotations

import os
import pathlib
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

REPO = pathlib.Path(__file__).resolve().parents[1]
WORK = pathlib.Path("/content/vtuber_builder")
PID_PATH = WORK / "ui_server.pid"
LOG_PATH = WORK / "logs" / "gradio_server.log"
STARTUP_TIMEOUT_SECONDS = 120


def _fresh_python_abi_check() -> None:
    """Check compiled NumPy/SciPy imports before allocating a Gradio port."""
    subprocess.run(
        [sys.executable, "-u", str(REPO / "tools" / "runtime_abi_probe.py")],
        cwd=str(REPO),
        check=True,
        timeout=120,
    )


def _stop_prior_ui() -> None:
    """Stop only a UI process started by our launcher; never kill the kernel."""
    if not PID_PATH.is_file():
        return
    try:
        pid = int(PID_PATH.read_text(encoding="utf-8").strip())
        command = pathlib.Path(f"/proc/{pid}/cmdline").read_bytes()
        if (
            pid > 1
            and pid != os.getpid()
            and str(REPO / "tools" / "colab_app.py").encode() in command
        ):
            os.kill(pid, signal.SIGTERM)
            for _ in range(30):
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    break
                time.sleep(0.1)
        PID_PATH.unlink(missing_ok=True)
    except (OSError, ValueError):
        PID_PATH.unlink(missing_ok=True)


def _open_unused_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_http(port: int, process: subprocess.Popen, timeout: int) -> None:
    deadline = time.monotonic() + timeout
    url = f"http://127.0.0.1:{port}/"
    while time.monotonic() < deadline:
        code = process.poll()
        if code is not None:
            tail = LOG_PATH.read_text(encoding="utf-8", errors="replace")[-12000:]
            raise RuntimeError(
                f"Gradio server exited before startup (exit={code}).\\n"
                f"{tail}\\nFull server log: {LOG_PATH}"
            )
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except (OSError, urllib.error.URLError, TimeoutError):
            pass
        time.sleep(0.5)
    process.terminate()
    tail = LOG_PATH.read_text(encoding="utf-8", errors="replace")[-12000:]
    raise RuntimeError(
        f"Gradio server did not start within {timeout}s.\\n"
        f"{tail}\\nFull server log: {LOG_PATH}"
    )


def main() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    # If the kernel holds pre-install NumPy/SciPy .so modules, they are never
    # inherited by this fresh subprocess. Fail fast on a bad *disk* install.
    _fresh_python_abi_check()
    _stop_prior_ui()
    port = _open_unused_port()
    environment = os.environ.copy()
    environment.pop("VTUBER_SETUP_ONLY", None)
    environment["VTUBER_COLAB_EXTERNAL_IFRAME"] = "1"
    environment["VTUBER_COLAB_SERVER_PORT"] = str(port)
    environment["PYTHONUNBUFFERED"] = "1"
    with LOG_PATH.open("w", encoding="utf-8") as logfile:
        process = subprocess.Popen(
            [sys.executable, "-u", str(REPO / "tools" / "colab_app.py")],
            cwd=str(REPO),
            env=environment,
            stdout=logfile,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    PID_PATH.write_text(str(process.pid) + "\n", encoding="utf-8")
    try:
        _wait_for_http(port, process, STARTUP_TIMEOUT_SECONDS)
    except Exception:
        PID_PATH.unlink(missing_ok=True)
        raise

    # Colab's native authenticated local-port iframe. The kernel does not
    # import Gradio, torch, trimesh, NumPy, or SciPy.
    from google.colab import output

    print(f"UI server PID={process.pid}, port={port}", flush=True)
    print(f"Server log: {LOG_PATH}", flush=True)
    output.serve_kernel_port_as_iframe(port, height="1100")


if __name__ == "__main__":
    main()
