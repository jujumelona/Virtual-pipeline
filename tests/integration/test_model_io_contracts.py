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
import pytest
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

    import vtuber_pipeline.avatar.face_detector as face_module

    fake_package = types.SimpleNamespace(create_detector=create_detector)
    monkeypatch.setitem(sys.modules, "anime_face_detector", fake_package)
    monkeypatch.setattr(
        face_module,
        "_create_pinned_anime_face_detector",
        lambda: create_detector("yolov3"),
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
    model_dir = tmp_path / "pinned-model"
    model_dir.mkdir()

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
    monkeypatch.setattr(
        reconstruction,
        "resolve_triposr_model",
        lambda: str(model_dir),
    )
    monkeypatch.setenv("TRIPOSR_TIMEOUT_SECONDS", "77")
    monkeypatch.setenv("MODEL_CHECKSUM_DISABLED", "1")

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
        env,
    ):
        captured["cmd"] = list(cmd)
        captured["timeout"] = timeout
        captured["cwd"] = cwd
        captured["env"] = dict(env)

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
    assert captured["cmd"][1].endswith("triposr_runner.py")
    assert captured["cmd"][2] == str(run_script)
    assert captured["cmd"][3] == str(image_path)
    assert captured["cmd"][
        captured["cmd"].index("--output-dir") + 1
    ] == str(output_dir)
    assert captured["cmd"][
        captured["cmd"].index("--model-save-format") + 1
    ] == "glb"
    assert "--no-remove-bg" in captured["cmd"]
    assert captured["cmd"][
        captured["cmd"].index("--pretrained-model-name-or-path") + 1
    ] == str(model_dir)
    assert captured["timeout"] == 77
    assert captured["cwd"] == str(triposr_dir)
    assert "MODEL_CHECKSUM_DISABLED" not in captured["env"]
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
    model_dir = tmp_path / "pinned-model"
    model_dir.mkdir()

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
    monkeypatch.setattr(
        reconstruction,
        "resolve_triposr_model",
        lambda: str(model_dir),
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
    assert captured["cmd"][
        captured["cmd"].index("--pretrained-model-name-or-path") + 1
    ] == str(model_dir)
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
            "model_revision": module.TRIPOSR_MODEL_REVISION,
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
    import textwrap

    from vtuber_pipeline.avatar.build import AvatarPipeline

    tree = ast.parse(textwrap.dedent(inspect.getsource(AvatarPipeline.build)))
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


def test_model_pins_agree_across_package_lock_code_and_colab():
    import ast
    import json
    import tomllib

    from vtuber_pipeline.avatar.reconstruction import (
        TRIPOSR_MODEL_ID,
        TRIPOSR_MODEL_REVISION,
        TRIPOSR_MODEL_WEIGHT_SHA256,
        TRIPOSR_PINNED_COMMIT,
    )

    root = pathlib.Path(__file__).resolve().parents[2]
    lock = json.loads(
        (root / "third_party.lock.json").read_text(encoding="utf-8")
    )
    pyproject = tomllib.loads(
        (root / "pyproject.toml").read_text(encoding="utf-8")
    )
    colab_source = (root / "tools" / "colab_app.py").read_text(
        encoding="utf-8"
    )
    colab_tree = ast.parse(colab_source)

    constants = {}
    for node in colab_tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Constant)
        ):
            constants[node.targets[0].id] = node.value.value

    tools = lock["tools"]
    assert TRIPOSR_PINNED_COMMIT == tools["triposr"]["source_commit"]
    assert constants["TRIPOSR_COMMIT"] == TRIPOSR_PINNED_COMMIT
    assert tools["triposr"]["model_id"] == TRIPOSR_MODEL_ID
    assert tools["triposr"]["model_revision"] == TRIPOSR_MODEL_REVISION
    assert (
        tools["triposr"]["model_weight_sha256"]
        == TRIPOSR_MODEL_WEIGHT_SHA256
    )

    anime_version = tools["anime_face_detector"]["package_version"]
    project_dependencies = pyproject["project"]["dependencies"]
    assert f"anime-face-detector=={anime_version}" in project_dependencies
    assert f'"anime-face-detector=={anime_version}"' in colab_source


def test_invalid_reconstruction_option_type_fails_before_model_call(tmp_path):
    from vtuber_pipeline.avatar.build import AvatarPipeline

    result = AvatarPipeline(
        str(tmp_path / "out"),
        config={
            "reconstruction": {
                "remove_background": "false",
            }
        },
    ).build(str(tmp_path / "source.png"))

    assert result["status"] == "failed"
    assert result["failed_stages"] == ["orchestrator"]
    assert "remove_background" in result["failed_reason"]


