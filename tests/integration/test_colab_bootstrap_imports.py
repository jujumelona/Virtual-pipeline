"""Exercise the real Colab runpy entrypoint without an editable install.

The first notebook cell installs packages in a CHILD Python process. The
second runs tools/colab_app.py inside the preexisting notebook kernel, where
the checkout does not automatically appear on sys.path. This reproduces that
exact boundary in an isolated Python subprocess.
"""

from __future__ import annotations

import json
import pathlib
import runpy
import shutil
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_colab_runpy_imports_pipeline_from_current_checkout(tmp_path):
    checkout = tmp_path / "checkout"
    (checkout / "tools").mkdir(parents=True)
    (checkout / "vtuber_pipeline" / "core").mkdir(parents=True)
    shutil.copy2(ROOT / "tools" / "colab_app.py", checkout / "tools" / "colab_app.py")
    shutil.copy2(
        ROOT / "vtuber_pipeline" / "core" / "stage_progress.py",
        checkout / "vtuber_pipeline" / "core" / "stage_progress.py",
    )
    (checkout / "vtuber_pipeline" / "__init__.py").write_text("", encoding="utf-8")
    (checkout / "vtuber_pipeline" / "core" / "__init__.py").write_text(
        "", encoding="utf-8"
    )

    # -I eliminates the working-directory import path, like the preexisting
    # Colab kernel after an editable install was done by a different process.
    probe = """
import pathlib, runpy, sys, types
gradio = types.ModuleType("gradio")
gradio.Progress = type("Progress", (), {})
sys.modules["gradio"] = gradio
checkout = pathlib.Path(sys.argv[1])
assert str(checkout) not in sys.path
app = runpy.run_path(str(checkout / "tools" / "colab_app.py"),
                     run_name="colab_ui_bootstrap_probe")
assert callable(app["_stream_ui_task"])
import vtuber_pipeline
from vtuber_pipeline.core.stage_progress import stage_reporter
assert pathlib.Path(vtuber_pipeline.__file__).resolve().is_relative_to(checkout)
assert callable(stage_reporter)
print("colab-runpy-import-ok", flush=True)
"""
    proc = subprocess.run(
        [sys.executable, "-I", "-c", probe, str(checkout)],
        cwd=tmp_path, text=True, capture_output=True, timeout=20,
    )
    assert proc.returncode == 0, (proc.stdout, proc.stderr)
    assert "colab-runpy-import-ok" in proc.stdout


def test_third_notebook_cell_generates_without_starting_any_server():
    notebook = json.loads(
        (ROOT / "notebooks" / "VTuber_Commercial_Pipeline_Colab.ipynb").read_text(
            encoding="utf-8"))
    cells = ["".join(x["source"]) for x in notebook["cells"] if x["cell_type"] == "code"]
    assert len(cells) == 3
    assert 'colab_native import generate' in cells[2]
    assert "RESULT_FILE = generate(" in cells[2]
    assert 'colab_ui_launcher' not in "\\n".join(cells)
    assert 'gradio' not in "\\n".join(cells).casefold()
    assert 'serve_kernel_port' not in "\\n".join(cells)
    assert 'VTUBER_SETUP_ONLY' in cells[0]


def test_gradio_6_theme_and_css_are_only_set_during_launch():
    source = (ROOT / "tools" / "colab_app.py").read_text(encoding="utf-8")
    start = source.index("def build_app()")
    launch = source.index("def launch()", start)
    build_code, launch_code = source[start:launch], source[launch:]
    assert 'with gr.Blocks(title="VTuber Builder") as demo:' in build_code
    assert 'theme=gr.themes.Soft()' not in build_code
    assert 'css=CSS' not in build_code
    assert 'theme=gr.themes.Soft()' in launch_code
    assert 'css=CSS' in launch_code


def test_preparation_import_never_requires_gradio(tmp_path):
    """The package installer can start even if Gradio cannot import yet."""
    checkout = tmp_path / "checkout"
    (checkout / "tools").mkdir(parents=True)
    shutil.copy2(ROOT / "tools" / "colab_app.py", checkout / "tools" / "colab_app.py")
    probe = """
import os, pathlib, runpy, sys
os.environ['VTUBER_SETUP_ONLY'] = '1'
sys.modules['gradio'] = None
checkout = pathlib.Path(sys.argv[1])
app = runpy.run_path(str(checkout / 'tools' / 'colab_app.py'), run_name='vtuber_prepare')
assert callable(app['ensure_runtime'])
assert callable(app['prepare_models'])
print('setup-import-without-gradio-ok')
"""
    proc = subprocess.run(
        [sys.executable, "-I", "-c", probe, str(checkout)],
        cwd=tmp_path, text=True, capture_output=True, timeout=20,
    )
    assert proc.returncode == 0, (proc.stdout, proc.stderr)
    assert "setup-import-without-gradio-ok" in proc.stdout


