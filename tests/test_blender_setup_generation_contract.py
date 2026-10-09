"""Blender VRM is installed and operator-validated during setup, never generation."""
from pathlib import Path
import pytest
from tools.setup_blender_runtime import require_blender_runtime_ready


def test_generation_refuses_unverified_configured_binary(tmp_path, monkeypatch):
    binary=tmp_path/"blender"
    binary.write_bytes(b"fake")
    monkeypatch.setenv("VTUBER_BLENDER_BINARY",str(binary))
    monkeypatch.delenv("VTUBER_BLENDER_VERIFIED_BINARY",raising=False)
    with pytest.raises(RuntimeError,match="workflow setup"):
        require_blender_runtime_ready()


def test_generation_accepts_only_exact_verified_binary(tmp_path, monkeypatch):
    binary=tmp_path/"blender"
    binary.write_bytes(b"fake")
    monkeypatch.setenv("VTUBER_BLENDER_BINARY",str(binary))
    monkeypatch.setenv("VTUBER_BLENDER_VERIFIED_BINARY",str(binary))
    assert require_blender_runtime_ready()==str(binary)
    binary.unlink()
    with pytest.raises(FileNotFoundError):
        require_blender_runtime_ready()


def test_generation_callsite_does_not_install_or_verify_blender():
    source=(Path(__file__).resolve().parents[1]/"tools"/"colab_app.py").read_text(encoding="utf-8")
    block=source.split("def build_avatar_ui(",1)[1].split("def _normalize_file_value",1)[0]
    assert "require_blender_runtime_ready()" in block
    assert "ensure_blender_runtime(" not in block
    selected=source.split("def choose_workflow(",1)[1].split("def return_to_workflow_choice",1)[0]
    assert '3D Blender VRM operator verification' in selected
    assert 'ensure_blender_runtime(' in selected
