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


def test_prefetch_only_models_consumed_by_actual_vts_entrypoints(tmp_path, monkeypatch):
    monkeypatch.setattr(setup, 'ROOT', tmp_path)
    monkeypatch.setattr(setup, 'checkout', lambda url, dest, sha: dest)
    downloaded = []
    def download(model, **kwargs):
        downloaded.append(model)
        return '/cache/' + model.replace('/', '--')
    monkeypatch.setattr(setup, 'download_snapshot', download)
    manifest = setup.prepare(qwen=True, install=False)
    assert downloaded == [
        '24yearsold/seethroughv0.0.2_layerdiff3d_nf4',
        '24yearsold/seethroughv0.0.1_marigold_nf4',
        'OzzyGT/qwen-image-layered-bnb-4bit-transformer',
        'StabilityLabs/Stable-Layers',
        'Qwen/Qwen-Image-Layered',
    ]
    assert [x['model'] for x in json.loads(manifest.read_text())['snapshots']] == downloaded


def test_see_through_venv_never_invokes_ensurepip(tmp_path, monkeypatch):
    """Colab /usr/bin/python3 may lack a functioning ensurepip."""
    venv = tmp_path / "see-through-venv"
    calls = []

    def fake_checked(args, **kwargs):
        calls.append(list(map(str, args)))
        if len(args) >= 3 and args[1:3] == ["-m", "venv"]:
            (venv / "bin").mkdir(parents=True)
            (venv / "bin" / "python").touch()
            (venv / "pyvenv.cfg").write_text(
                "include-system-site-packages = true\\n", encoding="utf-8"
            )
        return 0

    monkeypatch.setattr(setup, "checked", fake_checked)
    assert setup.ensure_see_through_python(venv) == str(venv / "bin" / "python")
    assert calls[0][1:4] == ["-m", "venv", "--without-pip"]
    assert "--system-site-packages" in calls[0]
    assert calls[1][0] == str(venv / "bin" / "python")
    assert calls[1][1] == "-c"
    assert "import pathlib, pip, sys" in calls[1][2]

    calls.clear()
    assert setup.ensure_see_through_python(venv) == str(venv / "bin" / "python")
    assert len(calls) == 1  # verify existing venv; do not recreate it


def test_partial_failed_venv_is_not_trusted(tmp_path, monkeypatch):
    venv = tmp_path / "partially-created"
    (venv / "bin").mkdir(parents=True)
    (venv / "bin" / "python").touch()
    # ensurepip may have failed after creating bin/python but before pip.
    calls = []

    def fake_checked(args, **kwargs):
        calls.append(list(map(str, args)))
        return 0

    monkeypatch.setattr(setup, "checked", fake_checked)
    setup.ensure_see_through_python(venv)
    assert any("--without-pip" in cmd for cmd in calls)


def test_worker_pip_preflight_failure_blocks_ready_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(setup, "ROOT", tmp_path)
    monkeypatch.setattr(setup, "checkout", lambda *args: tmp_path / "source")
    stale = tmp_path / "vts_setup_manifest.json"
    stale.write_text('{"ready":true}', encoding="utf-8")

    def fail_checked(args, **kwargs):
        if len(args) > 2 and args[1:3] == ["-m", "venv"]:
            return 0
        raise RuntimeError("worker pip unavailable")

    monkeypatch.setattr(setup, "checked", fail_checked)
    with pytest.raises(RuntimeError, match="worker pip unavailable"):
        setup.prepare(install=True)
    assert not stale.exists()