def test_gaze_limits_are_serialized_into_vrm_range_maps():
    from vtuber_pipeline.avatar.vrm_builder import create_vrm_extension

    gltf = types.SimpleNamespace(meshes=[], nodes=[])
    extension = create_vrm_extension(
        gltf,
        bone_mapping={},
        look_at_config={
            "type": "bone",
            "offsetFromHeadBone": [0.01, 0.07, -0.02],
            "yaw_limit_deg": 33.0,
            "pitch_limit_deg": 17.0,
        },
        commercial_usage="corporation",
    )

    look_at = extension["lookAt"]
    assert look_at["offsetFromHeadBone"] == [0.01, 0.07, -0.02]
    assert look_at["type"] == "bone"
    assert look_at["rangeMapHorizontalInner"] == {
        "inputMaxValue": 90.0,
        "outputScale": 33.0,
    }
    assert look_at["rangeMapHorizontalOuter"] == {
        "inputMaxValue": 90.0,
        "outputScale": 33.0,
    }
    assert look_at["rangeMapVerticalDown"] == {
        "inputMaxValue": 90.0,
        "outputScale": 17.0,
    }
    assert look_at["rangeMapVerticalUp"] == {
        "inputMaxValue": 90.0,
        "outputScale": 17.0,
    }


def test_product_validator_rejects_dead_look_at_range_maps(monkeypatch):
    from vtuber_pipeline.avatar.validator import VRMValidator

    validator = VRMValidator("unused.vrm", product_contract=True)
    monkeypatch.setattr(
        validator,
        "parse_vrm",
        lambda: {
            "lookAt": {
                "type": "bone",
                "offsetFromHeadBone": [0.0, 0.06, 0.0],
                "rangeMapHorizontalInner": {
                    "inputMaxValue": 90.0,
                    "outputScale": 30.0,
                },
                "rangeMapHorizontalOuter": {
                    "inputMaxValue": 90.0,
                    "outputScale": 30.0,
                },
                "rangeMapVerticalDown": {
                    "inputMaxValue": 90.0,
                    "outputScale": 20.0,
                },
                "rangeMapVerticalUp": {
                    "inputMaxValue": 90.0,
                    "outputScale": 0.0,
                },
            }
        },
    )

    result = validator.validate_look_at()
    assert result["valid"] is False
    assert result["range_maps"]["rangeMapVerticalUp"]["outputScale"] == 0.0


def test_triposr_model_resolver_uses_exact_hf_revision_and_hash(
    tmp_path,
    monkeypatch,
):
    import hashlib
    import vtuber_pipeline.avatar.reconstruction as reconstruction

    model_dir = tmp_path / "snapshot"
    model_dir.mkdir()
    (model_dir / "config.yaml").write_text(
        __import__("json").dumps(reconstruction.TRIPOSR_MODEL_CONFIG),
        encoding="utf-8",
    )
    weight_bytes = b"pinned-trip-osr-weights"
    (model_dir / "model.ckpt").write_bytes(weight_bytes)

    expected_hash = hashlib.sha256(weight_bytes).hexdigest()
    monkeypatch.setattr(
        reconstruction,
        "TRIPOSR_MODEL_WEIGHT_SHA256",
        expected_hash,
    )
    monkeypatch.delenv("TRIPOSR_MODEL_DIR", raising=False)

    calls = []

    def fake_download(*, repo_id, filename, revision):
        calls.append((repo_id, filename, revision))
        return str(model_dir / filename)

    monkeypatch.setitem(
        sys.modules,
        "huggingface_hub",
        types.SimpleNamespace(hf_hub_download=fake_download),
    )
    reconstruction.resolve_triposr_model.cache_clear()
    try:
        resolved = reconstruction.resolve_triposr_model()
    finally:
        reconstruction.resolve_triposr_model.cache_clear()

    assert resolved == str(model_dir.resolve())
    assert calls == [
        (
            reconstruction.TRIPOSR_MODEL_ID,
            "config.yaml",
            reconstruction.TRIPOSR_MODEL_REVISION,
        ),
        (
            reconstruction.TRIPOSR_MODEL_ID,
            "model.ckpt",
            reconstruction.TRIPOSR_MODEL_REVISION,
        ),
    ]


