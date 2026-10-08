"""Run one heavy model in its own subprocess and verify on-disk outputs."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import subprocess
import threading
import time

def _paths(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key.endswith(("_png", "_json", "_obj", "_glb", "_path", "_dir")) and isinstance(item, str):
                yield item
            elif isinstance(item, (list, dict)):
                yield from _paths(item)
    elif isinstance(value, list):
        for item in value:
            yield from _paths(item)

def run_stage(*, worker: str, request_json: str, result_json: str,
              executable: str, cwd: str, timeout_sec: int) -> dict:
    if timeout_sec <= 0:
        raise ValueError("timeout_sec must be positive")
    request = Path(request_json).resolve()
    result = Path(result_json).resolve()
    if not request.is_file():
        raise FileNotFoundError(request)
    result.parent.mkdir(parents=True, exist_ok=True)
    result.unlink(missing_ok=True)  # reject stale output
    command = [executable, "-u", worker, str(request), str(result)]
    proc = subprocess.Popen(command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, bufsize=1, start_new_session=(os.name != "nt"))
    log_path = result.with_suffix(".log")
    def collect():
        with log_path.open("w", encoding="utf-8") as log:
            if proc.stdout:
                for line in proc.stdout:
                    log.write(line)
                    log.flush()
                    print("[model]", line.rstrip(), flush=True)
    thread = threading.Thread(target=collect, daemon=True)
    thread.start()
    try:
        exit_code = proc.wait(timeout=timeout_sec)
    except subprocess.TimeoutExpired as exc:
        if os.name != "nt":
            import signal
            os.killpg(proc.pid, signal.SIGKILL)
        else:
            proc.kill()
        proc.wait(timeout=10)
        raise RuntimeError("model stage timed out: " + worker) from exc
    finally:
        thread.join(timeout=10)
    if exit_code:
        raise RuntimeError("model stage failed: " + worker + " exit=" + str(exit_code)
                           + "; see " + str(log_path))
    if not result.is_file():
        raise RuntimeError("worker did not write result JSON: " + worker)
    data = json.loads(result.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("status") != "complete":
        raise RuntimeError("model worker failed: " + str(data.get("error") if isinstance(data, dict) else data))
    for path in _paths(data):
        if not Path(path).exists():
            raise RuntimeError("model worker returned missing artifact: " + path)
    record = {"worker": worker, "request_sha256": hashlib.sha256(request.read_bytes()).hexdigest(),
              "result_json": str(result), "checked_at": int(time.time()), "artifacts": list(_paths(data))}
    result.with_suffix(".stage.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    return data
