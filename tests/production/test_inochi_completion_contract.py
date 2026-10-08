"""Only SDK-authored, animated/physical INP2 outputs can be declared complete."""
import json

import pytest

from vtuber_pipeline.common.completion import validate_build_result
from vtuber_pipeline.common.schemas import BuildResult
from vtuber_pipeline.two_d.inochi_bridge import INP2_MAGIC


def _result(tmp_path):
    return BuildResult("inochi2d", "complete", str(tmp_path / "avatar.inp"),
                       None, str(tmp_path))


def test_renamed_image_cannot_be_a_complete_inp(tmp_path):
    (tmp_path / "avatar.inp").write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 200)
    with pytest.raises(ValueError, match="native INP2 header"):
        validate_build_result(_result(tmp_path))


def test_sdk_signature_alone_does_not_prove_a_functioning_puppet(tmp_path):
    (tmp_path / "avatar.inp").write_bytes(INP2_MAGIC + b"0" * 200)
    with pytest.raises(ValueError, match="native SDK exporter"):
        validate_build_result(_result(tmp_path))
    (tmp_path / "native_export_report.json").write_text(json.dumps({
        "sdk_native_write": True, "mesh_vertices_count": 100,
        "bound_keyforms_count": 0, "physics_bindings_count": 2,
    }))
    with pytest.raises(ValueError, match="meshes, keyforms, or physics"):
        validate_build_result(_result(tmp_path))
