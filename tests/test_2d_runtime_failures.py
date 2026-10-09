"""The real 2D worker must preserve the causal error, not TensorFlow noise."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

from vtuber_pipeline.common.stage_runner import run_stage


def test_worker_exit_one_preserves_structured_florence_traceback(tmp_path, capsys):
    script = tmp_path / "florence_worker.py"
    script.write_text(
        "import sys, json\n"
        "from pathlib import Path\n"
        "print('WARNING: TensorFlow emitted CUDA stub noise', flush=True)\n"
        "Path(sys.argv[2]).write_text(json.dumps({"
        "'status':'error','error':'Unsupported Florence2 configuration',"
        "'traceback':'Traceback: Florence2ForConditionalGeneration config mismatch'}))\n"
        "sys.exit(1)\n",
        encoding="utf-8",
    )
    request = tmp_path / "request.json"
    request.write_text(json.dumps({"sample": "input"}))
    result = tmp_path / "florence.result.json"
    with pytest.raises(RuntimeError, match="Florence2ForConditionalGeneration config mismatch"):
        run_stage(
            worker=str(script), request_json=str(request),
            result_json=str(result), executable=sys.executable,
            cwd=str(tmp_path), timeout_sec=15,
        )
    assert result.is_file(), "Do not remove first failure's structured traceback"
    assert "Florence2ForConditionalGeneration" in result.read_text()
    shown = capsys.readouterr().out
    assert "config mismatch" in shown
    assert "TensorFlow emitted" in shown


def test_florence_worker_uses_native_model_without_tensorflow_or_legacy_causallm():
    import ast
    source = (
        Path(__file__).resolve().parents[1] / "tools" /
        "model_workers" / "florence_worker.py"
    ).read_text()
    ast.parse(source)
    assert 'os.environ["USE_TF"] = "0"' in source
    assert 'os.environ["USE_FLAX"] = "0"' in source
    assert "Florence2ForConditionalGeneration" in source
    assert "AutoModelForCausalLM.from_pretrained" not in source
    assert "from transformers import AutoProcessor, AutoModelForCausalLM" not in source
    assert "trust_remote_code=False" in source


def test_native_florence_checkpoint_is_immutable_mit_and_never_legacy_remote_code():
    from vtuber_pipeline.common.model_assets import model_pin, MODELS
    pin = model_pin("florence2_base")
    assert pin["model_id"] == "florence-community/Florence-2-base"
    assert pin["revision"] == "0ae188f8620727704bcffa9292a0fdb92f127480"
    assert "*.safetensors" in pin["allow_patterns"]
    assert MODELS["florence2_base"] == (pin["model_id"], "MIT")


def test_florence_prevents_part_segmentation_with_random_native_weights():
    from tools.model_workers import florence_worker
    import inspect
    source = inspect.getsource(florence_worker.infer)
    assert "output_loading_info=True" in source
    assert 'load_info.get("missing_keys", [])' in source
    assert 'load_info.get("unexpected_keys", [])' in source
    assert 'model=model.to(device).eval()' in source


def test_sigkill_reports_cgroup_oom_evidence(tmp_path, monkeypatch):
    """An OS SIGKILL is not automatically evidence of an OOM killer."""
    from vtuber_pipeline.common import stage_runner

    memory_states = iter([
        {"memory.max": 12 * 1048576, "events.oom_kill": 7},
        {"memory.max": 12 * 1048576, "events.oom_kill": 8,
         "memory.peak": 12 * 1048576},
    ])
    monkeypatch.setattr(stage_runner, "cgroup_memory_diagnostics",
                        lambda: next(memory_states))
    script = tmp_path / "worker.py"
    script.write_text("import os,signal; os.kill(os.getpid(),signal.SIGKILL)\n")
    request = tmp_path / "request.json"
    request.write_text(json.dumps({"input": "unit-test"}))
    with pytest.raises(RuntimeError, match="kernel_oom_confirmed") as error:
        run_stage(worker=str(script), request_json=str(request),
                  result_json=str(tmp_path / "result.json"),
                  executable=sys.executable, cwd=str(tmp_path), timeout_sec=20)
    assert "cgroup_oom_kill_delta=1" in str(error.value)
    assert "exit=-9" in str(error.value)


def test_sigkill_without_kernel_oom_delta_is_unconfirmed():
    from vtuber_pipeline.common.stage_runner import cgroup_oom_summary

    assert "SIGKILL_cause_unconfirmed" in cgroup_oom_summary(
        {"events.oom_kill": 2},
        {"events.oom_kill": 2, "memory.peak": 9 * 1048576},
    )
    assert "kernel_oom_confirmed" in cgroup_oom_summary(
        {"events.oom_kill": 2},
        {"events.oom_kill": 3},
    )
