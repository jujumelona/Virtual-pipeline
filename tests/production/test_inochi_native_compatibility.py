"""INP transport checks; actual D SDK round-trip runs in native GitHub workflow.

A forged eight-byte magic value, even with a fake success report, MUST NOT
make a production puppet. These tests never claim an SDK binary was built.
"""
from pathlib import Path
import json
import struct
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
def test_magic_and_forged_native_report_never_satisfy_integrity(
    tmp_path, monkeypatch, fmt, magic,
):
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
    with pytest.raises(ValueError):
        inochi_bridge.export_inp(str(spec), str(tmp_path / "output"))
    assert not (tmp_path / "output" / "avatar.inp").exists()


def test_sdk_diagnostics_reject_unbound_physics(tmp_path, monkeypatch):
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
    with pytest.raises(RuntimeError, match="deformation bindings"):
        inochi_bridge.export_inp(str(spec), str(tmp_path / "output"))
    assert not (tmp_path / "output" / "avatar.inp").exists()


def test_parse_real_inp1_wire_format_requires_texture_and_bound_physics(tmp_path):
    payload = {
        "param": [{"name": "physics.hair.front.sway",
                   "bindings": [{"node": 42, "param_name": "deform"}]}],
        "nodes": {"type": "Node", "children": [
            {"type": "Part", "children": []},
            {"type": "SimplePhysics", "children": []}
        ]},
    }
    raw_json = json.dumps(payload).encode("utf-8")
    texture_data = b"1234567890"
    data = (inochi_bridge.INP1_MAGIC +
            struct.pack(">I", len(raw_json)) + raw_json +
            b"TEX_SECT" + struct.pack(">I", 1) +
            struct.pack(">I", len(texture_data)) + b"\x01" + texture_data)
    output = tmp_path / "sample.inp"
    output.write_bytes(data)
    parsed = inochi_bridge.inspect_native_inp(str(output))
    assert parsed["format"] == "INP1"
    assert parsed["textures"] == 1
    assert parsed["binding_count"] == 1
    assert parsed["physics_drivers"] == 1
    output.write_bytes(data.replace(b"TEX_SECT", b"NOTEXXXX"))
    with pytest.raises(ValueError, match="texture section"):
        inochi_bridge.inspect_native_inp(str(output))
