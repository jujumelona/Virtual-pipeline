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
    monkeypatch.setattr(
        launcher, "_show_direct_download",
        lambda port, path: calls.append((port, path)),
    )
    # A blocked google.colab.files.download call must never be reached.
    colab = types.ModuleType("google.colab")
    files = types.ModuleType("google.colab.files")
    files.download = lambda path: (_ for _ in ()).throw(
        AssertionError("Colab files.download is no longer supported")
    )
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
        launcher._follow_server(AliveThenExit(), download_dir=queue, server_port=19876)
    assert calls == [(19876, str(file))]
    assert "파일 직접 다운로드 링크 표시됨" in capsys.readouterr().out
    assert len(list(queue.glob("receipt-*.json"))) == 1


def test_stable_avatar_vrm_path_is_atomically_copied_and_sha_verified(tmp_path):
    from tools.colab_download_contract import save_latest_avatar, gradio_file_route

    root = tmp_path / "output"
    root.mkdir()
    first = avatar_fixture(root, b"glTF" + b"A" * 80)
    target = tmp_path / "avatar.vrm"
    saved = save_latest_avatar(first, root, target)
    assert saved == target
    assert target.read_bytes() == first.read_bytes()
    assert first.exists()
    route = gradio_file_route(first, root)
    assert route == "/vtuber-download/avatar-123/avatar.vrm"

    second = root / "avatar-456" / "avatar.vrm"
    second.parent.mkdir()
    second.write_bytes(b"glTF" + b"B" * 125)
    save_latest_avatar(second, root, target)
    assert target.read_bytes() == second.read_bytes()
    assert not list(tmp_path.glob("*.pending"))
    assert first.exists()


def test_notebook_direct_download_renders_authenticated_link_not_blocking_colab_call(
    tmp_path, monkeypatch, capsys,
):
    from tools.colab_download_contract import gradio_file_route
    from pathlib import Path
    import importlib.util

    module_path = Path(__file__).resolve().parents[2] / "tools" / "colab_ui_launcher.py"
    spec = importlib.util.spec_from_file_location("direct_http_launcher", module_path)
    assert spec is not None and spec.loader is not None
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)
    launcher.WORK = tmp_path
    root = tmp_path / "output"
    root.mkdir()
    source = avatar_fixture(root)
    displayed = []
    class Javascript:
        def __init__(self, source):
            displayed.append(source)
    fake = types.ModuleType("IPython.display")
    fake.Javascript = Javascript
    fake.display = lambda value: None
    monkeypatch.setitem(sys.modules, "IPython", types.ModuleType("IPython"))
    monkeypatch.setitem(sys.modules, "IPython.display", fake)

    launcher._show_direct_download(19876, str(source))
    assert len(displayed) == 1
    assert "google.colab.kernel.proxyPort(port)" in displayed[0]
    assert gradio_file_route(source, root) in displayed[0]
    assert "link.click()" in displayed[0]
    assert "files.download" not in displayed[0]
    assert (tmp_path / "avatar.vrm").read_bytes() == source.read_bytes()
    text = capsys.readouterr().out
    assert str(source) in text
    assert str(tmp_path / "avatar.vrm") in text


def test_restart_offers_latest_completed_vrm_without_rebuilding(tmp_path):
    import importlib.util
    module_path = Path(__file__).resolve().parents[2] / "tools" / "colab_ui_launcher.py"
    spec = importlib.util.spec_from_file_location("colab_resume_vrm", module_path)
    assert spec and spec.loader
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)

    root = tmp_path / "output"
    root.mkdir()
    first = avatar_fixture(root, b"glTF" + b"1" * 40)
    second = root / "avatar-456" / "avatar.vrm"
    second.parent.mkdir()
    second.write_bytes(b"glTF" + b"2" * 56)
    bad = root / "avatar-789" / "avatar.vrm"
    bad.parent.mkdir()
    bad.write_bytes(b"not-a-vrm")
    import os
    os.utime(first, (10, 10))
    os.utime(second, (20, 20))
    os.utime(bad, (30, 30))
    assert launcher._latest_existing_avatar(root) == second
    assert launcher._latest_existing_avatar(tmp_path / "no-such-output") is None
