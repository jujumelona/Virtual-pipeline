"""Static integration tests for cross-stage pipeline wiring.

These tests intentionally avoid GPU/model imports. They protect the orchestration
contract that must remain true before expensive Colab E2E execution.
"""

from __future__ import annotations

import ast
import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[2]


def _source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _function_node(relative: str, class_name: str | None, function_name: str):
    tree = ast.parse(_source(relative))
    body = tree.body
    if class_name is not None:
        cls = next(
            node
            for node in body
            if isinstance(node, ast.ClassDef) and node.name == class_name
        )
        body = cls.body
    return next(
        node
        for node in body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == function_name
    )


def test_avatar_stage_dag_is_complete_and_ordered():
    node = _function_node(
        "vtuber_pipeline/avatar/build.py",
        "AvatarPipeline",
        "build",
    )
    stages = []
    for item in ast.walk(node):
        if not isinstance(item, ast.Call):
            continue
        func = item.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr == "_run_stage"
            and item.args
            and isinstance(item.args[0], ast.Constant)
            and isinstance(item.args[0].value, str)
        ):
            stages.append((item.lineno, item.args[0].value))

    ordered = [name for _, name in sorted(stages)]
    assert ordered == [
        "input_gate",
        "reference_reconstruction",
        "template_fitting",
        "texture_transfer",
        "rig",
        "expressions",
        "gaze",
        "springbone",
        "vrm_export",
        "validator",
    ]


def test_accessory_bake_revalidates_full_product_contract():
    node = _function_node(
        "vtuber_pipeline/accessory/build.py",
        "AccessoryPipeline",
        "build",
    )
    matches = []
    for item in ast.walk(node):
        if not isinstance(item, ast.Call):
            continue
        if isinstance(item.func, ast.Name) and item.func.id == "validate_vrm":
            matches.append(item)

    assert len(matches) == 1
    keyword = next(
        (kw for kw in matches[0].keywords if kw.arg == "product_contract"),
        None,
    )
    assert keyword is not None
    assert isinstance(keyword.value, ast.Constant)
    assert keyword.value.value is True


def test_cli_accessory_chain_feeds_each_output_into_next_input():
    source = _source("vtuber_pipeline/cli.py")
    start = source.index("current_vrm = base_vrm")
    call = source.index("base_vrm=current_vrm", start)
    update = source.index('current_vrm = build["output_vrm"]', call)
    assert start < call < update


def test_colab_accessory_chain_feeds_each_output_into_next_input():
    source = _source("tools/colab_app.py")
    start = source.index("current_vrm = base_path")
    call = source.index("base_vrm=current_vrm", start)
    update = source.index('current_vrm = result["output_vrm"]', call)
    assert start < call < update


def test_colab_gpu_queue_is_serialized():
    source = _source("tools/colab_app.py")
    assert "demo.queue(default_concurrency_limit=1)" in source
