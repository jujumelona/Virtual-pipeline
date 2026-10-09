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


def _process_tree_groups(root_pid: int) -> set[int]:
    """Find model grandchildren even when an individual stage used setsid().

    Killing only the top Popen group leaves stage_runner's start_new_session
    model subprocesses on the GPU. The Linux /proc tree is read before
    termination, while ancestry is still available.
    """
    seen = set()
    groups = set()
    pending = [root_pid]
    while pending:
        pid = pending.pop()
        if pid in seen or pid <= 1:
            continue
        seen.add(pid)
        try:
            group = os.getpgid(pid)
            if group != os.getpgrp():
                groups.add(group)
        except ProcessLookupError:
            continue
        tasks = Path(f"/proc/{pid}/task")
        for child_file in tasks.glob("*/children"):
            try:
                pending.extend(int(x) for x in child_file.read_text().split())
            except (OSError, ValueError):
                continue
    return groups


def _terminate_worker_tree(process, signum: int, groups: set[int] | None = None) -> set[int]:
    """Signal all independently sessioned descendant stage workers."""
    import signal
    groups = (groups or set()) | _process_tree_groups(process.pid)
    for pgid in groups:
        try:
            os.killpg(pgid, signum)
        except ProcessLookupError:
            pass
    return groups


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
    tail = deque(maxlen=140)

    def relay_line(line: str) -> None:
        """Deliver every worker stdout/stderr line, including the first error."""
        tail.append(line)
        if on_event is None:
            return
        if line.startswith(EVENT_PREFIX):
            try:
                payload = json.loads(line[len(EVENT_PREFIX):])
            except json.JSONDecodeError:
                on_event(("log", line))
                return
            if payload.get("kind") == "progress":
                on_event(("progress", payload.get("fraction", 0),
                          payload.get("description", "")))
            elif payload.get("kind") == "stage":
                on_event(("stage", payload.get("stage", ""), payload.get("status", ""),
                          payload.get("detail", "")))
            elif payload.get("kind") == "failed":
                on_event(("log", str(payload.get("error", "")) + "\n"))
            elif payload.get("kind") not in {"complete"}:
                on_event(("log", line))
        else:
            on_event(("log", line))


    # Colab's stop/interruption must terminate this exact process group.
    # start_new_session=True otherwise leaves an orphan model running after
    # the notebook cell is stopped.
    try:
        return _await_worker_completion(
            process, mode, folder, log_path, result_path, deadline,
            tail, relay_line,
        )
    except BaseException:
        # _await_worker_completion may already have recorded a regular
        # subprocess failure. Do not overwrite "failed" with "cancelled"
        # unless a notebook interruption caught an *alive* child process.
        if process.poll() is None:
            import signal
            groups = _terminate_worker_tree(process, signal.SIGTERM)
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                pass
            # A stage may ignore SIGTERM and survive after the direct worker
            # exits. Kill the groups discovered before the parent exited.
            _terminate_worker_tree(process, signal.SIGKILL, groups)
            if process.poll() is None:
                process.wait(timeout=10)
            (folder / "status.json").write_text(json.dumps({
                "mode": mode, "state": "cancelled",
                "pid": process.pid, "exit_code": process.returncode,
            }), encoding="utf-8")
        raise


def _await_worker_completion(
    process, mode, folder, log_path, result_path, deadline,
    tail, relay_line,
):
    cursor = 0
    # Do not hold a pipe open to the notebook kernel.
    while True:
        if log_path.is_file():
            with log_path.open("r", encoding="utf-8", errors="replace") as stream:
                stream.seek(cursor)
                while True:
                    line = stream.readline()
                    if not line:
                        break
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
            _terminate_worker_tree(process, signal.SIGKILL)
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
            # A callback may catch a model exception and return an explicit
            # failure status. Preserve that diagnostic in Gradio without
            # incorrectly recording the underlying job as successful.
            failed = str(values[0]).startswith("❌") or " 제작 실패" in str(values[0])
            (folder / "status.json").write_text(json.dumps({
                "mode": mode, "state": "failed" if failed else "complete",
                "pid": process.pid, "callback_status": str(values[0])[:400],
            }, ensure_ascii=False), encoding="utf-8")
            return tuple(values)
    (folder / "status.json").write_text(json.dumps({
        "mode": mode, "state": "failed", "pid": process.pid, "exit_code": status,
    }), encoding="utf-8")
    diagnosis = ("Model subprocess was terminated (possible RAM/VRAM OOM)"
                 if status in (-9, 137) else "Model subprocess failed")
    raise RuntimeError(
        f"{diagnosis}; mode={mode}; exit={status}; job={folder}; "
        f"log={log_path}\n"
        "Every subprocess output line was streamed to the notebook above; "
        "the complete unfiltered transcript is in generation.log."
    )
