"""Create REAL editable PSD2Live v3.6 project from independently painted PSD.

Run the official headless PSD2Live MCP server and drive its actual operations.
No fake CMO3->PSD2Live conversion or post hoc JSON synthesis. A complete
PSD2Live archive is saved only after source import and native rig generation.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import importlib.util
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import time

from tools.vts_psd2live_modern import ensure_modern_psd2live


def _external_client(proxy_path: Path, endpoint: str, token: str):
    spec = importlib.util.spec_from_file_location(
        "upstream_psd2live_mcp_client", str(proxy_path))
    if spec is None or spec.loader is None:
        raise RuntimeError("PSD2LIVE_MCP_PROXY_PYTHON_LOAD_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Client(endpoint=endpoint, token=token, timeout=120)


@contextmanager
def _serve_local_mcp(root: Path, output: Path, *, timeout_seconds: int = 360):
    output.mkdir(parents=True, exist_ok=True)
    # The port is reserved only until the child binds. The endpoint itself
    # is bound to loopback and still protected by an ephemeral local token.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    token = secrets.token_urlsafe(36)
    log = output / "headless_mcp.log"
    store = output / "headless_store"
    command = [
        str(root / "gradlew"), "--no-daemon", "run",
        "--args=mcp --port " + str(port) +
        " --token " + token + " --store " + str(store) +
        " --profile core",
    ]
    # stdout redirected: a failed Gradle build must leave a persistent
    # diagnostic, not hang indefinitely on a full pipe.
    with log.open("w", encoding="utf-8") as stream:
        proc = subprocess.Popen(
            command, cwd=root, stdout=stream, stderr=subprocess.STDOUT,
            start_new_session=True)
        try:
            deadline = time.monotonic() + timeout_seconds
            while time.monotonic() < deadline:
                if proc.poll() is not None:
                    raise RuntimeError("PSD2LIVE_HEADLESS_MCP_EXITED: " + str(log))
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=1):
                        break
                except OSError:
                    time.sleep(0.4)
            else:
                raise RuntimeError("PSD2LIVE_HEADLESS_MCP_TIMEOUT: " + str(log))
            yield ("http://127.0.0.1:" + str(port) + "/mcp", token, log)
        finally:
            # Terminate the whole Gradle/JVM process group on POSIX to avoid
            # leaving a stale editor session that can mutate future jobs.
            import signal
            if proc.poll() is None:
                try:
                    os.killpg(proc.pid, signal.SIGTERM)
                except (ProcessLookupError, PermissionError):
                    proc.terminate()
                try:
                    proc.wait(timeout=12)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except (ProcessLookupError, PermissionError):
                        proc.kill()
                    proc.wait(timeout=5)


def build_editable_project(psd: Path, output: Path, *, source: Path | None = None,
                           clone: bool = False,
                           connect=None) -> dict:
    """Import actual layers, generate native rig, save project through v3.6 MCP."""
    psd = Path(psd).expanduser().resolve(strict=True)
    if psd.suffix.lower() != ".psd" or psd.stat().st_size < 26:
        raise ValueError("PSD2LIVE_EDITABLE_SOURCE_MUST_BE_REAL_PSD")
    output = Path(output).expanduser().resolve()
    if output.is_relative_to(psd.parent):
        raise ValueError("Editable project directory must not overlap source PSD")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Editable project output must be a fresh directory")
    root = ensure_modern_psd2live(source, clone=clone)
    output.mkdir(parents=True, exist_ok=True)
    editable = output / (psd.stem + ".psd2live")
    with _serve_local_mcp(root, output / "mcp") as (endpoint, token, log):
        connection = connect or _external_client
        client = connection(root / "mcp_proxy.py", endpoint, token)
        with client as editor:
            inspection = editor.project()
            if not inspection.get("state"):
                raise RuntimeError("PSD2Live MCP project inspection missing state")
            imported = editor.edit("project_import_psd", path=str(psd))
            if not imported.get("project_id") or not imported.get("state"):
                raise RuntimeError("PSD2LIVE_SOURCE_IMPORT_NOT_COMMITTED")
            generated = editor.edit("rig_generate")
            if not generated.get("state"):
                raise RuntimeError("PSD2LIVE_NATIVE_RIG_GENERATION_NOT_COMMITTED")
            saved = editor.call("project_save_as",
                                {"path": str(editable)})[0]
            if not editable.is_file() or editable.stat().st_size < 1024:
                raise RuntimeError("PSD2LIVE_EDITABLE_PROJECT_NOT_SAVED")
            after = editor.project()
            if not after.get("state") or not after.get("project_id"):
                raise RuntimeError("PSD2LIVE_PROJECT_NOT_CURRENTLY_LOADED")
            report = {
                "schema": "vtuber/psd2live-v360-headless-editable-project-v1",
                "version": "v3.6.0",
                "source_psd": str(psd),
                "editable_project": str(editable),
                "source_imported": True,
                "rig_generate_committed": True,
                "saved_project_produced": True,
                "project_id": after["project_id"],
                "initial_imported_layers": len(imported.get("layers", [])),
                "native_keyform_quality_verified": False,
                "actual_vtube_studio_tracking_verified": False,
                "artistic_quality_verified": False,
                "headless_mcp_log": str(log),
            }
            (output / "editable_project_report.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2),
                encoding="utf-8")
    return report


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--psd", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--source", type=Path)
    p.add_argument("--clone", action="store_true")
    args = p.parse_args()
    print(json.dumps(build_editable_project(
        args.psd, args.output, source=args.source, clone=args.clone),
        ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
