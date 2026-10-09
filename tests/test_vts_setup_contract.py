"""Preparation may publish readiness only after bounded model acquisition."""
import json
from pathlib import Path
import sys
import pytest
from tools import vts_setup as setup


def test_failed_preparation_invalidates_previous_ready_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(setup, "ROOT", tmp_path)
    ready = tmp_path / "vts_setup_manifest.json"
    ready.write_text('{"qwen_weights_prefetched": true}')
    monkeypatch.setattr(setup, "checkout", lambda *a: (_ for _ in ()).throw(RuntimeError("checkout failed")))
    with pytest.raises(RuntimeError, match="checkout failed"):
        setup.prepare(install=False)
    assert not ready.exists()


def test_download_worker_returns_observed_snapshot_and_keeps_log(tmp_path, monkeypatch):
    module = tmp_path / "huggingface_hub.py"
    module.write_text('''def snapshot_download(repo_id, **kwargs):
    assert repo_id == 'fixture/model'
    assert kwargs['ignore_patterns'] == ['transformer/*.safetensors']
    print('download fixture complete', flush=True)
    return '/prepared/fixture-snapshot'
''')
    monkeypatch.setenv("PYTHONPATH", str(tmp_path))
    record = tmp_path / "download.json"
    result = setup.download_snapshot("fixture/model", python=sys.executable,
                                     record_path=record, timeout=20,
                                     ignore_patterns=["transformer/*.safetensors"])
    assert result == "/prepared/fixture-snapshot"
    assert json.loads(record.read_text())["snapshot"] == result
    assert "download fixture complete" in record.with_suffix(".log").read_text()


def test_download_wall_timeout_never_accepts_stale_snapshot_record(tmp_path, monkeypatch):
    (tmp_path / "huggingface_hub.py").write_text('''import time
def snapshot_download(*args, **kwargs):
    time.sleep(100)
''')
    monkeypatch.setenv("PYTHONPATH", str(tmp_path))
    record = tmp_path / "download.json"
    record.write_text('{"snapshot":"/stale"}')
    with pytest.raises(TimeoutError):
        setup.download_snapshot("fixture/model", python=sys.executable,
                                record_path=record, timeout=.3)
    assert not record.exists()
