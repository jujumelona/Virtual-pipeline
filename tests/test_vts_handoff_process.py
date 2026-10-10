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
