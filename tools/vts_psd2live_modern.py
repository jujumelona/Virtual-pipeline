"""Optional official PSD2Live v3.6.0 CLI backend with native artifact validation.

The v3.3.1 custom-budget Gradle launcher is NOT reused here. The 3.6
standalone app has a different project/editor/MCP lifecycle. Run the official
Gradle run --args command against an independently pinned checkout;
never silently replace the production v3.3.1 installation.
"""
from __future__ import annotations

import os
from pathlib import Path
import shlex
import subprocess

PSD2LIVE_MODERN_REF = "v3.6.0"
PSD2LIVE_MODERN_URL = "https://github.com/tsunehimatoi/psd2live.git"


def _modern_root(override: Path | None) -> Path:
    return Path(override or os.environ.get("VTS_PSD2LIVE_MODERN_HOME")
                or "/content/vtuber_builder/third_party/psd2live-v3.6.0").expanduser().resolve()


def ensure_modern_psd2live(root: Path | None = None, *,
                          clone: bool = False) -> Path:
    """Verify checkout tag. Cloning is explicit; never modify an existing tree."""
    root = _modern_root(root)
    if not (root / "gradlew").is_file():
        if not clone:
            raise RuntimeError(
                "PSD2LIVE_MODERN_SOURCE_MISSING: provide --modern-root or "
                "VTS_PSD2LIVE_MODERN_HOME; checkout v3.6.0 separately")
        if root.exists() and any(root.iterdir()):
            raise RuntimeError("PSD2LIVE_MODERN_NONEMPTY_DIRECTORY: " + str(root))
        from tools.vts_subprocess import run_logged
        root.parent.mkdir(parents=True, exist_ok=True)
        rc = run_logged(["git", "clone", "--depth", "1", "--branch",
                         PSD2LIVE_MODERN_REF, PSD2LIVE_MODERN_URL, str(root)],
                        cwd=root.parent, timeout_seconds=600,
                        log_path=root.parent / "modern_psd2live_clone.log")
        if rc:
            raise RuntimeError("PSD2LIVE_MODERN_CLONE_FAILED: " + str(rc))
    if not (root / "gradlew").is_file() or not (root / "mcp_proxy.py").is_file():
        raise RuntimeError("PSD2LIVE_MODERN_CHECKOUT_INCOMPLETE")
    from tools.vts_reference_keyform_author import _require_mcp_cli
    _require_mcp_cli(root)
    if not (root / ".git").exists():
        raise RuntimeError("PSD2LIVE_MODERN_PROVENANCE_MISSING: expected git checkout")
    tag = subprocess.run(["git", "-C", str(root), "describe",
                          "--tags", "--exact-match", "HEAD"],
                         capture_output=True, text=True, timeout=15, check=False)
    if tag.returncode or tag.stdout.strip() != PSD2LIVE_MODERN_REF:
        raise RuntimeError("PSD2LIVE_MODERN_TAG_MISMATCH: required v3.6.0")
    return root


def run_modern_psd2live(psd: Path, output: Path, *, edition: str,
                        source: Path | None = None, clone: bool = False,
                        runner=None, timeout_seconds: int = 7200) -> dict:
    """Use modern official CLI, then prove actual MOC3/CMO3 and atlas references."""
    from tools.vts_psd2live import _java_env, _git_revision
    from tools.vts_psd2live import validate_psd2live_output
    if edition not in {"free", "pro"}:
        raise ValueError("Invalid Cubism edition")
    psd = Path(psd).resolve(strict=True)
    if psd.suffix.lower() != ".psd" or psd.stat().st_size < 26:
        raise ValueError("Modern PSD2Live requires real layered PSD input")
    output = Path(output).resolve()
    if output == psd.parent or output.is_relative_to(psd.parent):
        raise ValueError("Native output must not overlap source PSD")
    if output.exists() and any(output.iterdir()):
        raise RuntimeError("PSD2LIVE_MODERN_OUTPUT_NOT_EMPTY")
    root = ensure_modern_psd2live(source, clone=clone)
    env = _java_env()
    atlas_size = 2048 if edition == "free" else 4096
    arguments = (f"--input {shlex.quote(str(psd))} "
                 f"--output {shlex.quote(str(output))} --atlas {atlas_size}")
    command = [str(root / "gradlew"), "--no-daemon", "run",
               "--args=" + arguments]
    from tools.vts_subprocess import run_logged
    output.mkdir(parents=True, exist_ok=True)
    log = output.parent / "psd2live_modern_cli.log"
    execute = runner or run_logged
    rc = execute(command, cwd=root, env=env, log_path=log,
                 timeout_seconds=timeout_seconds)
    if rc:
        raise RuntimeError("PSD2LIVE_MODERN_CLI_FAILED: " + str(log))
    checked = validate_psd2live_output(output, edition=edition)
    checked.update({
        "backend": "psd2live-modern-official",
        "version_ref": PSD2LIVE_MODERN_REF,
        "commit": _git_revision(root),
        "license": "GPL-3.0",
        "source": PSD2LIVE_MODERN_URL,
        "native_moc3_render_verified": False,
        "vts_tracking_verified": False,
        "artistic_quality_verified": False,
        "atlas_quality": "unmeasured",
        "rig_options": {
            "atlas_target": atlas_size,
            "atlas_texture_limits_checked": True,
            "mesh_structure_upgrade_available_via_mcp": True,
        },
        "log": str(log),
    })
    return checked


def main() -> None:
    import argparse
    import json
    parser = argparse.ArgumentParser()
    parser.add_argument("--psd", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--edition", choices=("free", "pro"), default="pro")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--clone", action="store_true")
    args = parser.parse_args()
    result = run_modern_psd2live(
        args.psd, args.output, edition=args.edition,
        source=args.source, clone=args.clone)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
