"""Resident one-shot face detector for overlapping GPU load with CPU downloads.

Download-stage process preloads the pinned YOLO/HRNet detector *once*. The
generation process sends exactly one face-detection request over a local
0600-permission Unix socket. On reply (success or failure) the resident worker
exits, releasing CUDA before the following GPU stage can acquire its lock.

Never spawn a second GPU model in this service. If a Colab runtime disappears,
the socket/ready record is ephemeral and the standard detector path remains
available on reconnect.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

from tools.model_log_output import quiet_model_environment

ROOT = Path(__file__).resolve().parents[1]
WARM_ROOT = Path(os.environ.get("VTUBER_GPU_PREWARM_ROOT",
                                "/content/vtuber_builder/gpu_prewarm"))
READY = WARM_ROOT / "face_ready.json"
SOCKET = WARM_ROOT / "face.sock"


def available_face_worker() -> bool:
    """Check *both* the socket and live resident PID, not a stale marker."""
    try:
        item = json.loads(READY.read_text(encoding="utf-8"))
        pid = int(item["pid"])
        if item.get("state") != "ready" or pid < 2 or not SOCKET.is_socket():
            return False
        os.kill(pid, 0)
        return True
    except (OSError, ValueError, KeyError, TypeError):
        return False


def stop_face_worker() -> None:
    """Release an unused resident face model when switching first GPU stages."""
    try:
        state = json.loads(READY.read_text(encoding="utf-8"))
        pid = int(state["pid"])
        command = Path(f"/proc/{pid}/cmdline").read_bytes()
        # Never kill a PID that has been reused for an unrelated process.
        if pid > 1 and b"colab_gpu_warmup.py" in command and b"--serve" in command:
            try:
                os.killpg(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
    except (OSError, ValueError, TypeError, KeyError):
        pass
    READY.unlink(missing_ok=True)


def start_face_worker(*, timeout: float = 180) -> bool:
    """Spawn once, wait for real CUDA model readiness, return False to fallback."""
    if available_face_worker():
        print("[gpu-prewarm] existing face detector is ready", flush=True)
        return True
    WARM_ROOT.mkdir(parents=True, exist_ok=True)
    READY.unlink(missing_ok=True)
    SOCKET.unlink(missing_ok=True)
    log_path = WARM_ROOT / "face_preload.log"
    # This is a single resident preload attempt, not an ever-growing history.
    with log_path.open("w", encoding="utf-8") as log:
        child = subprocess.Popen(
            [sys.executable, "-u", str(Path(__file__).resolve()), "--serve"],
            cwd=str(ROOT),
            stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
            start_new_session=True,
            env=quiet_model_environment({**os.environ, "VTUBER_GPU_PREWARM_SERVER": "1"}),
        )
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if available_face_worker():
            print(f"[gpu-prewarm] YOLO/HRNet on GPU, resident PID={child.pid}; "
                  "will unload after first face inference", flush=True)
            return True
        if child.poll() is not None:
            break
        time.sleep(0.3)
    if child.poll() is None:
        try:
            os.killpg(child.pid, signal.SIGTERM)
            child.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except OSError:
                pass
    print(f"[gpu-prewarm] not resident; direct detection remains available; "
          f"worker exit={child.poll()} log={log_path}", flush=True)
    return False


def detect_warmed_face(image_path: str, *, timeout: float = 240) -> dict:
    """Send one inference to already resident GPU model; no hidden reloading."""
    if not available_face_worker():
        raise RuntimeError("Face prewarm worker is not ready")
    payload = json.dumps({"image_path": str(Path(image_path).resolve())}).encode()
    if len(payload) > 4096:
        raise ValueError("Face inference request exceeds size limit")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(timeout)
        client.connect(str(SOCKET))
        client.sendall(payload + b"\n")
        with client.makefile("rb") as stream:
            line = stream.readline(1024 * 1024 + 1)
    if not line or len(line) > 1024 * 1024:
        raise RuntimeError("Prewarmed face detector ended without valid response")
    response = json.loads(line)
    if not response.get("ok"):
        raise RuntimeError("Prewarmed face inference failed: "
                           + str(response.get("error", "unknown"))[:2000])
    result = response.get("result")
    if not isinstance(result, dict) or "landmarks" not in result:
        raise RuntimeError("Invalid prewarmed face detector response")
    return result


def _serve_face_once(*, idle_seconds: float = 1200) -> None:
    from vtuber_pipeline.common.stage_runner import _process_gpu_lock
    # The lock persists while the model lives on GPU; all downstream stage
    # workers use the same lock and cannot overlap this resident allocation.
    with _process_gpu_lock(timeout_sec=240):
        from vtuber_pipeline.avatar.face_detector import AnimeFaceDetector
        detector = AnimeFaceDetector()
        WARM_ROOT.mkdir(parents=True, exist_ok=True)
        SOCKET.unlink(missing_ok=True)
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
                server.bind(str(SOCKET))
                SOCKET.chmod(0o600)
                server.listen(1)
                server.settimeout(idle_seconds)
                tmp = READY.with_suffix(".tmp")
                tmp.write_text(json.dumps({
                    "pid": os.getpid(), "state": "ready",
                    "model": "anime_face_yolov3+anime_face_hrnetv2",
                }), encoding="utf-8")
                tmp.replace(READY)
                print("[gpu-prewarm] face detector loaded and listening", flush=True)
                try:
                    connection, _ = server.accept()
                except socket.timeout:
                    print("[gpu-prewarm] idle timeout; unload", flush=True)
                    return
                with connection:
                    connection.settimeout(240)
                    try:
                        request = b""
                        while not request.endswith(b"\n") and len(request) < 4096:
                            chunk = connection.recv(4096)
                            if not chunk:
                                break
                            request += chunk
                        payload = json.loads(request)
                        image = payload.get("image_path")
                        if not isinstance(image, str) or not Path(image).is_file():
                            raise ValueError("Invalid face inference input")
                        result = detector.detect(image)
                        response = {"ok": True, "result": result}
                    except Exception as exc:
                        response = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
                    connection.sendall((json.dumps(response, ensure_ascii=False) + "\n").encode())
        finally:
            READY.unlink(missing_ok=True)
            SOCKET.unlink(missing_ok=True)
            print("[gpu-prewarm] face detector finished; process exiting to free CUDA",
                  flush=True)


if __name__ == "__main__":
    if sys.argv[1:] != ["--serve"]:
        raise SystemExit("Usage: python tools/colab_gpu_warmup.py --serve")
    _serve_face_once()
