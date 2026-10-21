"""Texture-aware mesh editing can only pass with actual editor evidence."""
from pathlib import Path
from types import SimpleNamespace
import json
import pytest

from tools.vts_modern_mesh_refiner import refine_texture_meshes, _settings


def _root(path):
    path.mkdir()
    (path / "mcp_proxy.py").write_text("def _cli(arguments):\n    return 0\n")
    return path


def _executor(ops, *, no_guides=False, deny_state=False):
    def run(cmd, **kwargs):
        op = cmd[3]
        data = json.loads(Path(cmd[4][1:]).read_text())
        ops.append((op, data, "--edit" in cmd))
        if op == "project_save_as":
            Path(data["path"]).write_bytes(b"project-from-real-editor-fixture")
            result = {"state": "start"}
        elif op == "layer_mesh_structure_preview":
            assert data["target"] == "mesh:inspected-id"
            assert data["settings"]["fill"] is False
            result = {"lines": [] if no_guides else [
                {"kind": "FOLD", "points": [[0, 0], [100, 100]]}]}
        elif op == "layer_mesh_structure":
            result = {} if deny_state else {"state": "remeshed"}
        elif op == "project_save":
            result = {"state": "saved"}
        elif op == "project_export_model":
            dest = Path(data["output_directory"])
            dest.mkdir(parents=True)
            (dest / "avatar.model3.json").write_text("{}")
            result = {"status": "completed"}
        else:
            raise AssertionError(op)
        return SimpleNamespace(returncode=0, stdout=json.dumps(result), stderr="")
    return run


def _native(model, output):
    assert Path(model).is_file()
    return {"native_pose_geometry_passed": True, "pose_activity_passed": True,
            "native_mouth_interpolation_passed": True,
            "parameter_isolation": {"passed": True}}


def test_v360_texture_structure_actual_mcp_sequence_and_pose(tmp_path):
    ops = []
    result = refine_texture_meshes(
        proxy_root=_root(tmp_path / "source"),
        mesh_targets=["mesh:inspected-id"],
        output=tmp_path / "work",
        executor=_executor(ops), render=_native)
    assert result["status"] == "real_native_remesh_pose_passed"
    assert result["targets"][0]["texture_guides"] == 1
    assert not result["artistic_quality_verified"]
    assert [(x[0], x[2]) for x in ops] == [
        ("project_save_as", False),
        ("layer_mesh_structure_preview", False),
        ("layer_mesh_structure", True),
        ("project_save", False),
        ("project_export_model", True),
    ]


def test_texture_structure_does_not_edit_without_guides(tmp_path):
    ops = []
    with pytest.raises(RuntimeError, match="TEXTURE_MESH_NO_SOURCE_GUIDES"):
        refine_texture_meshes(
            proxy_root=_root(tmp_path / "source"),
            mesh_targets=["mesh:inspected-id"],
            output=tmp_path / "work", executor=_executor(ops, no_guides=True),
            render=_native)
    assert not any(name == "layer_mesh_structure" for name, _, _ in ops)


def test_texture_structure_rejects_no_commit(tmp_path):
    ops = []
    with pytest.raises(RuntimeError, match="TEXTURE_MESH_NOT_COMMITTED"):
        refine_texture_meshes(
            proxy_root=_root(tmp_path / "source"),
            mesh_targets=["mesh:inspected-id"],
            output=tmp_path / "work", executor=_executor(ops, deny_state=True),
            render=_native)


def test_texture_structure_bounds(tmp_path):
    for bad in (float("nan"), 1.1, -0.1):
        with pytest.raises(ValueError, match="SENSITIVITY"):
            _settings(bad, 8, 6000)
    for bad in (0, 16001):
        with pytest.raises(ValueError, match="VERTEX_BUDGET"):
            _settings(0.7, 8, bad)
    from tools.vts_modern_mesh_refiner import refine_texture_meshes
    with pytest.raises(ValueError, match="REAL"):
        refine_texture_meshes(
            proxy_root=_root(tmp_path / "source"),
            mesh_targets=["not-a-real-mesh-id"], output=tmp_path / "out")
