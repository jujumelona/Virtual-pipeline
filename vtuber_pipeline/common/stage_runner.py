"""Serial model processes with bounded lifetime and content-verified resume."""
from collections import deque
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import threading
import tempfile
import time
from contextlib import contextmanager
import fcntl
def cgroup_memory_diagnostics() -> dict:
    """Read kernel OOM counters to distinguish SIGKILL from a guessed OOM."""
    root = Path("/sys/fs/cgroup")
    result = {}
    for name in ("memory.current", "memory.max", "memory.peak"):
        try:
            raw = (root / name).read_text(encoding="ascii").strip()
            result[name] = int(raw) if raw != "max" else raw
        except (OSError, ValueError):
            pass
    try:
        for line in (root / "memory.events").read_text(encoding="ascii").splitlines():
            key, value = line.split()
            if key in {"oom", "oom_kill", "max", "high"}:
                result["events." + key] = int(value)
    except (OSError, ValueError):
        pass
    return result


def cgroup_oom_summary(before: dict, after: dict) -> str:
    old = int(before.get("events.oom_kill", 0))
    new = int(after.get("events.oom_kill", 0))
    delta = new - old
    summary = f"cgroup_oom_kill_delta={delta} "
    limit = after.get("memory.max")
    peak = after.get("memory.peak")
    if isinstance(limit, int):
        summary += f"cgroup_limit_mib={limit//1048576} "
    if isinstance(peak, int):
        summary += f"cgroup_peak_mib={peak//1048576} "
    summary += ("kernel_oom_confirmed" if delta > 0 else
                "SIGKILL_cause_unconfirmed")
    return summary


def write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False))
    temporary.replace(path)

_GPU_LOCK = threading.Lock()


