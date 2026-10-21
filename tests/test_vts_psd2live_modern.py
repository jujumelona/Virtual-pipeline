"""The modern CLI is separate from legacy bridge and must prove output files."""
from pathlib import Path
import subprocess
import pytest


def _source(tmp_path):
    root = tmp_path / "external_v360"
    root.mkdir()
    (root / "gradlew").write_text("#!/bin/sh\n")
    (root / "mcp_proxy.py").write_text("def _cli(args):\n    return 0\n")
    for cmd in (["git", "init", "-q"], ["git", "config", "user.name", "Fixture"],
                ["git", "config", "user.email", "fixture@example.org"],
                ["git", "add", "."], ["git", "commit", "-qm", "fixture"],
                ["git", "tag", "v3.6.0"]):
        subprocess.run(cmd, cwd=root, check=True)
    return root


def test_modern_checkout_proves_tag_and_new_proxy(tmp_path):
    from tools.vts_psd2live_modern import ensure_modern_psd2live
    root = _source(tmp_path)
    assert ensure_modern_psd2live(root) == root
    subprocess.run(["git", "tag", "-d", "v3.6.0"], cwd=root,
                   capture_output=True, check=True)
    with pytest.raises(RuntimeError, match="PSD2LIVE_MODERN_TAG_MISMATCH"):
        ensure_modern_psd2live(root)


def test_modern_cli_no_legacy_launcher_and_structural_validation(tmp_path, monkeypatch):
    from tools.vts_psd2live_modern import run_modern_psd2live
    import tools.vts_psd2live as legacy
    root = _source(tmp_path)
    psd = tmp_path / "source.psd"
    psd.write_bytes(b"8BPS" + b"0" * 100)
    monkeypatch.setattr(legacy, "_java_env", lambda: {})
    validated = []
    def validator(folder, *, edition):
        validated.append((folder, edition))
        return {"files": [], "model3_json": str(folder / "example.model3.json")}
    monkeypatch.setattr(legacy, "validate_psd2live_output", validator)
    commands = []
    def runner(cmd, *, cwd, env, log_path, timeout_seconds):
        commands.append((cmd, cwd))
        return 0
    out = tmp_path / "result"
    result = run_modern_psd2live(psd, out, edition="free",
                                source=root, runner=runner)
    assert len(commands) == 1
    args, cwd = commands[0]
    assert args[1:3] == ["--no-daemon", "run"]
    assert "--args=" in args[3]
    assert "--input" in args[3] and "--output" in args[3]
    assert "vtsRig" not in str(args)
    assert cwd == root
    assert validated == [(out, "free")]
    assert result["backend"] == "psd2live-modern-official"
    assert result["version_ref"] == "v3.6.0"
    assert not result["artistic_quality_verified"]


def test_modern_refuses_reusing_existing_output(tmp_path):
    from tools.vts_psd2live_modern import run_modern_psd2live
    root = _source(tmp_path)
    psd = tmp_path / "source.psd"
    psd.write_bytes(b"8BPS" + b"0" * 100)
    out = tmp_path / "output"
    out.mkdir()
    (out / "stale.model3.json").write_text("{}")
    with pytest.raises(RuntimeError, match="PSD2LIVE_MODERN_OUTPUT_NOT_EMPTY"):
        run_modern_psd2live(psd, out, edition="pro", source=root)


def test_modern_rejects_legacy_profile_retry(tmp_path):
    from tools.vts_psd2live import rig_existing_artwork_zip
    with pytest.raises(ValueError, match="PSD2LIVE_MODERN_REPAIR_USES_MCP"):
        rig_existing_artwork_zip(tmp_path / "no-artwork.zip", tmp_path / "out",
                                 edition="free", auto_repair=True, backend="modern")
