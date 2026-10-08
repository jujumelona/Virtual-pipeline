"""Browser delivery contract for avatar.vrm created by the real Gradio worker.

No NumPy, PyTorch or Gradio is required in this test; Colab's notebook kernel
only uses stdlib to poll the server-produced artifact and downloads via the
first-party google.colab.files API.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import types

import pytest

from tools.colab_download_contract import (
    checked_avatar, publish_avatar_download, consume_avatar_downloads,
)


def avatar_fixture(root: Path, body: bytes = b"glTF" + b"\0" * 40) -> Path:
    path = root / "avatar-123" / "avatar.vrm"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return path


def test_only_completed_avatar_vrm_can_trigger_download(tmp_path):
    root = tmp_path / "output"
    root.mkdir()
    queue = tmp_path / "queue"
    assert not list(queue.glob("*")) if queue.is_dir() else True

    file = avatar_fixture(root)
    req = publish_avatar_download(file, root, queue)
    assert req.is_file()
    metadata = json.loads(req.read_text())
    assert metadata["filename"] == "avatar.vrm"
    assert metadata["size"] == file.stat().st_size
    assert len(metadata["sha256"]) == 64
    downloads = []
    outcomes = consume_avatar_downloads(queue, root, downloads.append)
    assert downloads == [str(file)]
    assert [o["status"] for o in outcomes] == ["requested"]
    assert list(queue.glob("request-*.json")) == []
    assert len(list(queue.glob("receipt-*.json"))) == 1
    assert consume_avatar_downloads(queue, root, downloads.append) == []
    assert downloads == [str(file)]


@pytest.mark.parametrize(
    "filename,contents",
    [
        ("avatar.vrm", b"not a VRM"),
        ("output.vrm", b"glTF" + b"0" * 40),
        ("avatar.vrm", b""),
    ],
)
def test_invalid_or_unverified_vrm_never_triggers_browser(tmp_path, filename, contents):
    root = tmp_path / "output"
    root.mkdir()
    target = root / "avatar-1" / filename
    target.parent.mkdir()
    target.write_bytes(contents)
    queue = tmp_path / "queue"
    with pytest.raises(ValueError):
        publish_avatar_download(target, root, queue)
    assert not list(queue.glob("request-*.json")) if queue.is_dir() else True


def test_changed_vrm_after_queueing_does_not_download(tmp_path):
    root = tmp_path / "output"
    root.mkdir()
    file = avatar_fixture(root)
    queue = tmp_path / "queue"
    publish_avatar_download(file, root, queue)
    file.write_bytes(b"glTF" + b"x" * 40)
    called = []
    outcomes = consume_avatar_downloads(queue, root, called.append)
    assert called == []
    assert outcomes[0]["status"] == "error"
    assert "VRM changed" in outcomes[0]["detail"]
    assert file.is_file()  # never delete VRM on transfer failure


def test_colab_download_exception_preserves_vrm_and_logs_failure(tmp_path):
    root = tmp_path / "output"
    root.mkdir()
    file = avatar_fixture(root)
    queue = tmp_path / "queue"
    publish_avatar_download(file, root, queue)

    def blocked(_path):
        raise PermissionError("browser rejected automatic download")

    outcomes = consume_avatar_downloads(queue, root, blocked)
    assert outcomes[0]["status"] == "error"
    assert "browser rejected" in outcomes[0]["detail"]
    assert file.is_file()
    assert not list(queue.glob("request-*.json"))


def test_live_colab_server_watcher_calls_browser_download_while_ui_is_alive(
    tmp_path, monkeypatch, capsys,
):
    import importlib.util

    module_path = Path(__file__).resolve().parents[2] / "tools" / "colab_ui_launcher.py"
    spec = importlib.util.spec_from_file_location("colab_ui_autodownload_test", module_path)
    assert spec is not None and spec.loader is not None
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)
    launcher.WORK = tmp_path
    launcher.PID_PATH = tmp_path / "ui.pid"
    launcher.LOG_PATH = tmp_path / "logs" / "gradio_server.log"
    launcher.LOG_PATH.parent.mkdir(parents=True)
    launcher.LOG_PATH.write_text("ui exited after VRM transfer", encoding="utf-8")
    launcher.PID_PATH.write_text("34567", encoding="utf-8")
    root = tmp_path / "output"
    root.mkdir()
    file = avatar_fixture(root)
    queue = tmp_path / "events"
    publish_avatar_download(file, root, queue)

    calls = []
    colab = types.ModuleType("google.colab")
    files = types.ModuleType("google.colab.files")
    files.download = lambda path: calls.append(path)
    colab.files = files
    google = types.ModuleType("google")
    google.colab = colab
    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.colab", colab)
    monkeypatch.setitem(sys.modules, "google.colab.files", files)
    monkeypatch.setattr(launcher.time, "sleep", lambda _: None)

    class AliveThenExit:
        pid = 34567

        def __init__(self):
            self.count = 0

        def poll(self):
            self.count += 1
            return None if self.count <= 2 else 0

    with pytest.raises(RuntimeError, match="exit=0"):
        launcher._follow_server(AliveThenExit(), download_dir=queue)
    assert calls == [str(file)]
    assert "avatar.vrm 브라우저 자동 다운로드 요청 완료" in capsys.readouterr().out
    assert len(list(queue.glob("receipt-*.json"))) == 1
