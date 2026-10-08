"""Exercise the real Colab runpy entrypoint without an editable install.

The first notebook cell installs packages in a CHILD Python process. The
second runs tools/colab_app.py inside the preexisting notebook kernel, where
the checkout does not automatically appear on sys.path. This reproduces that
exact boundary in an isolated Python subprocess.
"""

from __future__ import annotations

import json
import pathlib
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


def test_second_notebook_cell_adds_checkout_before_runpy():
    notebook = json.loads(
        (ROOT / "notebooks" / "VTuber_Commercial_Pipeline_Colab.ipynb").read_text(
            encoding="utf-8"
        )
    )
    cells = [
        "".join(c["source"])
        for c in notebook["cells"]
        if c["cell_type"] == "code"
    ]
    assert len(cells) == 2
    launch = cells[1]
    assert 'sys.path.insert(0, str(repo))' in launch
    assert launch.index('sys.path.insert(0, str(repo))') < launch.index(
        'runpy.run_path('
    )
    assert 'run_name="__main__"' in launch


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
