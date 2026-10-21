"""Editable project creation must reflect real MCP commits and disk artifacts."""
from contextlib import contextmanager
from pathlib import Path
import pytest


class Editor:
    def __init__(self, path, *, real_commit=True):
        self.path = path
        self.calls = []
        self.real_commit = real_commit

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def project(self):
        self.calls.append(("workspace_inspect", {}))
        return {"state": "st1", "project_id": "test-project"}

    def edit(self, op, **args):
        self.calls.append((op, args))
        if op == "project_import_psd":
            return {"state": "st2", "project_id": "loaded-project",
                    "layers": [{"id": "source-layer"}]}
        if op == "rig_generate":
            return {"state": "st3" if self.real_commit else None}
        raise AssertionError(op)

    def call(self, op, args):
        self.calls.append((op, args))
        assert op == "project_save_as"
        path = Path(args["path"])
        path.write_bytes(b"PSD2LIVE_EDITOR_ARCHIVE" * 60)
        return {"state": "st4"}, []


def _setup(tmp_path, monkeypatch):
    from tools import vts_modern_editable_project as mod
    root = tmp_path / "source"
    root.mkdir()
    (root / "mcp_proxy.py").write_text("def _cli(args):\n    return 0\n")
    monkeypatch.setattr(mod, "ensure_modern_psd2live",
                        lambda source=None, clone=False: root)

    @contextmanager
    def fake_server(root, path, **kwargs):
        path.mkdir(parents=True)
        yield "http://127.0.0.1:23871/mcp", "temporary", path / "headless.log"

    monkeypatch.setattr(mod, "_serve_local_mcp", fake_server)
    psd_dir = tmp_path / "art"
    psd_dir.mkdir()
    psd = psd_dir / "avatar.psd"
    psd.write_bytes(b"8BPS" + b"x" * 100)
    return mod, root, psd


def test_import_rig_save_actual_separate_project(tmp_path, monkeypatch):
    mod, root, psd = _setup(tmp_path, monkeypatch)
    editor = Editor(tmp_path)
    receipt = mod.build_editable_project(
        psd, tmp_path / "out",
        connect=lambda proxy, endpoint, token: editor)
    assert receipt["saved_project_produced"]
    assert receipt["initial_imported_layers"] == 1
    assert Path(receipt["editable_project"]).is_file()
    assert [step[0] for step in editor.calls] == [
        "workspace_inspect", "project_import_psd", "rig_generate",
        "project_save_as", "workspace_inspect"]
    assert not receipt["actual_vtube_studio_tracking_verified"]


def test_refuse_uncommitted_rig_before_any_save(tmp_path, monkeypatch):
    mod, root, psd = _setup(tmp_path, monkeypatch)
    editor = Editor(tmp_path, real_commit=False)
    with pytest.raises(RuntimeError, match="GENERATION_NOT_COMMITTED"):
        mod.build_editable_project(
            psd, tmp_path / "out",
            connect=lambda proxy, endpoint, token: editor)
    assert not any(name == "project_save_as" for name, _ in editor.calls)


def test_refuse_output_below_source_dir(tmp_path, monkeypatch):
    mod, root, psd = _setup(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="overlap"):
        mod.build_editable_project(psd, psd.parent / "out")