def test_triposr_model_resolver_rejects_weight_hash_mismatch(
    tmp_path,
    monkeypatch,
):
    import pytest
    import vtuber_pipeline.avatar.reconstruction as reconstruction

    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "config.yaml").write_text(
        __import__("json").dumps(reconstruction.TRIPOSR_MODEL_CONFIG),
        encoding="utf-8",
    )
    (model_dir / "model.ckpt").write_bytes(b"wrong-weights")

    monkeypatch.setenv("TRIPOSR_MODEL_DIR", str(model_dir))
    monkeypatch.setattr(
        reconstruction,
        "TRIPOSR_MODEL_WEIGHT_SHA256",
        "0" * 64,
    )

    reconstruction.resolve_triposr_model.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="SHA256 mismatch"):
            reconstruction.resolve_triposr_model()
    finally:
        reconstruction.resolve_triposr_model.cache_clear()


def test_triposr_model_resolver_rejects_config_semantic_mismatch(
    tmp_path,
    monkeypatch,
):
    import hashlib
    import json
    import pytest
    import vtuber_pipeline.avatar.reconstruction as reconstruction

    model_dir = tmp_path / "model"
    model_dir.mkdir()
    bad_config = dict(reconstruction.TRIPOSR_MODEL_CONFIG)
    bad_config["image_tokenizer"] = {
        "pretrained_model_name_or_path": "some/other-model",
    }
    (model_dir / "config.yaml").write_text(
        json.dumps(bad_config),
        encoding="utf-8",
    )
    weight_bytes = b"valid-weight-for-config-test"
    (model_dir / "model.ckpt").write_bytes(weight_bytes)

    monkeypatch.setenv("TRIPOSR_MODEL_DIR", str(model_dir))
    monkeypatch.setattr(
        reconstruction,
        "TRIPOSR_MODEL_WEIGHT_SHA256",
        hashlib.sha256(weight_bytes).hexdigest(),
    )

    reconstruction.resolve_triposr_model.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="config mismatch"):
            reconstruction.resolve_triposr_model()
    finally:
        reconstruction.resolve_triposr_model.cache_clear()


def test_triposr_runner_forces_nested_dino_revision(monkeypatch):
    import vtuber_pipeline.avatar.triposr_runner as runner

    calls = []

    def original(repo_id, filename, *args, **kwargs):
        calls.append((repo_id, filename, args, kwargs))
        return "/tmp/fake"

    fake_hub = types.SimpleNamespace(hf_hub_download=original)
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake_hub)

    runner._install_hf_revision_guard()

    fake_hub.hf_hub_download(
        runner.DINO_MODEL_ID,
        "config.json",
    )
    assert calls[-1][3]["revision"] == runner.DINO_MODEL_REVISION

    with pytest.raises(RuntimeError, match="Unexpected Hugging Face repository"):
        fake_hub.hf_hub_download(
            "some/other-model",
            "config.json",
        )

    with pytest.raises(RuntimeError, match="Unexpected DINO artifact"):
        fake_hub.hf_hub_download(
            runner.DINO_MODEL_ID,
            "model.safetensors",
        )

    with pytest.raises(RuntimeError, match="revision override rejected"):
        fake_hub.hf_hub_download(
            runner.DINO_MODEL_ID,
            "config.json",
            revision="floating-main",
        )


def test_triposr_runner_forces_commercial_safe_rembg_model(monkeypatch):
    import vtuber_pipeline.avatar.triposr_runner as runner

    calls = []

    def original(model_name="bria-rmbg", *args, **kwargs):
        calls.append((model_name, args, kwargs))
        return object()

    fake_rembg = types.SimpleNamespace(new_session=original)
    monkeypatch.setitem(sys.modules, "rembg", fake_rembg)

    runner._install_rembg_model_guard()

    fake_rembg.new_session()
    assert calls == [(runner.REMBG_MODEL_NAME, (), {})]
    assert runner.REMBG_MODEL_NAME == "u2net"

    with pytest.raises(RuntimeError, match="Unexpected rembg model"):
        fake_rembg.new_session("bria-rmbg")


def test_anime_face_model_resolver_pins_and_hashes_both_weights(
    tmp_path,
    monkeypatch,
):
    import hashlib
    import vtuber_pipeline.avatar.face_detector as module

    yolo = tmp_path / "yolo.safetensors"
    hrnet = tmp_path / "hrnet.safetensors"
    yolo.write_bytes(b"yolo-weight-bytes")
    hrnet.write_bytes(b"hrnet-weight-bytes")

    yolo_repo = "hysts/anime-face-detector-yolov3"
    hrnet_repo = "hysts/anime-face-detector-hrnetv2"
    pins = {
        yolo_repo: {
            "revision": "yolo-revision",
            "sha256": hashlib.sha256(yolo.read_bytes()).hexdigest(),
        },
        hrnet_repo: {
            "revision": "hrnet-revision",
            "sha256": hashlib.sha256(hrnet.read_bytes()).hexdigest(),
        },
    }
    monkeypatch.setattr(module, "ANIME_FACE_MODEL_PINS", pins)

    calls = []

    def fake_download(*, repo_id, filename, revision):
        calls.append((repo_id, filename, revision))
        return str(yolo if repo_id == yolo_repo else hrnet)

    fake_hub = types.ModuleType("huggingface_hub")
    fake_hub.hf_hub_download = fake_download
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake_hub)

    resolved = module.resolve_anime_face_model_paths()

    assert resolved == {
        yolo_repo: str(yolo.resolve()),
        hrnet_repo: str(hrnet.resolve()),
    }
    assert calls == [
        (yolo_repo, "model.safetensors", "yolo-revision"),
        (hrnet_repo, "model.safetensors", "hrnet-revision"),
    ]


