"""SDK-authored textured and physically deformed INP1/INP2 only.

These CPU tests reject both renamed PNGs and fabricated SDK reports.
Actual SDK generation and reimport are separately verified on DUB CI.
"""
import json
import struct
import pytest

from vtuber_pipeline.common.completion import validate_build_result
from vtuber_pipeline.common.schemas import BuildResult
from vtuber_pipeline.two_d.inochi_bridge import INP1_MAGIC, INP2_MAGIC


def _result(tmp_path):
    return BuildResult("inochi2d", "complete", str(tmp_path / "avatar.inp"),
                       None, str(tmp_path))


def _structural_sample(tmp_path):
    # Frame enough of the official 0.8 INP1 format to test the evidence gate,
    # not to pretend this is a working model or replace native SDK inference.
    doc = json.dumps({
        "nodes": {"type": "Node", "children": [
            {"type": "Part", "children": []},
            {"type": "SimplePhysics", "children": []},
        ]},
        "param": [{"name": "physics.hair.front.sway",
                   "bindings": [{"node": 101, "param_name": "deform"}]}],
    }).encode("utf-8")
    blob = (INP1_MAGIC + struct.pack(">I", len(doc)) + doc +
            b"TEX_SECT" + struct.pack(">I", 1) +
            struct.pack(">I", 12) + b"\x01" + b"X" * 12)
    (tmp_path / "avatar.inp").write_bytes(blob)


def test_renamed_image_cannot_be_a_complete_inp(tmp_path):
    (tmp_path / "avatar.inp").write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 200)
    with pytest.raises(ValueError, match="SDK-native INP puppet"):
        validate_build_result(_result(tmp_path))


def test_signature_alone_does_not_prove_functioning_puppet(tmp_path):
    (tmp_path / "avatar.inp").write_bytes(INP2_MAGIC + b"0" * 200)
    with pytest.raises(ValueError, match="SDK-native INP puppet"):
        validate_build_result(_result(tmp_path))


def test_valid_wire_envelope_still_requires_native_sdk_evidence(tmp_path):
    _structural_sample(tmp_path)
    with pytest.raises(ValueError, match="native SDK exporter"):
        validate_build_result(_result(tmp_path))
    (tmp_path / "native_export_report.json").write_text(json.dumps({
        "sdk_native_write": True, "sdk_roundtrip_read": True,
        "sdk_reimport_binding_count": 0, "mesh_vertices_count": 100,
        "bound_keyforms_count": 0, "physics_bindings_count": 2,
        "inp_format": "INP1",
    }))
    with pytest.raises(ValueError, match="verified meshes, keyforms, or physics"):
        validate_build_result(_result(tmp_path))
