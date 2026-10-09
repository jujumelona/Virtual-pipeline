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
    assert ui.choose_workflow in handlers
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
        assert two_d_setup.call_count == 2
        # 3D selects TripoSR source plus a minimal alpha worker, not the
        # entire 2D SAM/FLUX dependency environment.
        assert [call.args[0] for call in stage.call_args_list] == [
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
