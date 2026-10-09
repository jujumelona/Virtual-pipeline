"""Durable, bounded launcher for GPU generation detached from the Gradio server.

Keep the request, live log and final result on disk. A killed/OOM model worker
reports a failed job instead of killing the ASGI process; a UI restart does not
delete an already running detached job or its output files.
"""
from __future__ import annotations

from collections import deque
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
WORK = Path("/content/vtuber_builder")
EVENT_PREFIX = "VTUBER_GENERATION_EVENT "
MAX_SECONDS = 6 * 60 * 60


def _json_input(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_json_input(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _json_input(v) for k, v in value.items()}
    path = getattr(value, "name", None)
    if isinstance(path, str):
        return path
    raise TypeError(f"Unsupported production input type: {type(value).__name__}")


def run_isolated(
    mode: str, args: tuple | list, *,
    on_event: Callable[[tuple], None] | None = None,
    root: Path | None = None,
    timeout: int = MAX_SECONDS,
) -> tuple:
    """Run one production process; stream progress and retain full logs.

    stdout is a file, not a pipe, so a notebook/UI server restart cannot send
    BrokenPipeError into a detached running model worker. Never import torch,
    Gradio, GPU libraries or production code into the supervising process.
    """
    if mode not in {"inochi2d", "live2d", "avatar", "accessory"}:
        raise ValueError(f"Unsupported generation mode: {mode!r}")
    if timeout <= 0:
        raise ValueError("Production timeout must be positive")
    job_root = Path(root) if root is not None else WORK / "jobs"
    folder = job_root / uuid.uuid4().hex
    folder.mkdir(parents=True, exist_ok=False)
    request = folder / "request.json"
    result_path = folder / "result.json"
    log_path = folder / "generation.log"
    request.write_text(json.dumps({"mode": mode, "args": _json_input(list(args))},
                                  ensure_ascii=False), encoding="utf-8")
    cmd = [
        sys.executable, "-u", str(ROOT / "tools" / "colab_generation_worker.py"),
        str(request), str(result_path),
    ]
    env = os.environ.copy()
    env.pop("VTUBER_SETUP_ONLY", None)
    env["PYTHONUNBUFFERED"] = "1"
    # An actual file descriptor, not a pipe back to the possibly dying UI.
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            cmd, cwd=str(ROOT), env=env, stdout=log, stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    (folder / "pid").write_text(str(process.pid), encoding="utf-8")
    (folder / "status.json").write_text(json.dumps({
        "mode": mode, "state": "running", "pid": process.pid,
    }), encoding="utf-8")
    deadline = time.monotonic() + timeout
    cursor = 0
    tail = deque(maxlen=140)

    def relay_line(line: str) -> None:
        tail.append(line)
        if not on_event:
            return
        if line.startswith(EVENT_PREFIX):
            try:
                payload = json.loads(line[len(EVENT_PREFIX):])
            except json.JSONDecodeError:
                on_event(("log", line.rstrip()))
                return
            if payload.get("kind") == "progress":
                on_event(("progress", payload.get("fraction", 0),
                          payload.get("description", "")))
            elif payload.get("kind") == "stage":
                on_event(("stage", payload.get("stage", ""), payload.get("status", ""),
                          payload.get("detail", "")))
            elif payload.get("kind") == "failed":
                on_event(("log", payload.get("error", "")[-1500:]))
        else:
            on_event(("log", line.rstrip()))

    # Do not hold an open pipe or read model weights into the UI process.
    while True:
        if log_path.is_file():
            with log_path.open("r", encoding="utf-8", errors="replace") as stream:
                stream.seek(cursor)
                for line in stream:
                    relay_line(line)
                cursor = stream.tell()
        status = process.poll()
        if status is not None:
            # Drain late buffered output before checking result.json.
            with log_path.open("r", encoding="utf-8", errors="replace") as stream:
                stream.seek(cursor)
                for line in stream:
                    relay_line(line)
            break
        if time.monotonic() > deadline:
            # Stop the whole worker session, including its child model stages.
            import signal
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=10)
            status = -signal.SIGKILL
            break
        time.sleep(0.5)

    if status == 0 and result_path.is_file():
        try:
            payload = json.loads(result_path.read_text(encoding="utf-8"))
            values = payload["result"]
            expected = 4 if mode == "avatar" else 3
            if not isinstance(values, list) or len(values) != expected:
                raise ValueError("Invalid production result contract")
        except (OSError, ValueError, KeyError) as exc:
            status = 1
            tail.append(f"Invalid production output: {exc}")
        else:
            (folder / "status.json").write_text(json.dumps({
                "mode": mode, "state": "complete", "pid": process.pid,
            }), encoding="utf-8")
            return tuple(values)
    (folder / "status.json").write_text(json.dumps({
        "mode": mode, "state": "failed", "pid": process.pid, "exit_code": status,
    }), encoding="utf-8")
    diagnosis = ("Model subprocess was terminated (possible RAM/VRAM OOM)"
                 if status in (-9, 137) else "Model subprocess failed")
    raise RuntimeError(
        f"{diagnosis}; mode={mode}; exit={status}; job={folder}; "
        f"log={log_path}\n" + "".join(tail)[-8000:]
    )
