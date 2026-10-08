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
    module._real_require_runtime_ready = module.require_runtime_ready
    monkeypatch.setattr(
        module,
        "require_runtime_ready",
        lambda _progress=None: ("a" * 40, ["runtime-ready"]),
    )
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
    })]


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


def test_start_routes_to_exact_mode_with_selected_scope(ui):
    hidden, avatar, accessory, usage = ui.choose_workflow(
        "avatar", "personalProfit",
    )
    assert hidden["visible"] is False
    assert avatar["visible"] is True
    assert accessory["visible"] is False
    assert usage == "personalProfit"

    hidden, avatar, accessory, usage = ui.choose_workflow(
        "accessory", "corporation",
    )
    assert hidden["visible"] is False
    assert avatar["visible"] is False
    assert accessory["visible"] is True
    assert usage == "corporation"

    assert [v["visible"] for v in ui.return_to_workflow_choice()] == [
        True, False, False,
    ]


@pytest.mark.parametrize(
    "mode,usage",
    [("garbage", "corporation"), ("avatar", "GPL"), ("accessory", "")],
)
def test_workflow_selection_rejects_invalid_mode_or_usage(ui, mode, usage):
    with pytest.raises(ValueError):
        ui.choose_workflow(mode, usage)



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
    assert events == ["reload", "runtime", "build", "queue", "launch"]


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
