"""Model/backend option and I/O contract tests.

These tests verify the actual values crossing the boundaries between user-facing
options, model wrappers, external model invocations, normalized outputs, and
downstream consumers. GPU inference itself is intentionally replaced by
deterministic fakes so this contract runs on every CPU CI build.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import types

import numpy as np
from click.testing import CliRunner
from PIL import Image


def test_anime_face_detector_backend_input_and_output_contract(
    tmp_path,
    monkeypatch,
):
    created_backends = []
    model_inputs = []

    high_keypoints = [
        [float(i), float(i + 1), 0.95]
        for i in range(28)
    ]
    low_keypoints = [
        [float(i), float(i + 1), 0.80]
        for i in range(28)
    ]

    def create_detector(backend):
        created_backends.append(backend)

        def detector(image_bgr):
            model_inputs.append(image_bgr.copy())
            return [
                {
                    "bbox": [0.0, 0.0, 1.0, 1.0, 0.40],
                    "keypoints": low_keypoints,
                },
                {
                    "bbox": [1.0, 2.0, 30.0, 40.0, 0.97],
                    "keypoints": high_keypoints,
                },
            ]

        return detector

    monkeypatch.setitem(
        sys.modules,
        "anime_face_detector",
        types.SimpleNamespace(create_detector=create_detector),
    )

    image_path = tmp_path / "pixel.png"
    image = Image.new("RGB", (2, 1))
    image.putdata([(10, 20, 30), (40, 50, 60)])
    image.save(image_path)

    from vtuber_pipeline.avatar.face_detector import AnimeFaceDetector

    result = AnimeFaceDetector().detect(str(image_path))

    assert created_backends == ["yolov3"]
    assert len(model_inputs) == 1
    assert model_inputs[0].shape == (1, 2, 3)
    assert model_inputs[0][0, 0].tolist() == [30, 20, 10]
    assert model_inputs[0][0, 1].tolist() == [60, 50, 40]

    assert result["bbox"] == [1.0, 2.0, 30.0, 40.0]
    assert result["score"] == 0.97
    assert len(result["landmarks"]) == 28
    assert len(result["landmark_scores"]) == 28
    assert result["landmarks"][0] == [0.0, 1.0]
    assert result["landmark_scores"][0] == 0.95


def test_triposr_wrapper_maps_options_to_cli_timeout_and_output(
    tmp_path,
    monkeypatch,
):
    import vtuber_pipeline.avatar.reconstruction as reconstruction

    triposr_dir = tmp_path / "TripoSR"
    triposr_dir.mkdir()
    run_script = triposr_dir / "run.py"
    run_script.write_text("# fake TripoSR", encoding="utf-8")

    image_path = tmp_path / "character.png"
    image_path.write_bytes(b"image")
    output_dir = tmp_path / "triposr-output"

    captured = {}

    monkeypatch.setattr(
        reconstruction,
        "find_triposr_installation",
        lambda: str(run_script),
    )
    monkeypatch.setattr(
        reconstruction,
        "verify_triposr_revision",
        lambda run_script, profile: captured.setdefault(
            "revision_check",
            (run_script, profile),
        ),
    )
    monkeypatch.setenv("TRIPOSR_TIMEOUT_SECONDS", "77")

    class FakeScene:
        pass

    fake_mesh = types.SimpleNamespace(
        vertices=list(range(16)),
        faces=list(range(8)),
    )
    monkeypatch.setitem(
        sys.modules,
        "trimesh",
        types.SimpleNamespace(
            Scene=FakeScene,
            load=lambda path, process=False: fake_mesh,
        ),
    )

    def fake_run(
        cmd,
        *,
        capture_output,
        text,
        timeout,
        cwd,
    ):
        captured["cmd"] = list(cmd)
        captured["timeout"] = timeout
        captured["cwd"] = cwd

        out_index = cmd.index("--output-dir") + 1
        format_index = cmd.index("--model-save-format") + 1
        requested_output = pathlib.Path(cmd[out_index])
        requested_format = cmd[format_index]
        mesh_path = requested_output / "0" / f"mesh.{requested_format}"
        mesh_path.parent.mkdir(parents=True, exist_ok=True)
        mesh_path.write_bytes(b"mesh")
        return types.SimpleNamespace(
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(reconstruction.subprocess, "run", fake_run)

    result = reconstruction.reconstruct_avatar(
        str(image_path),
        str(output_dir),
        profile="production",
        model_save_format="glb",
        remove_background=False,
    )

    assert captured["revision_check"] == (
        str(run_script),
        "production",
    )
    assert captured["cmd"][0] == sys.executable
    assert captured["cmd"][1] == str(run_script)
    assert captured["cmd"][2] == str(image_path)
    assert captured["cmd"][
        captured["cmd"].index("--output-dir") + 1
    ] == str(output_dir)
    assert captured["cmd"][
        captured["cmd"].index("--model-save-format") + 1
    ] == "glb"
    assert "--no-remove-bg" in captured["cmd"]
    assert captured["timeout"] == 77
    assert captured["cwd"] == str(triposr_dir)
    assert result == str(output_dir / "0" / "mesh.glb")


def test_triposr_background_true_omits_no_remove_bg(
    tmp_path,
    monkeypatch,
):
    import vtuber_pipeline.avatar.reconstruction as reconstruction

    run_script = tmp_path / "run.py"
    run_script.write_text("# fake", encoding="utf-8")
    image_path = tmp_path / "accessory.png"
    image_path.write_bytes(b"image")
    output_dir = tmp_path / "out"
    captured = {}

    monkeypatch.setattr(
        reconstruction,
        "find_triposr_installation",
        lambda: str(run_script),
    )
    monkeypatch.setattr(
        reconstruction,
        "verify_triposr_revision",
        lambda *args, **kwargs: None,
    )

    class FakeScene:
        pass

    monkeypatch.setitem(
        sys.modules,
        "trimesh",
        types.SimpleNamespace(
            Scene=FakeScene,
            load=lambda path, process=False: types.SimpleNamespace(
                vertices=list(range(16)),
                faces=list(range(8)),
            ),
        ),
    )

    def fake_run(cmd, **kwargs):
        captured["cmd"] = list(cmd)
        mesh_path = output_dir / "0" / "mesh.obj"
        mesh_path.parent.mkdir(parents=True, exist_ok=True)
        mesh_path.write_bytes(b"mesh")
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(reconstruction.subprocess, "run", fake_run)

    result = reconstruction.reconstruct_avatar(
        str(image_path),
        str(output_dir),
        model_save_format="obj",
        remove_background=True,
    )

    assert "--no-remove-bg" not in captured["cmd"]
    assert captured["cmd"][
        captured["cmd"].index("--model-save-format") + 1
    ] == "obj"
    assert result.endswith("/0/mesh.obj")


def test_accessory_reconstruction_forwards_model_options_and_maps_outputs(
    tmp_path,
    monkeypatch,
):
    import vtuber_pipeline.accessory.reconstruction as module

    images = [
        str(tmp_path / "hat.png"),
        str(tmp_path / "glasses.png"),
    ]
    calls = []

    def fake_reconstruct(
        image_path,
        output_dir,
        profile="commercial",
        *,
        model_save_format="obj",
        remove_background=True,
    ):
        calls.append(
            {
                "image_path": image_path,
                "output_dir": output_dir,
                "profile": profile,
                "model_save_format": model_save_format,
                "remove_background": remove_background,
            }
        )
        return str(pathlib.Path(output_dir) / f"mesh.{model_save_format}")

    monkeypatch.setattr(module, "reconstruct_avatar", fake_reconstruct)

    result = module.reconstruct_accessories(
        images,
        str(tmp_path / "recon"),
        profile="production",
        model_save_format="obj",
        remove_background=False,
    )

    assert [item["image"] for item in result] == images
    assert [item["status"] for item in result] == [
        "complete",
        "complete",
    ]
    assert [item["mesh"] for item in result] == [
        str(tmp_path / "recon" / "accessory_000" / "mesh.obj"),
        str(tmp_path / "recon" / "accessory_001" / "mesh.obj"),
    ]
    assert all(
        item["model_options"]
        == {
            "profile": "production",
            "model_save_format": "obj",
            "remove_background": False,
        }
        for item in result
    )
    assert [call["profile"] for call in calls] == [
        "production",
        "production",
    ]
    assert [call["model_save_format"] for call in calls] == [
        "obj",
        "obj",
    ]
    assert [call["remove_background"] for call in calls] == [
        False,
        False,
    ]


def test_vrm_export_forwards_normalized_stage_outputs_to_builder(
    tmp_path,
    monkeypatch,
):
    import vtuber_pipeline.avatar.vrm_export as module

    captured = {}
    expressions = {"happy": {"morph_targets": [{"index": 3}]}}
    bone_mapping = {"head": 9}
    springbone = {
        "status": "complete",
        "springs": [{"name": "hair", "joints": []}],
    }
    gaze = {
        "type": "bone",
        "offsetFromHeadBone": [0.0, 0.06, 0.0],
    }

    monkeypatch.setattr(
        module,
        "_validate_for_vrm",
        lambda rig_path, expressions=None: {
            "valid": True,
            "errors": [],
            "checks": {},
        },
    )

    def fake_builder(**kwargs):
        captured.update(kwargs)
        return {
            "status": "complete",
            "vrm_path": str(tmp_path / "avatar.vrm"),
            "vrm_extension": {"specVersion": "1.0"},
            "file_size_bytes": 1234,
        }

    monkeypatch.setattr(module, "_export_vrm_pure", fake_builder)

    result = module.export_vrm(
        rig_path=str(tmp_path / "rigged.glb"),
        output_dir=str(tmp_path / "export"),
        expressions=expressions,
        bone_mapping=bone_mapping,
        commercial_usage="personalNonProfit",
        springbone_config=springbone,
        gaze_config=gaze,
    )

    assert captured == {
        "rigged_glb_path": str(tmp_path / "rigged.glb"),
        "output_dir": str(tmp_path / "export"),
        "expressions": expressions,
        "bone_mapping": bone_mapping,
        "commercial_usage": "personalNonProfit",
        "springbone_config": springbone,
        "look_at_config": gaze,
    }
    assert result["status"] == "complete"
    assert result["vrm_path"] == str(tmp_path / "avatar.vrm")
    assert result["vrm_extension"] == {"specVersion": "1.0"}
    assert result["file_size_bytes"] == 1234


def test_cli_avatar_options_reach_avatar_builder(
    tmp_path,
    monkeypatch,
):
    import vtuber_pipeline.avatar.build as build_module
    from vtuber_pipeline.cli import cli

    image_path = tmp_path / "character.png"
    image_path.write_bytes(b"image")
    captured = {}

    def fake_build_avatar(image, output, config):
        captured["image"] = image
        captured["output"] = output
        captured["config"] = config
        return {
            "status": "complete",
            "stages": {},
            "vrm_path": str(pathlib.Path(output) / "avatar.vrm"),
        }

    monkeypatch.setattr(build_module, "build_avatar", fake_build_avatar)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "avatar",
            "--image",
            str(image_path),
            "--output",
            str(tmp_path / "avatar-output"),
            "--profile",
            "production",
            "--commercial-usage",
            "personalProfit",
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["image"] == str(image_path)
    assert captured["config"] == {
        "profile": "production",
        "commercial_usage": "personalProfit",
    }


def test_model_option_cache_inputs_are_explicit():
    import ast
    import inspect

    from vtuber_pipeline.avatar.build import AvatarPipeline

    tree = ast.parse(inspect.getsource(AvatarPipeline.build))
    matches = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (
            isinstance(func, ast.Attribute)
            and func.attr == "_run_stage"
            and len(node.args) >= 2
        ):
            continue
        first = node.args[0]
        if (
            isinstance(first, ast.Constant)
            and first.value == "reference_reconstruction"
        ):
            matches.append(node)

    assert len(matches) == 1
    cache_inputs = matches[0].args[1]
    assert isinstance(cache_inputs, ast.Tuple)
    assert any(
        isinstance(item, ast.Name)
        and item.id == "reconstruction_options"
        for item in cache_inputs.elts
    )
