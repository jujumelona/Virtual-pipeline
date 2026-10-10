import json
import sys
from pathlib import Path
import pytest


def run(tmp_path, code, timeout=3):
    from vtuber_pipeline.common.stage_runner import run_stage
    worker = tmp_path / 'worker.py'
    worker.write_text(code)
    request = tmp_path / 'request.json'
    request.write_text(json.dumps({'inputs': {}, 'model': {'id': 'fixture', 'revision': '1'}, 'settings': {}}))
    return run_stage(worker=str(worker), request_json=str(request), result_json=str(tmp_path/'result.json'), executable=sys.executable, cwd=str(tmp_path), timeout_sec=timeout)


def test_real_child_artifacts_and_cached_hashes(tmp_path):
    code = '''import argparse,json,pathlib
p=argparse.ArgumentParser();p.add_argument('request');p.add_argument('result');a=p.parse_args()
f=pathlib.Path('output.png');f.write_bytes(b'real artifact')
pathlib.Path(a.result).write_text(json.dumps({'status': 'complete', 'image_png': str(f.resolve())}))
'''
    result = run(tmp_path, code)
    assert Path(result['image_png']).read_bytes() == b'real artifact'
    assert (tmp_path/'result.json.provenance.json').is_file()


def test_missing_output_rejected(tmp_path):
    with pytest.raises(RuntimeError, match='artifact'):
        run(tmp_path, "import sys,pathlib;pathlib.Path(sys.argv[-1]).write_text('{\"status\":\"complete\",\"image_png\":\"missing.png\"}')")


def test_timeout_cannot_accept_stale_result(tmp_path):
    (tmp_path/'result.json').write_text('{"artifacts":{}}')
    with pytest.raises(RuntimeError, match='timed out'):
        run(tmp_path, 'import time;time.sleep(30)', timeout=0.1)
    assert not (tmp_path/'result.json').exists()


def test_nonzero_child_rejected(tmp_path):
    with pytest.raises(RuntimeError, match='exit=7'):
        run(tmp_path, 'raise SystemExit(7)')


def test_downstream_stage_releases_skipped_face_prewarm_before_gpu_lock(
    tmp_path, monkeypatch,
):
    """Cached face gate may skip its model: next GPU stage must not deadlock."""
    from tools import colab_gpu_warmup as warm

    monkeypatch.setenv("VTUBER_GENERATION_WORKER", "1")
    released = []
    monkeypatch.setattr(warm, "available_face_worker", lambda: True)
    monkeypatch.setattr(warm, "stop_face_worker",
                        lambda: released.append("face-gpu-unloaded"))
    code = (
        "import json,pathlib,sys; "
        "p=pathlib.Path('gpu-next.png');p.write_bytes(b'next-gpu-stage');"
        "pathlib.Path(sys.argv[-1]).write_text(json.dumps("
        "{'status':'complete','image_png':str(p.resolve())}))"
    )
    result = run(tmp_path, code)
    assert Path(result["image_png"]).is_file()
    assert released == ["face-gpu-unloaded"]

def test_stage_worker_hides_weight_progress_not_model_errors(tmp_path, capsys):
    code = """import pathlib,sys
print('Loading checkpoint shards: 50%|██████   | 2/4', flush=True)
print('Model load failed: verified checksum mismatch', flush=True)
raise SystemExit(7)
"""
    with pytest.raises(RuntimeError, match="checksum mismatch"):
        run(tmp_path, code)
    output = capsys.readouterr().out
    stored = (tmp_path / "result.log").read_text()
    assert "Loading checkpoint shards" not in output
    assert "Loading checkpoint shards" not in stored
    assert "checksum mismatch" in output
    assert "checksum mismatch" in stored
