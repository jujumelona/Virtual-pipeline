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
import uuid
import urllib.error
import urllib.request

REPO = pathlib.Path(__file__).resolve().parents[1]
# The notebook invokes this file via runpy rather than importing a package.
# Ensure the standard-library-only delivery module resolves in that kernel.
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
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


def _show_direct_download(port: int, file_path: str) -> None:
    """Show a clickable authenticated Gradio file URL without files.download().

    Colab files.download can block forever while printing 'Downloading ...'.
    Colab's documented proxyPort JS gives the correct per-session URL, the
    same mechanism used for the embedded Gradio iframe. The link remains
    clickable even when automatic browser navigation/download is blocked.
    """
    import json
    from IPython.display import Javascript, display
    from tools.colab_download_contract import gradio_file_route, save_latest_avatar

    path = pathlib.Path(file_path).resolve(strict=True)
    output_root = WORK / "output"
    stable = save_latest_avatar(path, output_root, WORK / "avatar.vrm")
    route = gradio_file_route(path, output_root)
    print(f"[VRM] 생성 파일: {path}", flush=True)
    print(f"[VRM] 고정 복사본: {stable} (Colab 왼쪽 파일 탐색기에서도 접근)", flush=True)
    print(f"[VRM] 서버 다운로드 경로: {route}", flush=True)

    script = """(async (port, fileRoute, element) => {
      const root = document.createElement('div');
      root.style.padding = '12px';
      root.style.border = '1px solid #999';
      root.style.margin = '8px 0';
      const heading = document.createElement('strong');
      heading.textContent = 'avatar.vrm 생성 완료 — 직접 다운로드';
      root.appendChild(heading);
      root.appendChild(document.createElement('br'));
      const link = document.createElement('a');
      link.textContent = '↓ avatar.vrm 다운로드 (직접 HTTP 링크)';
      link.download = 'avatar.vrm';
      link.style.cssText = 'display:inline-block;margin-top:8px;padding:8px 12px;background:#e0e0e0;color:#101010;border-radius:5px;';
      root.appendChild(link);
      element.appendChild(root);
      try {
        const proxyUrl = await google.colab.kernel.proxyPort(port);
        const href = new URL(fileRoute, proxyUrl).toString();
        link.href = href;
        link.target = '_blank';
        link.rel = 'noopener';
        // Best-effort only: browsers can block programmatic clicks.
        // A real user click on this visible link is the reliable fallback.
        link.click();
      } catch (error) {
        const warning = document.createElement('span');
        warning.textContent = ' 다운로드 URL 생성 실패: ' + error;
        root.appendChild(warning);
      }
    })""" + f"({port}, {json.dumps(route)}, window.element)"
    display(Javascript(script))


def _follow_server(
    process: subprocess.Popen, *, download_dir: pathlib.Path | None = None,
    server_port: int | None = None,
) -> None:
    """Keep Colab's third cell active for the ENTIRE Gradio server lifetime.

    Colab's iframe helper returns immediately. Previously the cell completed
    even while a generation was running in the detached UI process. The kernel
    must remain blocked here without importing NumPy, SciPy or torch.
    """
    print(
        "[UI] 서버 실행 중 — 이 셀은 Avatar 생성 중에도 종료되지 않습니다. "
        "중지하려면 셀 실행을 중단하세요.",
        flush=True,
    )
    next_heartbeat = time.monotonic() + 60
    try:
        while True:
            if download_dir is not None:
                # This runs IN the Colab notebook kernel, not inside Gradio.
                # The kernel is the owner of the authenticated browser download.
                from tools.colab_download_contract import consume_avatar_downloads

                def show_file(path: str) -> None:
                    if server_port is None:
                        raise RuntimeError("Cannot generate a download link without Gradio port")
                    _show_direct_download(server_port, path)

                outcomes = consume_avatar_downloads(
                    download_dir, WORK / "output", show_file,
                )
                for outcome in outcomes:
                    if outcome["status"] == "requested":
                        print(
                            "[VRM] 파일 직접 다운로드 링크 표시됨. 브라우저가 자동 다운로드를 "
                            "차단하면 출력된 링크를 클릭하세요. ③ 셀은 계속 실행됩니다.",
                            flush=True,
                        )
                    else:
                        print(
                            "[VRM] 직접 다운로드 링크 생성 실패: "
                            + outcome["detail"]
                            + f" · Colab 파일 탐색기: {WORK / 'output'}",
                            flush=True,
                        )
            code = process.poll()
            if code is not None:
                PID_PATH.unlink(missing_ok=True)
                tail = (
                    LOG_PATH.read_text(encoding="utf-8", errors="replace")[-12000:]
                    if LOG_PATH.is_file() else "(server log missing)"
                )
                raise RuntimeError(
                    f"Gradio UI server exited (exit={code}).\\n"
                    f"{tail}\\nFull server log: {LOG_PATH}"
                )
            now = time.monotonic()
            if now >= next_heartbeat:
                print(
                    f"[UI] server alive PID={process.pid} · "
                    f"full log: {LOG_PATH}",
                    flush=True,
                )
                next_heartbeat = now + 60
            time.sleep(2)
    except KeyboardInterrupt:
        print("[UI] 셀 중단 요청 — UI 서버 종료", flush=True)
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
        PID_PATH.unlink(missing_ok=True)


def main() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    # If the kernel holds pre-install NumPy/SciPy .so modules, they are never
    # inherited by this fresh subprocess. Fail fast on a bad *disk* install.
    _fresh_python_abi_check()
    _stop_prior_ui()
    port = _open_unused_port()
    # Per-UI-run event directory prevents old avatar artifacts from launching
    # an unexpected download in a newly started notebook session.
    download_dir = WORK / "download_events" / uuid.uuid4().hex
    download_dir.mkdir(parents=True, exist_ok=False)
    environment = os.environ.copy()
    environment.pop("VTUBER_SETUP_ONLY", None)
    environment["VTUBER_COLAB_EXTERNAL_IFRAME"] = "1"
    environment["VTUBER_COLAB_SERVER_PORT"] = str(port)
    environment["VTUBER_COLAB_AUTODOWNLOAD_DIR"] = str(download_dir)
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
    # serve_kernel_port_as_iframe() returns immediately. Do NOT let the
    # notebook finish while the server or its model inference is still alive.
    print("[VRM] 생성 성공 시 직접 HTTP 다운로드 링크와 고정 파일 경로를 표시합니다.", flush=True)
    _follow_server(process, download_dir=download_dir, server_port=port)


if __name__ == "__main__":
    main()
