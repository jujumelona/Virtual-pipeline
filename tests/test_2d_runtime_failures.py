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
