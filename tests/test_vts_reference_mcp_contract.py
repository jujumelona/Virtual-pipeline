"""Exercise the actual upstream mcp_proxy.py CLI business-request envelope.

Fake executable responses test adapter state discipline, not real graphics.
"""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.vts_reference_keyform_author import (
    _run_mcp, apply_reference_keyforms,
)


def _proxy(root):
    root.mkdir(parents=True)
    (root / "mcp_proxy.py").write_text("# fake proxy path for adapter tests\n")
    return root


def _reply(data, *, exit_code=0):
    return SimpleNamespace(returncode=exit_code, stdout=json.dumps(data), stderr="")


def test_proxy_cli_sends_bare_business_fields(tmp_path):
    proxy = _proxy(tmp_path / "psd2live")
    observed = []
    def executor(cmd, **kwargs):
        assert cmd[2:4] == ["call", "rig_deform"]
        data = json.loads(Path(cmd[4][1:]).read_text())
        observed.append(data)
        assert data == {"changes": [{"target": "warp:real", "key": {"ParamAngleX": 45},
                                      "operations": [{"type": "translate", "delta": [0.01, 0]}]}]}
        return _reply({"state": "new-state", "applied": 1})
    _run_mcp(proxy, "rig_deform", {"changes": [{
        "target": "warp:real", "key": {"ParamAngleX": 45},
        "operations": [{"type": "translate", "delta": [0.01, 0]}],
    }]}, tmp_path / "work", executor)
    assert len(observed) == 1


def test_proxy_rejects_double_request_envelope(tmp_path):
    proxy = _proxy(tmp_path / "psd2live")
    with pytest.raises(ValueError, match="nested request"):
        _run_mcp(proxy, "rig_deform", {"request": {"changes": []}},
                 tmp_path / "work")


@pytest.mark.parametrize("result,exit_code", [
    ({}, 1), ({"error": {"code": "invalid_edit"}}, 0),
    ({"status": "queued"}, 0), ({"status": "failed"}, 0),
])
def test_proxy_does_not_fake_completed_job(tmp_path, result, exit_code):
    proxy = _proxy(tmp_path / "psd2live")
    with pytest.raises(RuntimeError, match="PSD2Live MCP failed"):
        _run_mcp(proxy, "rig_deform", {"changes": [{"target": "warp:x"}]},
                 tmp_path / "work",
                 lambda cmd, **kwargs: _reply(result, exit_code=exit_code))


def test_reference_editor_preview_save_export_uses_real_tool_shapes(tmp_path, monkeypatch):
    proxy = _proxy(tmp_path / "psd2live")
    operations = []
    def executor(cmd, **kwargs):
        op = cmd[3]
        business = json.loads(Path(cmd[4][1:]).read_text())
        assert "request" not in business
        operations.append(op)
        if op == "project_save_as":
            assert business["path"].endswith("reference_authoring_copy.psd2live")
            Path(business["path"]).write_bytes(b"saved-test-copy")
            return _reply({"state": "saved-state"})
        if op == "workspace_preview_edits":
            assert len(business["edits"]) == 1
            assert business["edits"][0]["operation"] == "rig_deform"
            assert "changes" in business["edits"][0]["request"]
            return _reply({"dry_run": True, "would_commit": True})
        if op == "rig_deform":
            assert len(business["changes"]) == 1
            return _reply({"state": "modified-state"})
        if op == "project_save":
            assert business == {}
            return _reply({"state": "saved-state"})
        if op == "project_export_model":
            target = Path(business["output_directory"])
            target.mkdir(parents=True)
            (target / "avatar.model3.json").write_text("{}")
            return _reply({"status": "completed"})
        raise AssertionError("Unexpected MCP operation " + op)

    import tools.vts_multiview_runtime as runtime
    monkeypatch.setattr(runtime, "render_actual_native_moc3",
                        lambda model3, output: {"pose_activity_passed": True})
    plan = {
        "schema": "vtuber/native-keyform-reference-edits-v1",
        "canvas": [512, 512],
        "views": [], "changes": [{
            "target": "warp:real-face",
            "key": {"ParamAngleX": 45},
            "operations": [{"type": "translate", "delta": [0.02, 0]}],
        }],
    }
    receipt = apply_reference_keyforms(
        plan, proxy_root=proxy, work=tmp_path / "authoring",
        export_to=tmp_path / "model-output", executor=executor)
    assert operations == ["project_save_as", "workspace_preview_edits",
                          "rig_deform", "project_save", "project_export_model"]
    assert receipt["reference_angles_used_as_rig_keyforms"] is True
    assert receipt["full_90_degree_profile_verified"] is False


def test_reference_editor_rejects_nonchanging_preview(tmp_path):
    proxy = _proxy(tmp_path / "psd2live")
    def executor(cmd, **kwargs):
        op = cmd[3]
        business = json.loads(Path(cmd[4][1:]).read_text())
        if op == "project_save_as":
            Path(business["path"]).write_bytes(b"saved-test-copy")
            return _reply({"state": "saved-state"})
        if op == "workspace_preview_edits":
            return _reply({"dry_run": True, "would_commit": False})
        raise AssertionError("Writer must stop after failed preview")
    plan = {"schema": "vtuber/native-keyform-reference-edits-v1",
            "changes": [{"target": "warp:one"}]}
    with pytest.raises(RuntimeError, match="did not confirm"):
        apply_reference_keyforms(
            plan, proxy_root=proxy, work=tmp_path / "authoring",
            export_to=tmp_path / "model-output", executor=executor)
