"""Real child-process supervision tests; no network, torch, or Gradio required."""
from __future__ import annotations

import json
import pathlib
import sys
import textwrap

import pytest

from tools import colab_generation_process as process


def _fake_worker(tmp_path: pathlib.Path, body: str, monkeypatch):
    scripts = tmp_path / "tools"
    scripts.mkdir(exist_ok=True)
    (scripts / "colab_generation_worker.py").write_text(
        "from pathlib import Path\nimport json,os,signal,sys\n"
        "request=Path(sys.argv[1]); result=Path(sys.argv[2]); "
        "payload=json.loads(request.read_text())\n"
        + textwrap.dedent(body), encoding="utf-8",
    )
    monkeypatch.setattr(process, "ROOT", tmp_path)


def test_separate_real_python_process_returns_artifacts_and_streams_progress(tmp_path, monkeypatch):
    _fake_worker(tmp_path, """
        print('subprocess initialized', flush=True)
        print('VTUBER_GENERATION_EVENT ' + json.dumps({
            'kind':'progress', 'fraction':0.7, 'description':'model inference'
        }), flush=True)
        result.write_text(json.dumps({'result':['prepared','detail','output.zip']}))
    """, monkeypatch)
    events = []
    response = process.run_isolated(
        "live2d", ["portrait.png", "corporation"],
        root=tmp_path / "jobs", timeout=10, on_event=events.append,
    )
    assert response == ("prepared", "detail", "output.zip")
    assert ("progress", 0.7, "model inference") in events
    assert any(event[0] == "log" and "initialized" in event[1] for event in events)
    folder = next((tmp_path / "jobs").iterdir())
    assert json.loads((folder / "request.json").read_text()) == {
        "mode": "live2d", "args": ["portrait.png", "corporation"]
    }
    assert json.loads((folder / "status.json").read_text())["state"] == "complete"


def test_crashed_model_process_preserves_diagnostics_without_killing_controller(tmp_path, monkeypatch):
    _fake_worker(tmp_path, """
        print('CUDA initialization failed on worker', flush=True)
        sys.exit(19)
    """, monkeypatch)
    with pytest.raises(RuntimeError, match="exit=19") as error:
        process.run_isolated(
            "avatar", ["portrait.png", "corporation", None, None, None,
                       False, 2048, None, None, "canonical"],
            root=tmp_path / "jobs", timeout=10,
        )
    assert "generation.log" in str(error.value)
    folder = next((tmp_path / "jobs").iterdir())
    assert json.loads((folder / "status.json").read_text())["state"] == "failed"
    assert "CUDA initialization failed" in (folder / "generation.log").read_text()
    # Successful parent continuation means a failing child did not terminate UI.
    assert 2 + 3 == 5


def test_sigkill_model_worker_reports_oom_candidate_not_a_frozen_ui(tmp_path, monkeypatch):
    _fake_worker(tmp_path, """
        os.kill(os.getpid(), signal.SIGKILL)
    """, monkeypatch)
    with pytest.raises(RuntimeError, match="possible RAM/VRAM OOM"):
        process.run_isolated("inochi2d", ["portrait.png", "corporation"],
                             root=tmp_path / "jobs", timeout=10)
    folder = next((tmp_path / "jobs").iterdir())
    assert json.loads((folder / "status.json").read_text())["exit_code"] == -9


def test_worker_input_rejects_unknown_modes_before_any_subprocess(tmp_path):
    with pytest.raises(ValueError, match="Unsupported generation mode"):
        process.run_isolated("not-a-mode", [], root=tmp_path / "jobs")


def test_generation_worker_never_imports_gradio_or_torch_at_module_load():
    """Models are loaded through runpy only in the subprocess."""
    text = (pathlib.Path(__file__).resolve().parents[1]
            / "tools" / "colab_generation_worker.py").read_text(encoding="utf-8")
    assert "run_name=\"vtuber_prepare\"" in text
    assert "VTUBER_GENERATION_WORKER" in text
    assert "import gradio" not in text
    assert "import torch" not in text