def test_anime_face_detector_uses_only_preverified_local_weights(
    tmp_path,
    monkeypatch,
):
    import vtuber_pipeline.avatar.face_detector as module

    yolo_repo = "hysts/anime-face-detector-yolov3"
    hrnet_repo = "hysts/anime-face-detector-hrnetv2"
    yolo = tmp_path / "yolo.safetensors"
    hrnet = tmp_path / "hrnet.safetensors"
    yolo.write_bytes(b"yolo")
    hrnet.write_bytes(b"hrnet")

    monkeypatch.setattr(
        module,
        "resolve_anime_face_model_paths",
        lambda: {
            yolo_repo: str(yolo),
            hrnet_repo: str(hrnet),
        },
    )

    calls = []
    detector_module = types.ModuleType("anime_face_detector.detector")

    def forbidden_network(*args, **kwargs):
        raise AssertionError("network downloader must be replaced during detector creation")

    detector_module.hf_hub_download = forbidden_network

    face_module = types.ModuleType("anime_face_detector._face")
    landmark_module = types.ModuleType("anime_face_detector._landmark")
    old_loader = lambda path: None
    face_module.load_state_dict_from_path = old_loader
    landmark_module.load_state_dict_from_path = old_loader
    safetensors_package = types.ModuleType("safetensors")
    safetensors_package.__path__ = []
    safetensors_torch = types.ModuleType("safetensors.torch")
    safetensors_torch.load_file = lambda path, device="cpu": {"path": path}
    safetensors_package.torch = safetensors_torch

    package = types.ModuleType("anime_face_detector")
    package.__path__ = []
    package.detector = detector_module
    package._face = face_module
    package._landmark = landmark_module
    sentinel = object()

    def fake_create_detector(name):
        assert name == "yolov3"
        calls.append(
            detector_module.hf_hub_download(
                hrnet_repo,
                "model.safetensors",
            )
        )
        calls.append(
            detector_module.hf_hub_download(
                yolo_repo,
                "model.safetensors",
            )
        )
        assert landmark_module.load_state_dict_from_path(str(hrnet)) == {
            "path": str(hrnet)
        }
        assert face_module.load_state_dict_from_path(str(yolo)) == {
            "path": str(yolo)
        }
        return sentinel

    package.create_detector = fake_create_detector
    monkeypatch.setitem(sys.modules, "anime_face_detector", package)
    monkeypatch.setitem(
        sys.modules,
        "anime_face_detector.detector",
        detector_module,
    )
    monkeypatch.setitem(sys.modules, "anime_face_detector._face", face_module)
    monkeypatch.setitem(sys.modules, "anime_face_detector._landmark", landmark_module)
    monkeypatch.setitem(sys.modules, "safetensors", safetensors_package)
    monkeypatch.setitem(sys.modules, "safetensors.torch", safetensors_torch)

    result = module._create_pinned_anime_face_detector()

    assert result is sentinel
    assert calls == [str(hrnet), str(yolo)]
    assert detector_module.hf_hub_download is forbidden_network
    assert face_module.load_state_dict_from_path is old_loader
    assert landmark_module.load_state_dict_from_path is old_loader


def test_anime_face_model_resolver_rejects_weight_hash_mismatch(
    tmp_path,
    monkeypatch,
):
    import vtuber_pipeline.avatar.face_detector as module

    model = tmp_path / "model.safetensors"
    model.write_bytes(b"tampered")
    repo_id = "hysts/anime-face-detector-yolov3"

    monkeypatch.setattr(
        module,
        "ANIME_FACE_MODEL_PINS",
        {
            repo_id: {
                "revision": "pinned",
                "sha256": "0" * 64,
            }
        },
    )

    fake_hub = types.ModuleType("huggingface_hub")
    fake_hub.hf_hub_download = (
        lambda **kwargs: str(model)
    )
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake_hub)

    with pytest.raises(RuntimeError, match="SHA256 mismatch"):
        module.resolve_anime_face_model_paths()