def test_notebook_setup_captures_child_traceback_and_writes_full_log(tmp_path):
    """An aborted setup child leaves an explicit error in the local log."""
    import ast
    import os
    import signal
    import time
    import pytest

    notebook = json.loads(
        (ROOT / "notebooks" / "VTuber_Commercial_Pipeline_Colab.ipynb").read_text(
            encoding="utf-8"))
    first = next(c for c in notebook["cells"] if c["cell_type"] == "code")
    tree = ast.parse("".join(first["source"]))
    runner = next(node for node in tree.body
                  if isinstance(node, ast.FunctionDef) and node.name == "run")
    namespace = {
        "SETUP_LOG": tmp_path / "logs" / "setup.log",
        "subprocess": subprocess, "os": os, "signal": signal, "time": time,
    }
    exec(compile(ast.Module(body=[runner], type_ignores=[]),
                 "<notebook-runner>", "exec"), namespace)
    with pytest.raises(RuntimeError, match="child-crash-diagnostic"):
        namespace["run"]([
            sys.executable, "-u", "-c",
            "import sys; print('child-crash-diagnostic', file=sys.stderr); sys.exit(3)",
        ], 15)
    text = namespace["SETUP_LOG"].read_text(encoding="utf-8")
    assert "child-crash-diagnostic" in text
    assert "sys.exit(3)" in text


def test_native_notebook_setup_isolated_and_selector_downloads_no_models():
    notebook = json.loads(
        (ROOT / "notebooks" / "VTuber_Commercial_Pipeline_Colab.ipynb").read_text(
            encoding="utf-8"))
    cells = ["".join(c["source"]) for c in notebook["cells"] if c["cell_type"] == "code"]
    assert len(cells) == 3
    assert "VTUBER_SETUP_ONLY" in cells[0]
    assert "subprocess.Popen" not in cells[1]
    assert 'TASK = "캐릭터 생성"' in cells[1]
    assert "ACCESSORY_ANCHOR = \"AUTO\"" in cells[1]
    assert "if TASK == \"캐릭터 생성\":" in cells[2]
    assert "elif TASK == \"액세서리 제작\":" in cells[2]
    assert "MODE =" in cells[1]
    assert "generate(" in cells[2]
    assert "colab_ui_launcher" not in "".join(cells)
    for code in cells:
        compile(code, "<colab-cell>", "exec")


