"""Native crashes must become logged child failures, not notebook kernel deaths."""
import json
import os
from pathlib import Path
import signal
import sys

import pytest


def test_native_segfault_child_preserves_supervisor_and_failure_evidence(tmp_path):
    from tools.vts_handoff_process import supervise_handoff
    script = tmp_path / 'crash.py'
    script.write_text("import os,signal\nprint('[VTS] PSD_NATIVE_STEP: {\"operation\":\"save\"}',flush=True)\nos.kill(os.getpid(),signal.SIGSEGV)\n")
    with pytest.raises(RuntimeError, match='SIGSEGV'):
        supervise_handoff([sys.executable, '-X', 'faulthandler', str(script)], tmp_path / 'out', timeout_seconds=20)
    failure = json.loads((tmp_path / 'out/vts_process_failure.json').read_text())
    assert failure['signal'] == 'SIGSEGV'
    assert failure['returncode'] == -signal.SIGSEGV
    assert 'PSD_NATIVE_STEP' in Path(failure['log_path']).read_text()
    assert failure['last_psd_step']['operation'] == 'save'
    assert 'Fatal Python error' in Path(failure['log_path']).read_text()
    assert failure['memory_before']
    assert os.getpid() == failure['supervisor_pid']


def test_handoff_child_result_is_required_and_stale_success_is_removed(tmp_path):
    from tools.vts_handoff_process import supervise_handoff
    output = tmp_path / 'out'; output.mkdir()
    (output / 'handoff_result.json').write_text('{"state":"stale"}')
    with pytest.raises(RuntimeError, match='result manifest'):
        supervise_handoff([sys.executable, '-c', 'pass'], output, timeout_seconds=20)
    assert not (output / 'handoff_result.json').exists()


def test_handoff_silent_child_timeout_is_persisted(tmp_path):
    from tools.vts_handoff_process import supervise_handoff
    with pytest.raises(TimeoutError):
        supervise_handoff([sys.executable, '-c', 'import time;time.sleep(20)'], tmp_path, timeout_seconds=.2)
    failure = json.loads((tmp_path / 'vts_process_failure.json').read_text())
    assert failure['error_type'] == 'TimeoutError'
    assert Path(failure['log_path']).exists()


def test_isolated_handoff_reuses_real_completed_psd(tmp_path):
    from PIL import Image
    from tools.vts_psd_layer import new_import_psd, create_import_layer
    from tools.vts_handoff_process import make_cubism_handoff_isolated
    master = tmp_path / 'master.png'
    Image.new('RGBA',(256,384),(127,90,180,255)).save(master)
    psd = new_import_psd((384,384))
    for name in ('hair.front','body.torso'):
        create_import_layer(Image.new('RGBA',(384,384),(127,90,180,2)), psd, name=name)
    source = tmp_path / 'completed.psd'; psd.save(source)
    report = make_cubism_handoff_isolated(master, tmp_path / 'out', edition='free', scope='upper', generated_psd=source, timeout_seconds=60)
    assert report['reused_precomputed_see_through']
    assert Path(report['package']).is_file()
    assert Path(report['process_log']).is_file()


def test_notebook_direct_handoff_dispatches_before_image_or_codec_calls(tmp_path, monkeypatch):
    from types import ModuleType
    from tools import vts_production, vts_handoff_process
    monkeypatch.setitem(sys.modules, 'ipykernel', ModuleType('ipykernel'))
    monkeypatch.setattr(vts_production, '_image', lambda *a: pytest.fail('Notebook decoded image before isolation'))
    calls = []
    def isolated(master, output, **options):
        calls.append((master, output, options))
        return {'package': 'isolated.zip'}
    monkeypatch.setattr(vts_handoff_process, 'make_cubism_handoff_isolated', isolated)
    result = vts_production.make_cubism_handoff(tmp_path / 'missing.png', tmp_path / 'out', edition='free', scope='upper')
    assert result['package'] == 'isolated.zip'
    assert calls[0][2]['edition'] == 'free'


