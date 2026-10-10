"""Keep native PSD and model libraries outside the notebook kernel."""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import sys
import time


def memory_snapshot():
    """Best-effort host and cgroup evidence; SIGKILL alone does not prove OOM."""
    snapshot = {}
    for name, path in {
        "process": "/proc/self/status", "host": "/proc/meminfo",
        "cgroup_events": "/sys/fs/cgroup/memory.events",
        "cgroup_current": "/sys/fs/cgroup/memory.current",
        "cgroup_max": "/sys/fs/cgroup/memory.max",
    }.items():
        try:
            text = Path(path).read_text()
            if name == "process":
                text = "\n".join(x for x in text.splitlines() if x.startswith(("Vm", "Rss")))
            elif name == "host":
                text = "\n".join(x for x in text.splitlines() if x.startswith(("MemTotal:", "MemAvailable:", "SwapFree:")))
            snapshot[name] = text.strip()
        except OSError as exc:
            snapshot[name] = str(exc)
    return snapshot


def _save(path, data):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def supervise_handoff(command, output: Path, *, timeout_seconds=21600):
    from tools.vts_subprocess import run_logged
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    result_path = output / "handoff_result.json"
    result_path.unlink(missing_ok=True)
    failure_path = output / "vts_process_failure.json"
    failure_path.unlink(missing_ok=True)
    log_path = output / "logs" / "handoff_process.log"
    status_path = output / "vts_process_status.json"
    evidence = {
        "event": "VTS_PROCESS_START", "supervisor_pid": os.getpid(),
        "python_executable": sys.executable, "command": list(map(str, command)),
        "log_path": str(log_path), "memory_before": memory_snapshot(),
        "started_at": time.time(), "timeout_seconds": timeout_seconds,
    }
    _save(status_path, evidence)
    print("[VTS] VTS_PROCESS_START: " + json.dumps(evidence), flush=True)
    returncode = None
    try:
        returncode = run_logged(command, cwd=Path(__file__).resolve().parents[1],
                                env={**os.environ, "PYTHONFAULTHANDLER": "1"},
                                log_path=log_path, timeout_seconds=timeout_seconds)
        if returncode != 0:
            signal_name = signal.Signals(-returncode).name if returncode < 0 else None
            raise RuntimeError(f"VTS child failed: returncode={returncode} signal={signal_name}; log={log_path}")
        if not result_path.is_file():
            raise RuntimeError(f"VTS child exited without a result manifest: {result_path}")
        result = json.loads(result_path.read_text(encoding="utf-8"))
        if result.get("state") != "artwork_ready_editor_rig_required" or not Path(result.get("package", "")).is_file():
            raise RuntimeError("VTS child returned an invalid result manifest or missing package")
    except BaseException as exc:
        last_psd_step = None
        if log_path.is_file():
            with log_path.open(encoding="utf-8", errors="replace") as stream:
                for line in stream:
                    if line.startswith("[VTS] PSD_NATIVE_STEP: "):
                        try:
                            last_psd_step = json.loads(line.split(": ", 1)[1])
                        except ValueError:
                            pass
        failure = {**evidence, "event": "VTS_PROCESS_FAIL", "error": str(exc),
                   "error_type": type(exc).__name__, "returncode": returncode,
                   "signal": signal.Signals(-returncode).name if returncode is not None and returncode < 0 else None,
                   "memory_after": memory_snapshot(), "finished_at": time.time(),
                   "failure_log": str(failure_path), "last_psd_step": last_psd_step}
        _save(failure_path, failure)
        _save(status_path, failure)
        print("[VTS] VTS_PROCESS_FAIL: " + json.dumps(failure), flush=True)
        # Preserve the original failure before probing. Each probe gets a
        # fresh interpreter, so one native fault cannot suppress the others.
        # No See-through/GPU models are loaded or rerun during diagnosis.
        if last_psd_step is not None and returncode is not None and returncode < 0:
            try:
                from tools.vts_psd_diagnose import diagnose_psd_runtime
                failure['psd_diagnosis'] = diagnose_psd_runtime(output / 'logs' / 'psd_diagnosis')
            except Exception as diagnostic_error:
                failure['psd_diagnosis_error'] = str(diagnostic_error)
            _save(failure_path, failure)
            _save(status_path, failure)
        raise
    result["process_log"] = str(log_path)
    _save(status_path, {**evidence, "event": "VTS_PROCESS_PASS", "returncode": returncode,
                        "memory_after": memory_snapshot(), "finished_at": time.time()})
    print("[VTS] VTS_PROCESS_PASS: " + json.dumps({"returncode": returncode, "log_path": str(log_path)}), flush=True)
    return result


def make_cubism_handoff_isolated(master, output, *, timeout_seconds=21600, **options):
    """Fresh interpreter, streamed logs and fatal-signal supervision."""
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    paths = {"reference_image", "external_psd", "generated_psd", "third_party"}
    request = {"master": str(Path(master).resolve()), "output": str(output),
               "options": {key: str(Path(value).resolve()) if key in paths and value is not None
                           else value for key, value in options.items()}}
    request_path = output / "handoff_request.json"
    _save(request_path, request)
    return supervise_handoff(
        [sys.executable, "-X", "faulthandler", "-u", "-m", "tools.vts_handoff_worker",
         "--request", str(request_path)], output, timeout_seconds=timeout_seconds)
