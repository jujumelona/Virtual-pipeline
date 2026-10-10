"""Regression tests for the shared Colab package-resolution contract.

The live notebook must not downgrade the Hub version beneath Gradio and
Diffusers requirements or upgrade Torch/RAPIDS-incompatible support packages.
"""
import ast
from pathlib import Path

from packaging.requirements import Requirement
from packaging.version import Version


SOURCE = Path(__file__).resolve().parents[1] / "tools" / "colab_app.py"


def _runtime_packages_and_installer_source():
    module = ast.parse(SOURCE.read_text(encoding="utf-8"))
    function = next(
        node for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "_install_runtime"
    )
    runtime_list = next(
        node.value for node in ast.walk(function)
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "runtime_packages" for t in node.targets)
    )
    return {Requirement(p).name.lower(): Requirement(p) for p in ast.literal_eval(runtime_list)}, ast.get_source_segment(
        SOURCE.read_text(encoding="utf-8"), function
    )


def test_colab_runtime_pins_have_compatible_shared_versions():
    packages, source = _runtime_packages_and_installer_source()
    assert Version("5.18.0") in packages["transformers"].specifier
    assert Version("1.33.0") in packages["huggingface-hub"].specifier
    assert Version("0.36.2") not in packages["huggingface-hub"].specifier
    assert Version("0.61.2") in packages["numba"].specifier
    assert Version("0.68.0") not in packages["numba"].specifier
    assert Version("2.1.3") in packages["numpy"].specifier
    assert Version("2.5.3") not in packages["numpy"].specifier
    assert Version("0.17.2") in packages["jedi"].specifier
    assert '"setuptools<82"' in source
