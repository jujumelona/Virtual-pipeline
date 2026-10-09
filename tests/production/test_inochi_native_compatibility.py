"""Contract-level checks for actual upstream Inochi SDK writer output formats.

Fake process artifacts here test only the gate. A separate D SDK workflow
compiles and executes the native producer; mocks never demonstrate a rig.
"""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from vtuber_pipeline.two_d import inochi_bridge


def _spec(tmp_path):
    path = tmp_path / "puppet_spec.json"
    path.write_text(json.dumps({
        "textures": ["observed.png"],
        "parts": [{"semantic_id": "hair.front"}],
        "mesh": [{"semantic_id": "hair.front"}],
        "parameters": {"head.angle_x": [-30, 0, 30]},
        "keyforms": [{"semantic_id": "hair.front", "deltas": {}}],
        "physics": [{"semantic_id": "hair.front"}],
        "draw_order": ["hair.front"],
    }))
    binary = tmp_path / "native"
    binary.write_bytes(b"native")
    return path, binary


@pytest.mark.parametrize("fmt,magic", [
    ("INP1", b"TRNSRTS\x00"), ("INP2", b"TRNSRTS2"),
])
def test_only_real_declared_sdk_format_survives_gate(tmp_path, monkeypatch, fmt, magic):
    spec, native = _spec(tmp_path)
    monkeypatch.setenv("VTUBER_INOCHI_NATIVE", str(native))

    def fake_runner(command, *, stdout, stderr, timeout):
        assert command[0] == str(native)
        assert timeout == 900
        Path(command[2]).write_bytes(magic + bytes(256))
        Path(command[3]).write_text(json.dumps({
            "sdk_native_write": True, "sdk_roundtrip_read": True,
            "sdk_reimport_binding_count": 1, "bound_keyforms_count": 3,
            "mesh_vertices_count": 100, "physics_bindings_count": 1,
            "inp_format": fmt, "sdk_version": "0.8.7",
        }))
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(inochi_bridge.subprocess, "run", fake_runner)
    out = inochi_bridge.export_inp(str(spec), str(tmp_path / "output"))
    assert out["inp_format"] == fmt
    assert Path(out["inp"]).read_bytes().startswith(magic)


def test_unbound_or_invalid_native_puppet_is_rejected(tmp_path, monkeypatch):
    spec, native = _spec(tmp_path)
    monkeypatch.setenv("VTUBER_INOCHI_NATIVE", str(native))

    def fake_runner(command, *, stdout, stderr, timeout):
        Path(command[2]).write_bytes(b"TRNSRTS\x00" + bytes(256))
        Path(command[3]).write_text(json.dumps({
            "sdk_native_write": True, "sdk_roundtrip_read": True,
            "sdk_reimport_binding_count": 0, "bound_keyforms_count": 0,
            "mesh_vertices_count": 100, "physics_bindings_count": 1,
            "inp_format": "INP1",
        }))
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(inochi_bridge.subprocess, "run", fake_runner)
    with pytest.raises(RuntimeError, match="not a functional rig"):
        inochi_bridge.export_inp(str(spec), str(tmp_path / "output"))
    assert not (tmp_path / "output" / "avatar.inp").exists()