def test_preflight_identity_crash_leaves_durable_start_before_roundtrip(tmp_path, monkeypatch):
    from tools.vts_handoff_process import supervise_handoff
    from tools import vts_psd_diagnose
    monkeypatch.setattr(vts_psd_diagnose, 'diagnose_psd_runtime',
                        lambda *a, **k: {'state': 'probes_passed_cause_unresolved'})
    script = tmp_path / 'preflight_crash.py'
    diagnostics = tmp_path / 'runtime'
    script.write_text("from pathlib import Path\nimport os,signal\nfrom tools import vts_psd_layer\ndef crash():\n os.kill(os.getpid(),signal.SIGSEGV)\nvts_psd_layer.psd_runtime_identity=crash\nvts_psd_layer.verify_import_psd_runtime(diagnostics_dir=Path(" + repr(str(diagnostics)) + "))\n")
    # -c keeps the repository on sys.path even though the script lives in tmp.
    with pytest.raises(RuntimeError, match='SIGSEGV'):
        supervise_handoff([sys.executable, '-X', 'faulthandler', '-c', script.read_text()], tmp_path / 'out', timeout_seconds=20)
    failure = json.loads((tmp_path / 'out/vts_process_failure.json').read_text())
    assert failure['returncode'] == -signal.SIGSEGV
    assert failure['last_psd_step'] is None
    assert failure['last_runtime_step']['operation'] == 'runtime_identity'
    assert failure['psd_diagnosis']['state'] == 'probes_passed_cause_unresolved'
    assert 'PSD_RUNTIME_START' in Path(failure['log_path']).read_text()
    events = [json.loads(x) for x in (diagnostics / 'runtime.steps.jsonl').read_text().splitlines()]
    assert events[-1]['operation'] == 'runtime_identity'


def test_runtime_identity_is_saved_before_native_document_creation(tmp_path, monkeypatch):
    from tools import vts_psd_layer
    diagnostics = tmp_path / 'runtime'
    def fail(*args, **kwargs):
        report = json.loads((diagnostics / 'runtime.json').read_text())
        assert report['state'] == 'running'
        assert report['psd_tools_version']
        assert 'runtime_identity' in (diagnostics / 'runtime.steps.jsonl').read_text()
        raise RuntimeError('document creation stopped')
    monkeypatch.setattr(vts_psd_layer, 'new_import_psd', fail)
    with pytest.raises(RuntimeError, match='document creation stopped'):
        vts_psd_layer.verify_import_psd_runtime(diagnostics_dir=diagnostics)
    assert json.loads((diagnostics / 'runtime.json').read_text())['state'] == 'FAIL'


def test_preflight_completes_when_icc_transform_would_kill_interpreter(tmp_path):
    from tools.vts_subprocess import run_logged
    script = (
        "import os,signal\nfrom pathlib import Path\n"
        "from psd_tools.api import pil_io\n"
        "def crash(*args,**kwargs):\n os.kill(os.getpid(),signal.SIGSEGV)\n"
        "pil_io._apply_icc=crash\n"
        "from tools.vts_psd_layer import verify_import_psd_runtime\n"
        "report=verify_import_psd_runtime(diagnostics_dir=Path(" + repr(str(tmp_path / 'runtime')) + "))\n"
        "assert report['state']=='PASS' and report['rgba_byte_exact']\n"
    )
    code = run_logged([sys.executable, '-X', 'faulthandler', '-c', script],
                      log_path=tmp_path / 'preflight.log', timeout_seconds=20)
    assert code == 0
    events = [json.loads(line) for line in (tmp_path / 'runtime/probe.psd.steps.jsonl').read_text().splitlines()]
    assert events[-1]['operation'] == 'verified'
    decoded = next(event for event in events if event['operation'] == 'decode_layer')
    assert decoded['apply_icc'] is False