def test_legacy_open_colab_cell_does_not_import_gradio(tmp_path):
    """Old, already-open Colab cells don't set VTUBER_SETUP_ONLY."""
    checkout = tmp_path / "checkout"
    (checkout / "tools").mkdir(parents=True)
    shutil.copy2(ROOT / "tools" / "colab_app.py", checkout / "tools" / "colab_app.py")
    probe = """
import os, pathlib, runpy, sys
os.environ.pop('VTUBER_SETUP_ONLY', None)
sys.modules['gradio'] = None
checkout = pathlib.Path(sys.argv[1])
app = runpy.run_path(str(checkout / 'tools' / 'colab_app.py'), run_name='vtuber_prepare')
assert app['_PREPARATION_MODE'] is True
assert callable(app['ensure_runtime'])
print('legacy-unflagged-setup-import-ok')
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", probe, str(checkout)],
        cwd=tmp_path, text=True, capture_output=True, timeout=20,
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert "legacy-unflagged-setup-import-ok" in result.stdout


def test_setup_stage_prints_and_persists_exception(tmp_path, capsys):
    """The exact setup failure is in stdout for old check=True notebook cells."""
    import os
    from unittest.mock import patch

    with patch.dict(os.environ, {"VTUBER_SETUP_ONLY": "1"}):
        module = runpy.run_path(
            str(ROOT / "tools" / "colab_app.py"), run_name="vtuber_prepare",
        )
    stage = module["_setup_stage"]
    stage.__globals__["WORK_ROOT"] = tmp_path

    def explode():
        raise RuntimeError("forced-setup-failure-marker")

    import pytest
    with pytest.raises(RuntimeError, match="forced-setup-failure-marker"):
        stage("forced package setup", explode)
    out = capsys.readouterr().out
    assert "forced package setup: FAILED" in out
    assert "Traceback (most recent call last):" in out
    assert "forced-setup-failure-marker" in out
    logged = (tmp_path / "logs" / "runtime_setup.log").read_text(encoding="utf-8")
    assert "forced-setup-failure-marker" in logged


def test_readme_canonical_notebook_uses_native_colab_cells():
    notebook_path = ROOT / "notebooks" / "VTuber_Commercial_Pipeline_Colab_v8.ipynb"
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "blob/main/notebooks/VTuber_Commercial_Pipeline_Colab_v8.ipynb" in readme
    cells = ["".join(c["source"]) for c in json.loads(
        notebook_path.read_text(encoding="utf-8"))["cells"] if c["cell_type"] == "code"]
    assert len(cells) == 3
    assert "subprocess.Popen(" in cells[0]
    assert "colab_bootstrap.log" in cells[0]
    assert "start_new_session=True" in cells[0]
    assert "stop_legacy_server()" in cells[0]
    assert 'TASK = "캐릭터 생성"' in cells[1]
    assert "ACCESSORY_ANCHOR = \"AUTO\"" in cells[1]
    assert "if TASK == \"캐릭터 생성\":" in cells[2]
    assert "elif TASK == \"액세서리 제작\":" in cells[2]
    assert "MODE =" in cells[1]
    assert "files.download(RESULT_FILE)" in cells[2]
    assert "colab_native import generate" in cells[2]
    assert "colab_ui_launcher" not in "".join(cells)


def test_native_mode_picker_does_not_download_unselected_models(monkeypatch, capsys):
    notebook = json.loads(
        (ROOT / "notebooks" / "VTuber_Commercial_Pipeline_Colab_v8.ipynb")
        .read_text(encoding="utf-8"))
    cells = ["".join(c["source"]) for c in notebook["cells"] if c["cell_type"] == "code"]
    assert len(cells) == 3
    assert "prepare_models(" not in cells[1]
    assert "subprocess." not in cells[1]
    def forbidden(*args, **kwargs):
        raise AssertionError("mode selection must not spawn any process")
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    exec(compile(cells[1], "<colab-mode>", "exec"), {})
    assert "작업 종류: 캐릭터 생성" in capsys.readouterr().out


def test_model_prepare_entrypoint_dumps_unmodified_traceback(tmp_path, capsys):
    """Old Colab cells also receive an actual traceback without wrapper edits."""
    import os
    from unittest.mock import patch

    with patch.dict(os.environ, {"VTUBER_SETUP_ONLY": "1"}):
        module = runpy.run_path(
            str(ROOT / "tools" / "colab_app.py"), run_name="prepare",
        )
    prepare = module["prepare_models"]
    prepare.__globals__["WORK_ROOT"] = tmp_path

    def fail(mode):
        assert mode == "3d"
        raise RuntimeError("pin-verification-failed-unique-code")

    prepare.__globals__["_prepare_models_checked"] = fail

    import pytest
    with pytest.raises(RuntimeError, match="pin-verification-failed-unique-code"):
        prepare()
    output = capsys.readouterr().out
    assert "pin-verification-failed-unique-code" in output
    assert "Traceback (most recent call last)" in output
    assert "pin-verification-failed-unique-code" in (
        tmp_path / "logs" / "model_setup.log"
    ).read_text(encoding="utf-8")


def test_all_colab_notebooks_use_native_cell_lifetimes():
    import ast

    for suffix in ("", "_v2", "_v3", "_v4", "_v5", "_v6", "_v7", "_v8"):
        notebook_path = ROOT / "notebooks" / f"VTuber_Commercial_Pipeline_Colab{suffix}.ipynb"
        notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
        cells = ["".join(cell["source"]) for cell in notebook["cells"]
                 if cell["cell_type"] == "code"]
        assert len(cells) == 3, notebook_path
        assert "run_name=\"__main__\"" not in cells[2]
        assert "RESULT_FILE = generate(" in cells[2]
        assert "gradio" not in "\\n".join(cells).lower()
        ast.parse(cells[2])

