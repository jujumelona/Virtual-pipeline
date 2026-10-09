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


def test_gradio_6_builds_named_2d_and_3d_workflows():
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
    assert ui.select_workflow_view in handlers
    assert ui.prepare_selected_workflow_ui in handlers
    assert ui.return_to_workflow_choice in handlers
    assert ui.stream_avatar_ui in handlers
    assert ui.stream_accessories_ui in handlers
    assert ui.build_inochi2d_ui in handlers
    assert ui.build_live2d_ui in handlers
    assert ui.show_3d_accessory in handlers
    assert ui.show_3d_avatar in handlers


def test_gradio_real_update_routes_without_refreshing_installed_packages():
    # Test actual Gradio component updates without kicking off multi-GB
    # checkpoint downloads or cloning a Git repository on a CPU UI runner.
    # Separate production tests cover the worker setup contracts.
    from unittest.mock import patch
    ui = _app()
    with (
        patch("tools.install_2d_workers.activate_2d_environment") as two_d_setup,
        patch.object(ui, "_setup_stage") as stage,
        patch.object(ui, "prepare_models") as prepare,
    ):
        for mode, visible in (
            ("inochi2d", [False, True, False, False, False]),
            ("live2d", [False, False, True, False, False]),
            ("3d", [False, False, False, True, False]),
        ):
            selection = ui.choose_workflow(mode, "personalNonProfit")
            assert [value["visible"] for value in selection[:-1]] == visible
            assert selection[-1] == "personalNonProfit"
            prepare.assert_any_call(mode)
        # The test stubs the stage runner to prevent real pip/git downloads.
        # Each 2D callback is supplied to the labeled runner unchanged.
        assert two_d_setup.call_count == 0
        assert stage.call_args_list[0].args[1] is two_d_setup
        assert stage.call_args_list[2].args[1] is two_d_setup
        # 3D selects TripoSR source plus a minimal alpha worker, not the
        # entire 2D SAM/FLUX dependency environment.
        assert [call.args[0] for call in stage.call_args_list] == [
            "2D alpha/SAM/FLUX worker environment",
            "Inochi SDK native rig exporter",
            "2D alpha/SAM/FLUX worker environment",
            "3D TripoSR checkout",
            "3D alpha-only worker environment",
            "3D Blender VRM operator verification",
        ]


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
    assert "build_inochi2d_ui" in names
    assert "build_live2d_ui" in names


def test_avatar_has_native_download_button_bound_to_completed_generator():
    ui = _app()
    demo = ui.build_app()
    config = demo.get_config_file()
    components = {component["id"]: component for component in config["components"]}
    buttons = [
        comp for comp in components.values()
        if comp.get("type") == "downloadbutton"
    ]
    assert any(
        b["props"].get("label") == "↓ avatar.vrm 파일 직접 다운로드"
        for b in buttons
    ), buttons
    download = next(
        b for b in buttons
        if b["props"].get("label") == "↓ avatar.vrm 파일 직접 다운로드"
    )
    dependencies = config["dependencies"]
    generator = next(
        d for d in dependencies if d.get("api_name") == "stream_avatar_ui"
    )
    # The button only updates *after* the generation event completes.
    assert any(
        download["id"] in dep.get("outputs", [])
        and generator["id"] in dep.get("targets", [])
        for dep in dependencies
    ) or any(
        download["id"] in dep.get("outputs", [])
        and any(trigger[0] == generator["id"] for trigger in dep.get("targets", []))
        for dep in dependencies
    ) or any(
        download["id"] in dep.get("outputs", [])
        and dep.get("trigger_after") == generator["id"]
        for dep in dependencies
    ), dependencies


def test_real_gradio_native_file_route_serves_verified_avatar_bytes(tmp_path):
    from fastapi.testclient import TestClient
    from gradio.routes import App

    model_dir = tmp_path / "output" / "avatar-123"
    model_dir.mkdir(parents=True)
    model = model_dir / "avatar.vrm"
    data = b"glTF" + bytes(range(64))
    model.write_bytes(data)
    with gr.Blocks() as demo:
        gr.DownloadButton(value=str(model), label="Download avatar.vrm")
    demo.allowed_paths = [str(tmp_path / "output")]
    test_app = App.create_app(demo)
    # In pinned Gradio 6.3, VRM MIME is model/vrml, which gets rendered
    # inline. Verify we really fix the browser behavior, not only body bytes.
    original = TestClient(test_app).get("/gradio_api/file=" + str(model))
    assert original.status_code == 200
    assert original.content == data
    assert "inline" in original.headers.get("content-disposition", "").lower()

    from tools.colab_download_contract import install_direct_download_route
    install_direct_download_route(test_app, tmp_path / "output")
    response = TestClient(test_app).get(
        "/vtuber-download/avatar-123/avatar.vrm"
    )
    assert response.status_code == 200, (response.status_code, response.text[:300])
    assert response.content == data
    disposition = response.headers.get("content-disposition", "").lower()
    assert "attachment" in disposition, disposition
    assert "avatar.vrm" in disposition
    assert response.headers["content-type"].startswith("application/octet-stream")
    assert TestClient(test_app).get(
        "/vtuber-download/..%2f..%2fetc/avatar.vrm"
    ).status_code != 200


