"""Stream child output without ever losing the requested wall-clock deadline.

The prior for-line-in-stdout loops never checked timeouts when a child hung
without printing a newline. This runner applies the timeout from a supervising
thread, retains full logs, and kills the child process group on POSIX.
"""
from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path
from queue import Empty, Queue
import os
import signal
import subprocess
import threading
import time

try:
    from .model_log_output import is_weight_progress, quiet_model_environment
except ImportError:  # Direct invocation from tools/ during Colab setup.
    from model_log_output import is_weight_progress, quiet_model_environment


def run_logged(command, *, cwd=None, env=None, log_path=None,
               timeout_seconds: float = 3600.0) -> int:
    """Return a real exit code; raise TimeoutError for silent or noisy hangs.

    A subprocess may spawn CUDA helpers. On POSIX, kill the isolated child
    process group rather than merely the parent to avoid leaked GPU workers.
    """
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    cmd = list(map(str, command))
    if not cmd:
        raise ValueError("empty command")
    if log_path is not None:
        path = Path(log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        writer = path.open("w", encoding="utf-8")
    else:
        writer = nullcontext()
    deadline = time.monotonic() + timeout_seconds
    with writer as output:
        proc = subprocess.Popen(
            cmd, cwd=cwd, env=quiet_model_environment(env),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            bufsize=1, start_new_session=(os.name == "posix"),
        )
        # Prevent bursty model output from filling the supervisor's RAM.
        lines: Queue[str | None] = Queue(maxsize=256)

        def drain():
            try:
                assert proc.stdout is not None
                for line in proc.stdout:
                    lines.put(line)
            finally:
                lines.put(None)

        thread = threading.Thread(target=drain, daemon=True)
        thread.start()
        try:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(
                        f"Process exceeded wall-clock timeout {timeout_seconds}s: {cmd}"
                    )
                try:
                    line = lines.get(timeout=min(0.5, remaining))
                except Empty:
                    continue
                if line is None:
                    break
                # Weight progress bars can redraw hundreds of times per load.
                # Preserve all diagnostics and ordinary lines unchanged.
                if is_weight_progress(line):
                    continue
                if output is not None:
                    output.write(line)
                    output.flush()
                print(line, end="", flush=True)
            # Do not let the process remain running after stdout closes.
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(
                    f"Process exceeded wall-clock timeout {timeout_seconds}s: {cmd}"
                )
            return proc.wait(timeout=remaining)
        except BaseException:
            if proc.poll() is None:
                if os.name == "posix":
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                else:
                    proc.kill()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
            raise
        finally:
            if proc.stdout is not None:
                proc.stdout.close()
