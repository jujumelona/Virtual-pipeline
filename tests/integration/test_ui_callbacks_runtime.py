"""CPU-only Gradio callback contract tests with the heavy runtime mocked out.

The actual Colab handler functions are imported from their source module,
so these tests exercise Python option routing and artifact handoffs rather
than checking for specific lines of text.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import types

import pytest


ROOT = pathlib.Path(__file__).resolve().parents[2]


class FakeProgress:
    def __call__(self, *_args, **_kwargs):
        pass


@pytest.fixture
def ui(tmp_path, monkeypatch):
    gradio_stub = types.ModuleType("gradio")
    gradio_stub.Progress = FakeProgress
    gradio_stub.Blocks = object
    gradio_stub.update = lambda **kwargs: kwargs
    monkeypatch.setitem(sys.modules, "gradio", gradio_stub)

    spec = importlib.util.spec_from_file_location(
        "vtuber_colab_app_contract_test",
        ROOT / "tools" / "colab_app.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "OUTPUT_ROOT", tmp_path / "outputs")
    monkeypatch.setattr(module, "WORK_ROOT", tmp_path / "runtime")
    # Editor presence is a real production precondition. The callback tests
    # mock only the independently tested Blender probe, not the output graph.
    import tools.setup_blender_runtime as blender_setup
    monkeypatch.setattr(blender_setup, "require_blender_runtime_ready", lambda: "/mock/blender")
    module._real_require_runtime_ready = module.require_runtime_ready
    monkeypatch.setattr(
        module,
        "require_runtime_ready",
        lambda _progress=None: ("a" * 40, ["runtime-ready"]),
    )
    # These tests substitute pure functions for real GPU models. Keep mocked
    # callbacks in-process: production always uses a separate model process.
    def run_mocked_generation(mode, args, on_event=None):
        if mode in {"inochi2d", "live2d"}:
            return module._run_2d_production_inline(*args, target=mode)
        from vtuber_pipeline.core.stage_progress import stage_reporter
        handler = module.build_avatar_ui if mode == "avatar" else module.build_accessories_ui
        with stage_reporter(lambda name, status, detail: on_event and on_event(
                ("stage", name, status, detail))):
            return handler(*args, progress=lambda fraction, desc="": (
                on_event and on_event(("progress", fraction, desc))))
    monkeypatch.setattr(module, "_run_isolated_generation", run_mocked_generation)
    return module


def test_avatar_ui_passes_usage_to_avatar_and_exposes_vrm(ui, tmp_path, monkeypatch):
    image = tmp_path / "character.png"
    image.write_bytes(b"input")
    calls = []

    def fake_avatar(*, image_path, output_dir, config):
        calls.append((image_path, config))
        vrm = pathlib.Path(output_dir) / "avatar.vrm"
        vrm.write_bytes(b"vrm")
        return {
            "status": "complete",
            "vrm_path": str(vrm),
            "stages": {"validator": {"status": "complete"}},
        }

    monkeypatch.setattr(
        ui, "_pipeline_imports", lambda: (fake_avatar, None, None),
    )
    status, logs, download, state = ui.build_avatar_ui(
        str(image), "personalProfit", None,
    )
    assert status.startswith("✅")
    assert "validator" in logs
    assert pathlib.Path(download).is_file()
    assert state == download
    assert calls == [(str(image), {
        "profile": "commercial",
        "commercial_usage": "personalProfit",
        "rigging": {"provider": "canonical"},
        "references": {
            "full_body": False,
            "face_image": None,
            "back_image": None,
            "left_image": None,
            "right_image": None,
            "texture_size": 2048,
        },
    })]
    # Nondefault engine selection must reach AvatarPipeline, not just exist
    # in the Gradio dropdown without a live data binding.
    second_status, _, _, _ = ui.build_avatar_ui(
        str(image), "personalProfit", None, rigging_provider="blender_heat",
    )
    assert second_status.startswith("✅")
    assert calls[-1][1]["rigging"] == {"provider": "blender_heat"}


def test_accessory_ui_forwards_each_slot_and_chains_combined_vrm(
    ui, tmp_path, monkeypatch,
):
    latest_avatar = tmp_path / "latest.vrm"
    latest_avatar.write_bytes(b"vrm")
    image_a = tmp_path / "crown.png"
    image_b = tmp_path / "ribbon.png"
    mesh_a = tmp_path / "crown.glb"
    mesh_b = tmp_path / "ribbon.glb"
    for path in (image_a, image_b, mesh_a, mesh_b):
        path.write_bytes(b"payload")

    seen = {"builds": []}

    def fake_reconstruct(images, output_dir, *, profile):
        seen["images"] = images
        seen["profile"] = profile
        return [
            {"status": "complete", "image": images[0], "mesh": str(mesh_a)},
            {"status": "complete", "image": images[1], "mesh": str(mesh_b)},
        ]

    class FakeAccessoryPipeline:
        def __init__(self, output_dir):
            self.output_dir = pathlib.Path(output_dir)

        def build(self, *, base_vrm, accessory_glb, config):
            seen["builds"].append((base_vrm, accessory_glb, config))
            self.output_dir.mkdir(parents=True, exist_ok=True)
            result = self.output_dir / "combined.vrm"
            result.write_bytes(b"combined")
            return {
                "status": "complete",
                "output_vrm": str(result),
                "stages": {"bake": {"status": "complete"}},
            }

    monkeypatch.setattr(
        ui,
        "_pipeline_imports",
        lambda: (None, fake_reconstruct, FakeAccessoryPipeline),
    )
    slot_values = [
        str(image_a), "CUSTOM", "head", 0.01, 0.02, 0.03, 0.14,
        str(image_b), "HEAD_TOP", "head", 0.0, 0.0, 0.0, 0.12,
        *([None] * (6 * 7)),
    ]
    status, logs, download = ui.build_accessories_ui(
        True, None, str(latest_avatar), *slot_values,
    )
    assert status.startswith("✅"), (status, logs)
    assert seen["images"] == [str(image_a), str(image_b)]
    assert seen["profile"] == "commercial"
    first, second = seen["builds"]
    assert first[0] == str(latest_avatar)
    assert first[1] == str(mesh_a)
    assert first[2] == {
        "anchor_name": "CUSTOM",
        "custom_anchor": {
            "parent_bone": "head",
            "offset": [0.01, 0.02, 0.03],
            "target_size": 0.14,
        },
        "bake": True,
    }
    assert second[0] != str(latest_avatar)
    assert pathlib.Path(second[0]).is_file()
    assert second[1] == str(mesh_b)
    assert second[2]["anchor_name"] == "HEAD_TOP"
    assert second[2]["custom_anchor"] is None
    assert download == str(ui_path := pathlib.Path(download))
    assert ui_path.is_file()
    assert "bake" in logs


def test_avatar_ui_keeps_previous_success_on_new_generation_failure(
    ui, tmp_path, monkeypatch,
):
    prior = tmp_path / "previous.vrm"
    prior.write_bytes(b"prior-valid-vrm")

    status, logs, download, state = ui.build_avatar_ui(
        None, "corporation", str(prior),
    )
    assert status.startswith("❌")
    assert download is None
    assert state == str(prior)

    image = tmp_path / "invalid-character.png"
    image.write_bytes(b"new-input")

    def failed_avatar(**_kwargs):
        return {
            "status": "failed",
            "failed_stages": ["input_gate"],
            "failed_reason": "invalid face",
            "stages": {"input_gate": {"status": "error", "error": "invalid face"}},
        }

    monkeypatch.setattr(
        ui, "_pipeline_imports", lambda: (failed_avatar, None, None),
    )
    status, logs, download, state = ui.build_avatar_ui(
        str(image), "corporation", str(prior),
    )
    assert "invalid face" in status
    assert download is None
    assert state == str(prior)
    assert prior.is_file()


def test_avatar_generator_streams_stage_updates_and_full_log(ui, tmp_path, monkeypatch):
    from vtuber_pipeline.core.stage_progress import report_stage

    image = tmp_path / "image.png"
    image.write_bytes(b"image")
    monkeypatch.setattr(ui, "WORK_ROOT", tmp_path / "work")
    monkeypatch.setattr(ui, "_gpu_snapshot", lambda: "GPU VRAM 125/15000 MiB, 사용률 4%")

    def fake_build(*, image_path, output_dir, config):
        report_stage("input_gate", "running")
        report_stage("input_gate", "complete")
        report_stage("reference_reconstruction", "running")
        report_stage("reference_reconstruction", "complete")
        vrm = pathlib.Path(output_dir) / "avatar.vrm"
        vrm.write_bytes(b"valid")
        return {"status": "complete", "vrm_path": str(vrm), "stages": {}}

    monkeypatch.setattr(ui, "_pipeline_imports", lambda: (fake_build, None, None))
    updates = list(ui.stream_avatar_ui(
        str(image), "corporation", None, progress=FakeProgress(),
    ))

    assert len(updates) >= 4
    assert all(len(item) == 5 for item in updates)
    assert any("[input_gate] running" in item[1] for item in updates)
    assert any("[reference_reconstruction] running" in item[1] for item in updates)
    assert any("GPU VRAM 125" in item[1] for item in updates)
    assert updates[-1][0].startswith("✅")
    assert pathlib.Path(updates[-1][2]).is_file()
    assert updates[-1][3] == updates[-1][2]
    log_file = pathlib.Path(updates[-1][4])
    assert log_file.is_file()
    assert "input_gate" in log_file.read_text(encoding="utf-8")


def test_generation_requires_explicit_prepared_runtime_without_install(ui, tmp_path, monkeypatch):
    monkeypatch.setattr(ui, "WORK_ROOT", tmp_path / "not-prepared")
    monkeypatch.setattr(ui, "REPO_DIR", tmp_path / "checkout")
    monkeypatch.setattr(ui, "_runtime_contract_fingerprint", lambda: "a" * 64)
    monkeypatch.setattr(
        ui.subprocess, "run",
        lambda *args, **kwargs: types.SimpleNamespace(
            returncode=0, stdout="b" * 40 + "\n", stderr="",
        ),
    )
    with pytest.raises(RuntimeError, match="① 환경 설치"):
        ui._real_require_runtime_ready()


def test_start_routes_to_exact_mode_with_selected_scope(ui, monkeypatch):
    import tools.install_2d_workers as installers
    setup_calls = []
    monkeypatch.setattr(installers, "activate_2d_environment",
                        lambda: setup_calls.append("2d"))
    monkeypatch.setattr(ui, "_setup_stage",
                        lambda name, fn: setup_calls.append(name))
    monkeypatch.setattr(ui, "prepare_models",
                        lambda mode: setup_calls.append(mode))
    for requested, expected in (
        ("inochi2d", [False, True, False, False, False]),
        ("live2d", [False, False, True, False, False]),
        ("3d", [False, False, False, True, False]),
    ):
        selected = ui.choose_workflow(requested, "personalProfit")
        assert [part["visible"] for part in selected[:-1]] == expected
        assert selected[-1] == "personalProfit"

    assert setup_calls == [
        "2D alpha/SAM/FLUX worker environment", "Inochi SDK native rig exporter",
        "inochi2d", "2D alpha/SAM/FLUX worker environment", "live2d",
        "3D TripoSR checkout",
        "3D alpha-only worker environment",
        "3D Blender VRM operator verification",
        "3d",
    ]
    assert [v["visible"] for v in ui.return_to_workflow_choice()] == [
        True, False, False, False, False,
    ]
    assert ui.show_3d_accessory() == (
        {"visible": False}, {"visible": True},
    )
    assert ui.show_3d_avatar() == (
        {"visible": True}, {"visible": False},
    )


@pytest.mark.parametrize(
    "mode,usage",
    [("garbage", "corporation"), ("3d", "GPL"), ("inochi2d", ""), ("2d", "corporation")],
)
def test_workflow_selection_rejects_invalid_mode_or_usage(ui, mode, usage):
    with pytest.raises(ValueError):
        ui.choose_workflow(mode, usage)


@pytest.mark.parametrize(
    "target,filename",
    [
        ("inochi2d", "inochi2d_artwork_prep.zip"),
        ("live2d", "live2d_artwork_prep.zip"),
    ],
)
def test_both_2d_modes_do_not_require_3d_gpu_runtime(
    ui, tmp_path, monkeypatch, target, filename,
):
    """2D outputs are prepared/editor handoffs, never fake streaming puppets."""
    from PIL import Image
    import vtuber_pipeline.two_d.build as production
    artwork = tmp_path / "artwork.png"
    Image.new("RGBA", (512, 768), (20, 40, 60, 255)).save(artwork)
    checked = []
    def assert_selected_runtime(mode):
        checked.append(mode)
        assert mode == target, "A 2D callback must never require 3D models"
        return ("a" * 40, ["2d-runtime-ready"])
    monkeypatch.setattr(ui, "require_runtime_ready", assert_selected_runtime)

    expected_status = "prepared" if target == "inochi2d" else "needs_editor_export"
    output_name = "artwork.psd" if target == "inochi2d" else "cubism_handoff.zip"
    observed_sources = []
    def fake_native_graph(source):
        observed_sources.append(source)
        assert source.mode == target
        assert source.commercial_usage == "personalProfit"
        assert source.user_layers_zip is None, "user must only supply the original character image"
        folder = pathlib.Path(source.output_dir)
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / output_name
        path.write_bytes(b"editable-contract-content")
        return types.SimpleNamespace(
            status=expected_status, primary_file=str(path),
            editable_file=str(path), error=None,
        )
    monkeypatch.setattr(
        production, "build_inochi2d" if target == "inochi2d" else "build_live2d",
        fake_native_graph,
    )
    handler = ui.build_inochi2d_ui if target == "inochi2d" else ui.build_live2d_ui
    status, report, path = handler(str(artwork), "personalProfit")
    assert checked == [target]
    assert len(observed_sources) == 1
    assert pathlib.Path(path).is_file()
    assert pathlib.Path(path).name == output_name
    assert "status: " + expected_status in report
    assert "방송용 모델 생성 완료" not in status
    if target == "inochi2d":
        # SDK 0.8 exports genuine INP1 and later versions may export INP2.
        # UI must advertise the actual official SDK gate, not one encoding.
        assert "SDK INP" in status
    else:
        assert "Cubism" in status


def test_launch_clears_stale_pipeline_modules_before_runtime_check(ui, tmp_path, monkeypatch):
    events = []

    class FakeDemo:
        def queue(self, **kwargs):
            events.append("queue")

        def launch(self, **kwargs):
            events.append("launch")

    monkeypatch.setattr(ui, "WORK_ROOT", tmp_path / "root")
    monkeypatch.setattr(ui, "OUTPUT_ROOT", tmp_path / "root" / "outputs")
    monkeypatch.setattr(
        ui.gr, "themes", types.SimpleNamespace(Soft=lambda: object()), raising=False,
    )
    monkeypatch.setattr(ui, "_reload_pipeline_modules", lambda: events.append("reload"))
    monkeypatch.setattr(
        ui, "require_runtime_ready",
        lambda: (events.append("runtime") or ("a" * 40, [])),
    )
    monkeypatch.setattr(ui, "build_app", lambda: (events.append("build") or FakeDemo()))
    ui.launch()
    # 2D art preparation launches even if 3D model assets are not ready.
    # 3D callbacks still enforce their runtime readiness individually.
    assert events == ["reload", "build", "queue", "launch"]


def test_native_import_failure_is_written_to_ui_log_instead_of_gradio_traceback(
    ui, tmp_path, monkeypatch,
):
    """A broken NumPy/SciPy import must return a log file, not crash Gradio."""
    image = tmp_path / "image.png"
    image.write_bytes(b"image")
    monkeypatch.setattr(ui, "WORK_ROOT", tmp_path / "work")
    monkeypatch.setattr(ui, "_gpu_snapshot", lambda: "GPU VRAM 0/15360 MiB")
    monkeypatch.setitem(sys.modules, "vtuber_pipeline.core.stage_progress", None)

    updates = list(ui.stream_avatar_ui(
        str(image), "corporation", None, progress=FakeProgress(),
    ))
    assert updates[-1][0].startswith("❌")
    assert "ModuleNotFoundError" in updates[-1][1]
    assert "stage_progress" in updates[-1][1]
    log = pathlib.Path(updates[-1][-1])
    assert log.is_file()
    assert "ModuleNotFoundError" in log.read_text(encoding="utf-8")


def test_avatar_success_publishes_verified_download_for_colab_kernel(
    ui, tmp_path, monkeypatch,
):
    import json

    image = tmp_path / "face.png"
    image.write_bytes(b"png")
    queue = tmp_path / "session"
    monkeypatch.setenv("VTUBER_COLAB_AUTODOWNLOAD_DIR", str(queue))

    def produce(*, image_path, output_dir, config):
        path = pathlib.Path(output_dir) / "avatar.vrm"
        path.write_bytes(b"glTF" + b"0" * 36)
        return {
            "status": "complete", "vrm_path": str(path),
            "stages": {"validator": {"status": "complete"}},
        }

    monkeypatch.setattr(ui, "_pipeline_imports", lambda: (produce, None, None))
    status, logs, download, state = ui.build_avatar_ui(
        str(image), "corporation", None,
    )
    assert status.startswith("✅"), (status, logs)
    assert "직접 다운로드 링크 생성 중" in status
    assert download == state
    events = list(queue.glob("request-*.json"))
    assert len(events) == 1
    content = json.loads(events[0].read_text(encoding="utf-8"))
    assert pathlib.Path(content["path"]).samefile(download)
    assert content["filename"] == "avatar.vrm"


def test_failed_avatar_does_not_publish_or_download(tmp_path, ui, monkeypatch):
    queue = tmp_path / "session"
    monkeypatch.setenv("VTUBER_COLAB_AUTODOWNLOAD_DIR", str(queue))
    image = tmp_path / "face.png"
    image.write_bytes(b"png")

    monkeypatch.setattr(
        ui, "_pipeline_imports",
        lambda: (lambda **kwargs: {
            "status": "failed", "failed_reason": "template fit invalid",
            "stages": {"template_fitting": {"status": "error"}},
        }, None, None),
    )
    status, logs, download, state = ui.build_avatar_ui(
        str(image), "corporation", None,
    )
    assert status.startswith("❌"), (status, logs)
    assert download is None
    assert not list(queue.glob("request-*.json")) if queue.is_dir() else True


def test_2d_build_autoprepares_missing_model_marker_without_extra_user_steps(ui, tmp_path, monkeypatch):
    """The user presses Generate once, without a separate 'step 2' button."""
    from PIL import Image
    import vtuber_pipeline.two_d.build as production
    artwork = tmp_path / "character.png"
    Image.new("RGBA", (300, 400), "white").save(artwork)
    events = []
    def ready(mode):
        events.append(("check", mode))
        if len(events) == 1:
            raise RuntimeError("② 모델 다운로드·검증을 먼저 완료하세요.")
        return ("head", ["verified"])
    def prepare(mode, usage):
        events.append(("install", mode, usage))
    monkeypatch.setattr(ui, "require_runtime_ready", ready)
    monkeypatch.setattr(ui, "choose_workflow", prepare)

    def build(source):
        events.append(("build", source.mode, source.user_layers_zip))
        folder = pathlib.Path(source.output_dir)
        folder.mkdir(parents=True, exist_ok=True)
        output = folder / "layers.zip"
        output.write_bytes(b"valid-test-package")
        return types.SimpleNamespace(
            status="needs_editor_export", primary_file=str(output),
            editable_file=str(output), error=None,
        )

    monkeypatch.setattr(production, "build_live2d", build)
    status, report, path = ui.build_live2d_ui(str(artwork), "corporation")
    assert "needs_editor_export" in report
    assert pathlib.Path(path).is_file()
    assert events == [
        ("check", "live2d"),
        ("install", "live2d", "corporation"),
        ("check", "live2d"),
        ("build", "live2d", None),
    ]


def test_model_install_failure_stops_2d_build_without_faking_success(ui, tmp_path, monkeypatch):
    import vtuber_pipeline.two_d.build as production
    image = tmp_path / "character.png"
    image.write_bytes(b"source")
    monkeypatch.setattr(ui, "require_runtime_ready", lambda mode: (_ for _ in ()).throw(
        RuntimeError("② 모델 다운로드·검증을 먼저 완료하세요.")
    ))
    def fail(mode, usage):
        raise RuntimeError("missing compatible CUDA wheel")
    monkeypatch.setattr(ui, "choose_workflow", fail)
    monkeypatch.setattr(production, "build_inochi2d",
                        lambda source: pytest.fail("Cannot build without verified models"))
    status, report, output = ui.build_inochi2d_ui(str(image), "corporation")
    assert "제작 실패" in status
    assert "missing compatible CUDA wheel" in report
    assert output is None


@pytest.mark.parametrize("mode", ["inochi2d", "live2d"])
def test_live_2d_stream_reports_progress_and_keeps_ui_alive_on_worker_failure(
    ui, tmp_path, monkeypatch, mode,
):
    image = tmp_path / "character.png"
    image.write_bytes(b"image")
    monkeypatch.setattr(ui, "_gpu_snapshot", lambda: "GPU available")
    report = []
    def worker(selected, values, on_event=None):
        report.append((selected, values))
        on_event(("stage", "model", "running", "loading"))
        on_event(("log", "model started"))
        return ("❌ worker returned an error", "OOM on isolated worker", None)
    monkeypatch.setattr(ui, "_run_isolated_generation", worker)
    handler = ui.stream_inochi2d_ui if mode == "inochi2d" else ui.stream_live2d_ui
    updates = list(handler(str(image), "corporation", progress=FakeProgress()))
    assert len(updates) >= 2
    assert all(len(update) == 3 for update in updates)
    assert updates[-1][0].startswith("❌")
    assert "model started" in updates[-1][1]
    assert report == [(mode, (str(image), "corporation"))]


@pytest.mark.parametrize("mode", ["inochi2d", "live2d"])
def test_live_2d_empty_photo_does_not_spawn_model_worker(ui, monkeypatch, mode):
    monkeypatch.setattr(ui, "_run_isolated_generation", lambda *a, **kw: pytest.fail(
        "empty photo must not launch models"))
    handler = ui.stream_inochi2d_ui if mode == "inochi2d" else ui.stream_live2d_ui
    assert list(handler(None, "corporation", progress=FakeProgress())) == [
        ("원본 캐릭터 이미지를 업로드하세요.", "", None)
    ]


def test_same_accessory_image_at_multiple_anchors_only_reconstructs_once(
    ui, tmp_path, monkeypatch,
):
    """The ALL option must not duplicate expensive 3D image reconstruction."""
    latest = tmp_path / "base.vrm"
    latest.write_bytes(b"vrm")
    image = tmp_path / "crown.png"
    image.write_bytes(b"pixels")
    mesh = tmp_path / "crown.glb"
    mesh.write_bytes(b"mesh")
    reconstructed = []
    baked = []

    def reconstruct(inputs, output_dir, *, profile):
        reconstructed.append(inputs)
        return [{"status": "complete", "mesh": str(mesh)}]

    class Baker:
        def __init__(self, folder):
            self.folder = pathlib.Path(folder)
        def build(self, *, base_vrm, accessory_glb, config):
            baked.append((base_vrm, accessory_glb, config["anchor_name"]))
            self.folder.mkdir(parents=True, exist_ok=True)
            path = self.folder / "combined.vrm"
            path.write_bytes(b"fake combined")
            return {"status": "complete", "output_vrm": str(path), "stages": {}}

    monkeypatch.setattr(ui, "_pipeline_imports", lambda: (None, reconstruct, Baker))
    values = [
        str(image), "HEAD_TOP", "", 0., 0., 0., 1.,
        str(image), "FACE", "", 0., 0., 0., 1.,
    ]
    status, logs, output = ui.build_accessories_ui(True, None, str(latest), *values)
    assert status.startswith("✅"), (status, logs)
    assert reconstructed == [[str(image)]]
    assert [item[2] for item in baked] == ["HEAD_TOP", "FACE"]
    assert all(item[1] == str(mesh) for item in baked)
    assert pathlib.Path(output).is_file()
