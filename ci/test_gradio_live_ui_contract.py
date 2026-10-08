"""Validate actual Gradio 6.3 Blocks construction and callback output wiring.

These tests deliberately import installed Gradio instead of a fake component,
so regressions in visibility/Group/Accordion/launch kwargs are detected.
"""

from __future__ import annotations

import importlib.util
import pathlib

import gradio as gr

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _app():
    spec = importlib.util.spec_from_file_location(
        "colab_gradio_ui_real", ROOT / "tools" / "colab_app.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_gradio_6_builds_initial_chooser_and_two_hidden_workflows():
    ui = _app()
    demo = ui.build_app()
    assert isinstance(demo, gr.Blocks)
    config = demo.get_config_file()
    components = config["components"]
    labels = {
        part["props"].get("label")
        for part in components
        if isinstance(part.get("props"), dict)
    }
    assert {"작업 선택", "사용 범위", "진행 로그"} <= labels
    visible = {
        part["props"].get("elem_id"): part["props"].get("visible", True)
        for part in components
        if isinstance(part.get("props"), dict)
    }
    assert visible["workflow-start"] is True

    handlers = {getattr(fn, "fn", None) for fn in demo.fns.values()}
    assert ui.choose_workflow in handlers
    assert ui.return_to_workflow_choice in handlers
    assert ui.stream_avatar_ui in handlers
    assert ui.stream_accessories_ui in handlers


def test_gradio_real_update_routes_without_refreshing_installed_packages():
    ui = _app()
    selection = ui.choose_workflow("avatar", "personalNonProfit")
    assert selection[0]["visible"] is False
    assert selection[1]["visible"] is True
    assert selection[2]["visible"] is False
    assert selection[3] == "personalNonProfit"

    selection = ui.choose_workflow("accessory", "corporation")
    assert selection[1]["visible"] is False
    assert selection[2]["visible"] is True


def test_both_streaming_handlers_keep_progress_and_log_file_outputs():
    ui = _app()
    demo = ui.build_app()
    config = demo.get_config_file()
    registry = {part["id"]: part for part in config["components"]}
    for dependency in config["dependencies"]:
        api = dependency.get("api_name", "")
        if api not in {"stream_avatar_ui", "stream_accessories_ui"}:
            continue
        outputs = [
            registry[identity]["props"].get("label")
            for identity in dependency["outputs"]
        ]
        assert "진행 로그" in outputs
        assert "전체 로그" in outputs
    names = {
        dep.get("api_name") for dep in config["dependencies"]
    }
    assert "stream_avatar_ui" in names
    assert "stream_accessories_ui" in names