@contextmanager
def _process_gpu_lock(timeout_sec: int):
    """Serialize GPU workers across independent Colab/Python processes.

    A thread lock alone cannot prevent two concurrently launched notebook
    kernels from loading full-sized model weights onto the same T4.
    """
    lock_file = Path(os.environ.get(
        "VTUBER_GPU_STAGE_LOCK",
        str(Path(tempfile.gettempdir()) / "vtuber_pipeline_gpu_stage.lock"),
    )).expanduser()
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_sec
    with lock_file.open("a+") as handle:
        while True:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise RuntimeError(
                        f"model worker GPU lock timed out after {timeout_sec}s: {lock_file}"
                    )
                time.sleep(0.25)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _hash_inputs(value):
    if isinstance(value, dict):
        return {k: _hash_inputs(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_hash_inputs(v) for v in value]
    if isinstance(value, str) and Path(value).is_file():
        return {'path': value, 'sha256': sha256(value)}
    return value


def _paths(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key.endswith(("_png", "_json", "_obj", "_glb", "_npy", "_npz", "_path", "_dir")) and isinstance(item, str):
                yield item
            elif isinstance(item, (list, dict)):
                yield from _paths(item)
    elif isinstance(value, list):
        for item in value:
            yield from _paths(item)


def _outputs(result, cwd):
    if result.get('status') != 'complete':
        raise RuntimeError(f"worker failed: {result.get('error', 'missing complete status')}")
    paths = list(_paths(result))
    if not paths:
        raise RuntimeError('stage did not declare any output artifacts')
    hashes = {}
    pending = list(paths)
    seen = set()
    while pending:
        name = pending.pop()
        path = (Path(cwd) / name).resolve()
        if path in seen:
            continue
        seen.add(path)
        if path.is_dir():
            children = list(path.rglob('*'))
            files = [p for p in children if p.is_file()]
            if not files:
                raise RuntimeError(f'empty artifact directory: {path}')
            pending.extend(str(p) for p in files)
            continue
        if not path.is_file() or not path.stat().st_size:
            raise RuntimeError(f'missing or empty artifact: {path}')
        hashes[str(path)] = sha256(path)
        if path.suffix == '.json':
            data = json.loads(path.read_text())
            pending.extend(_paths(data))
    return hashes


def run_stage(*, worker: str, request_json: str, result_json: str,
              executable: str, cwd: str, timeout_sec: int) -> dict:
    if timeout_sec <= 0:
        raise ValueError('timeout_sec must be positive')
    worker = str(Path(worker).resolve())
    request_json = str(Path(request_json).resolve())
    result_path = Path(result_json).resolve()
    provenance = result_path.with_suffix(result_path.suffix + '.provenance.json')
    request = json.loads(Path(request_json).read_text())
    identity = {'request': _hash_inputs(request), 'worker_sha256': sha256(worker),
                'executable': str(Path(executable).resolve()), 'cwd': str(Path(cwd).resolve())}
    fingerprint = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    result_path.parent.mkdir(parents=True, exist_ok=True)
    # If a cached face-gate skipped the prewarmed first model, it must NOT
    # monopolize the GPU lock while another model stage needs CUDA.
    # A real face-gate uses its resident worker directly, not run_stage().
    if os.environ.get("VTUBER_GENERATION_WORKER") == "1":
        from tools.colab_gpu_warmup import available_face_worker, stop_face_worker

        if available_face_worker():
            print("[gpu-handoff] face gate skipped or cached; "
                  "unload unused resident detector before next GPU worker",
                  flush=True)
            stop_face_worker()
    with _GPU_LOCK, _process_gpu_lock(timeout_sec):
        if provenance.is_file() and result_path.is_file():
            try:
                old = json.loads(provenance.read_text())
                result = json.loads(result_path.read_text())
                if old['fingerprint'] == fingerprint and _outputs(result, cwd) == old['outputs']:
                    return result
            except (ValueError, KeyError, OSError, RuntimeError):
                pass
        result_path.unlink(missing_ok=True)
        provenance.unlink(missing_ok=True)
        from vtuber_pipeline.common.model_log_output import is_weight_progress, quiet_model_environment
        log_path = result_path.with_suffix('.log')
        tail = deque(maxlen=30)
        memory_before = cgroup_memory_diagnostics()
        with log_path.open('w') as log:
            process = subprocess.Popen([executable, '-u', worker, request_json, str(result_path)], cwd=cwd,
                                       env=quiet_model_environment(),
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       text=True, errors='replace', start_new_session=True)
            def stream():
                for line in process.stdout:
                    if is_weight_progress(line):
                        continue
                    log.write(line); log.flush(); tail.append(line)
                    print(f'[{Path(worker).stem}] {line}', end='', flush=True)
            reader = threading.Thread(target=stream, daemon=True)
            reader.start()
            try:
                status = process.wait(timeout=timeout_sec)
            except BaseException as exc:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=10)
                reader.join(timeout=10)
                result_path.unlink(missing_ok=True)
                if isinstance(exc, subprocess.TimeoutExpired):
                    raise RuntimeError(f'{worker}: timed out after {timeout_sec}s; log={log_path}') from exc
                raise
            reader.join(timeout=10)
            # No descendant may hold GPU allocations after this stage finishes.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            reader.join(timeout=2)
        if status:
            # The worker wrote structured traceback to result.json. Never
            # delete it or replace that root cause with the last TensorFlow
            # startup lines from stdout (those are often unrelated noise).
            structured = ""
            if result_path.is_file():
                try:
                    failure = json.loads(result_path.read_text(encoding="utf-8"))
                    structured = str(failure.get("traceback") or failure.get("error") or "")
                except (ValueError, OSError):
                    structured = ""
            message = structured or "".join(tail)
            oom_detail = (
                cgroup_oom_summary(memory_before, cgroup_memory_diagnostics())
                if status == -signal.SIGKILL else ""
            )
            print(f"[stage failure] {worker}: exit={status} "
                  f"{oom_detail}\n{message}", flush=True)
            raise RuntimeError(
                f"{worker}: exit={status}; {oom_detail}; log={log_path}; "
                f"worker_error_json={result_path}\n{message}"
            )
        if not result_path.is_file():
            raise RuntimeError(f'{worker}: missing result JSON')
        result = json.loads(result_path.read_text())
        if result.get('error'):
            raise RuntimeError(f'{worker}: {result["error"]}')
        outputs = _outputs(result, cwd)
        write_json(result_path, result)
        write_json(provenance, {'fingerprint': fingerprint, 'identity': identity, 'outputs': outputs})
        return result