def test_upload_panels_open_before_any_heavy_mode_setup():
    """Navigation must not invoke pip, source checkout, or model prefetch."""
    from unittest.mock import patch
    ui = _app()
    with patch.object(ui, "choose_workflow", side_effect=AssertionError("unexpected setup")):
        for mode, expected in (
            ("inochi2d", (False, True, False, False, False)),
            ("live2d", (False, False, True, False, False)),
            ("3d", (False, False, False, True, False)),
        ):
            selection = ui.select_workflow_view(mode, "corporation")
            assert tuple(item["visible"] for item in selection[:5]) == expected
            assert selection[5] == "corporation"
            assert selection[6] == mode
            assert "이미지 업로드" in selection[7]
            assert selection[8] is None


def test_failed_3d_alpha_setup_keeps_upload_panel_and_provides_log(tmp_path):
    from unittest.mock import patch
    ui = _app()
    ui.WORK_ROOT = tmp_path
    with patch.object(ui, "choose_workflow", side_effect=RuntimeError(
        "pip install failed: No matching distribution found"
    )):
        status, log = ui.prepare_selected_workflow_ui("3d", "corporation")
    assert "3D VRM" in status
    assert "No matching distribution" in status
    assert "재시도" in status
    assert pathlib.Path(log).exists()
    assert "RuntimeError" in pathlib.Path(log).read_text(encoding="utf-8")


def test_real_gradio_mode_selection_wires_upload_then_background_preparation():
    ui = _app()
    config = ui.build_app().get_config_file()
    registry = {component["id"]: component for component in config["components"]}
    deps = config["dependencies"]
    navigation = next(entry for entry in deps if entry.get("api_name") == "select_workflow_view")
    setup_events = [entry for entry in deps if str(entry.get("api_name", "")).startswith("prepare_selected_workflow_ui")]
    assert len(setup_events) == 4  # chained preparation plus one retry per mode
    assert any(entry.get("trigger_after") == navigation["id"] for entry in setup_events)
    first_outputs = [registry[i]["props"].get("label") for i in navigation["outputs"]]
    assert "선택한 모드의 환경·모델 준비 상태" in first_outputs
    for name in ("Inochi2D 캐릭터 그림", "2D 캐릭터 원본 일러스트 (필수)",
                 "전신 정면 이미지 (필수)"):
        assert name in {item["props"].get("label") for item in registry.values()}


def test_avatar_components_declared_before_gradio_callback_registration():
    """Regression for the 3D startup NameError before any model is loaded.

    A malformed prompt edit previously removed avatar_status/other controls
    while leaving click(outputs=[avatar_status]) in place. Check the AST
    independently of Gradio's evolving construction-time behavior.
    """
    import ast

    tree = ast.parse((ROOT / "tools" / "colab_app.py").read_text(encoding="utf-8"))
    app = next(node for node in tree.body
               if isinstance(node, ast.FunctionDef) and node.name == "build_app")
    assignments = {}
    for node in ast.walk(app):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assignments[target.id] = node.lineno

    required = (
        "avatar_skintokens_setup", "avatar_run", "avatar_status",
        "avatar_log", "avatar_log_file", "avatar_result",
        "avatar_download_button", "avatar_http_link",
    )
    for name in required:
        assert name in assignments, f"3D component not defined: {name}"

    event_bindings = [
        node for node in ast.walk(app)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"click", "then"}
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id in {
            "avatar_skintokens_setup", "avatar_run", "avatar_generation_event",
        }
    ]
    assert len(event_bindings) == 3, "3D initialization callbacks not wired"
    for event in event_bindings:
        for argument in ast.walk(event):
            if isinstance(argument, ast.Name) and argument.id in required:
                assert assignments[argument.id] < event.lineno, (
                    f"{argument.id} referenced at line {event.lineno} "
                    f"before creation at line {assignments[argument.id]}"
                )


def test_3d_view_exposes_real_upload_status_and_download_components():
    ui = _app()
    config = ui.build_app().get_config_file()
    labels = {item.get("props", {}).get("label") for item in config["components"]}
    for label in (
        "전신 정면 이미지 (필수)",
        "얼굴 확대 이미지 (전신 고품질 모드 필수)",
        "전신 후면 이미지 (선택: 후면 텍스처에 사용)",
        "왼쪽 측면 참조 (선택)",
        "오른쪽 측면 참조 (선택)",
        "전신 VRM 변환",
        "완성 VRM (다운로드 가능한 원본 파일)",
        "↓ avatar.vrm 파일 직접 다운로드",
        "진행 로그",
        "전체 로그",
    ):
        assert label in labels, f"3D startup dropped required control: {label}"
