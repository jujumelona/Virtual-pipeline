"""Automatic probes isolate runtime faults without replaying GPU inference."""
import json
from pathlib import Path


def test_real_psd_diagnostic_probes_record_each_independent_result(tmp_path):
    from tools.vts_psd_diagnose import diagnose_psd_runtime
    report = diagnose_psd_runtime(tmp_path, timeout_seconds=20)
    assert report['state'] == 'probes_passed_cause_unresolved'
    assert {p['probe'] for p in report['probes']} == {
        'numpy', 'pillow', 'psd_import', 'rle_roundtrip', 'raw_roundtrip',
        'bounded_writer', 'legacy_save'}
    for probe in report['probes']:
        assert probe['returncode'] == 0
        assert probe['signal'] is None
        assert 'PSD_DIAG_PASS' in Path(probe['log_path']).read_text()
    saved = json.loads((tmp_path / 'psd_diagnosis.json').read_text())
    assert saved == report


def test_psd_native_failure_triggers_diagnostics_and_preserves_original_error(tmp_path, monkeypatch):
    import pytest
    import signal
    import sys
    from tools.vts_handoff_process import supervise_handoff
    from tools import vts_psd_diagnose
    calls = []
    def diagnose(output, **kwargs):
        calls.append(output)
        return {'state': 'probe_failed', 'probes': []}
    monkeypatch.setattr(vts_psd_diagnose, 'diagnose_psd_runtime', diagnose)
    script = "import os,signal;print('[VTS] PSD_NATIVE_STEP: {\"operation\":\"save\"}',flush=True);os.kill(os.getpid(),signal.SIGSEGV)"
    with pytest.raises(RuntimeError, match='SIGSEGV'):
        supervise_handoff([sys.executable, '-X', 'faulthandler', '-c', script], tmp_path, timeout_seconds=20)
    assert calls == [tmp_path / 'logs' / 'psd_diagnosis']
    failure = json.loads((tmp_path / 'vts_process_failure.json').read_text())
    assert failure['returncode'] == -signal.SIGSEGV
    assert failure['psd_diagnosis']['state'] == 'probe_failed'


def test_diagnostic_native_crash_does_not_prevent_remaining_probes(tmp_path, monkeypatch):
    import signal
    import sys
    from tools import vts_subprocess
    from tools.vts_psd_diagnose import diagnose_psd_runtime
    original = vts_subprocess.run_logged
    def run(command, **kwargs):
        if command[command.index('--probe') + 1] == 'rle_roundtrip':
            command = [sys.executable, '-X', 'faulthandler', '-c',
                       'import os,signal;os.kill(os.getpid(),signal.SIGSEGV)']
        return original(command, **kwargs)
    monkeypatch.setattr(vts_subprocess, 'run_logged', run)
    report = diagnose_psd_runtime(tmp_path, timeout_seconds=20)
    assert report['state'] == 'probe_failed'
    crashed = next(p for p in report['probes'] if p['probe'] == 'rle_roundtrip')
    assert crashed['returncode'] == -signal.SIGSEGV
    assert crashed['signal'] == 'SIGSEGV'
    assert report['probes'][-1]['returncode'] == 0
    assert 'Fatal Python error' in Path(crashed['log_path']).read_text()
