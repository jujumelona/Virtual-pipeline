"""Runtime module-graph and producer/consumer contract tests.

These tests exercise real Python imports and real orchestrator call paths while
replacing GPU/model work with deterministic fakes. They are intended to catch
module moves, stale public exports, broken stage handoffs, and entry-point
wiring before a Colab GPU run.
"""

from __future__ import annotations

import ast
import importlib
import importlib.util
import pathlib
import pkgutil

import pytest

from click.testing import CliRunner


ROOT = pathlib.Path(__file__).resolve().parents[2]
PACKAGE_ROOT = ROOT / "vtuber_pipeline"


def test_every_vtuber_pipeline_module_imports():
    import vtuber_pipeline

    names = [vtuber_pipeline.__name__]
    names.extend(
        item.name
        for item in pkgutil.walk_packages(
            vtuber_pipeline.__path__,
            vtuber_pipeline.__name__ + ".",
        )
    )

    failures = {}
    for name in sorted(set(names)):
        try:
            importlib.import_module(name)
        except Exception as exc:  # pragma: no cover - assertion reports detail
            failures[name] = f"{type(exc).__name__}: {exc}"

    assert failures == {}


def test_all_internal_import_targets_resolve():
    missing = []

    for path in sorted(PACKAGE_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            targets = []
            if isinstance(node, ast.Import):
                targets.extend(
                    alias.name
                    for alias in node.names
                    if alias.name == "vtuber_pipeline"
                    or alias.name.startswith("vtuber_pipeline.")
                )
            elif isinstance(node, ast.ImportFrom):
                if node.module and (
                    node.module == "vtuber_pipeline"
                    or node.module.startswith("vtuber_pipeline.")
                ):
                    targets.append(node.module)

            for target in targets:
                if importlib.util.find_spec(target) is None:
                    missing.append(
                        f"{path.relative_to(ROOT)}:{node.lineno}: {target}"
                    )

    assert missing == []


def test_public_all_exports_exist():
    missing = {}
    for module_name in (
        "vtuber_pipeline",
        "vtuber_pipeline.avatar",
        "vtuber_pipeline.accessory",
        "vtuber_pipeline.core",
    ):
        module = importlib.import_module(module_name)
        absent = [
            name
            for name in getattr(module, "__all__", ())
            if not hasattr(module, name)
        ]
        if absent:
            missing[module_name] = absent

    assert missing == {}


def test_avatar_orchestrator_runtime_handoffs(tmp_path, monkeypatch):
    from vtuber_pipeline.avatar.build import AvatarPipeline
    from vtuber_pipeline.avatar.reconstruction import TRIPOSR_MODEL_REVISION
    import vtuber_pipeline.avatar.blender_bridge as blender_module
    import vtuber_pipeline.avatar.expressions as expressions_module
    import vtuber_pipeline.avatar.gaze as gaze_module
    import vtuber_pipeline.avatar.input_gate as input_gate_module
    import vtuber_pipeline.avatar.reconstruction as reconstruction_module
    import vtuber_pipeline.avatar.rigging as rigging_module
    import vtuber_pipeline.avatar.springbone as springbone_module
    import vtuber_pipeline.avatar.template_fitting as fitting_module
    import vtuber_pipeline.avatar.template_mesh as template_module
    import vtuber_pipeline.avatar.texture_transfer as texture_module
    import vtuber_pipeline.avatar.validator as validator_module
    import vtuber_pipeline.avatar.vrm_export as export_module

    source = tmp_path / "source.png"
    from PIL import Image
    Image.new("RGBA", (512, 768), (240, 180, 150, 255)).save(source)

    artifacts = {
        name: tmp_path / name
        for name in (
            "reference.glb",
            "template.glb",
            "fitted.glb",
            "texture.png",
            "uv.npy",
            "rigged.glb",
            "avatar.vrm",
            "avatar_rigged.blend",
        )
    }
    for path in artifacts.values():
        path.write_bytes(path.name.encode("utf-8"))

    calls = []
    landmarks = [[float(i), float(i + 1)] for i in range(28)]
    expression_map = {
        "happy": {"morph_targets": [{"index": 0, "weight": 1.0}]}
    }
    expected_gaze_config = {"type": "bone", "offsetFromHeadBone": [0.0, 0.0, 0.0]}
    spring_config = {"status": "complete", "springs": [{"name": "hair"}]}

    def fake_gate(image_path, output_dir):
        calls.append("input_gate")
        assert image_path == str(source)
        return {
            "status": "complete",
            "valid": True,
            "landmarks": landmarks,
            "bbox": [1.0, 2.0, 3.0, 4.0],
        }

    def fake_reconstruct(
        image_path,
        output_dir,
        profile="commercial",
        *,
        model_save_format="obj",
        remove_background=True,
    ):
        calls.append("reference_reconstruction")
        assert image_path == str(source)
        assert profile == "production"
        assert model_save_format == "glb"
        assert remove_background is False
        return str(artifacts["reference.glb"])

    def fake_fit(
        template_path,
        received_landmarks,
        output_dir,
        config,
        *,
        reference_mesh_path,
    ):
        calls.append("template_fitting")
        assert template_path == str(artifacts["template.glb"])
        assert received_landmarks == landmarks
        assert reference_mesh_path == str(artifacts["reference.glb"])
        assert config == {
            "fitting_objective": {
                "lambda_landmark": 1.7,
                "lambda_surface": 0.6,
                "lambda_laplacian": 0.12,
                "lambda_symmetry": 0.25,
            }
        }
        return {
            "status": "complete",
            "fitted_mesh": str(artifacts["fitted.glb"]),
        }

    def fake_texture(
        image_path, mesh_path, output_dir, face_bbox=None, *,
        face_image_path=None, back_image_path=None,
        left_image_path=None, right_image_path=None,
        full_body=False, texture_size=1024,
    ):
        assert face_image_path is None
        assert back_image_path is None
        assert left_image_path is None
        assert right_image_path is None
        assert full_body is False
        assert texture_size == 1024
        calls.append("texture_transfer")
        assert image_path == str(source)
        assert mesh_path == str(artifacts["fitted.glb"])
        assert face_bbox == [1.0, 2.0, 3.0, 4.0]
        return {
            "status": "complete",
            "texture_png": str(artifacts["texture.png"]),
            "uv_path": str(artifacts["uv.npy"]),
        }

    def fake_rig(mesh_path, output_path, *, texture_path, uv_path):
        calls.append("rig")
        assert mesh_path == str(artifacts["fitted.glb"])
        assert texture_path == str(artifacts["texture.png"])
        assert uv_path == str(artifacts["uv.npy"])
        return str(artifacts["rigged.glb"])

    def fake_generate_expressions(rigged_mesh):
        calls.append("expressions")
        assert rigged_mesh == str(artifacts["rigged.glb"])
        return {"status": "complete", "expressions": expression_map}

    def fake_validate_expressions(expressions, output_dir):
        assert expressions is expression_map
        return {
            "pass": True,
            "required_expressions": ["happy"],
            "missing_expressions": [],
        }

    def fake_gaze(rigged_mesh, output_dir):
        calls.append("gaze")
        assert rigged_mesh == str(artifacts["rigged.glb"])
        return {"status": "complete", "config": expected_gaze_config}

    def fake_springbone(rigged_mesh, output_dir):
        calls.append("springbone")
        assert rigged_mesh == str(artifacts["rigged.glb"])
        return spring_config

    def fake_export(
        rigged_mesh,
        output_dir,
        *,
        expressions,
        commercial_usage,
        springbone_config,
        gaze_config,
    ):
        calls.append("vrm_export")
        assert rigged_mesh == str(artifacts["rigged.glb"])
        assert expressions is expression_map
        assert commercial_usage == "personalProfit"
        assert springbone_config is spring_config
        assert gaze_config is expected_gaze_config
        return {
            "status": "complete",
            "vrm_path": str(artifacts["avatar.vrm"]),
        }

    def fake_blender(vrm_path, output_dir):
        calls.append("blender_vrm_export")
        assert vrm_path == str(artifacts["avatar.vrm"])
        return {
            "status": "complete",
            "vrm_path": vrm_path,
            "blend": str(artifacts["avatar_rigged.blend"]),
        }

    def fake_validate(vrm_path, output_dir, **kwargs):
        # The final common completion contract performs a second product-level
        # validation. Keep the legacy stage trace scoped to its first call.
        if not kwargs.get("product_contract"):
            calls.append("validator")
        assert vrm_path == str(artifacts["avatar.vrm"])
        return {"status": "complete", "passed": True}

    monkeypatch.setattr(input_gate_module, "validate_input", fake_gate)
    monkeypatch.setattr(
        reconstruction_module, "reconstruct_avatar", fake_reconstruct
    )
    monkeypatch.setattr(
        template_module,
        "get_template_path",
        lambda: artifacts["template.glb"],
    )
    monkeypatch.setattr(fitting_module, "fit_template", fake_fit)
    monkeypatch.setattr(texture_module, "transfer_texture", fake_texture)
    monkeypatch.setattr(rigging_module, "rig_avatar", fake_rig)
    monkeypatch.setattr(
        expressions_module,
        "generate_expressions",
        fake_generate_expressions,
    )
    monkeypatch.setattr(
        expressions_module,
        "validate_expressions",
        fake_validate_expressions,
    )
    monkeypatch.setattr(gaze_module, "configure_gaze", fake_gaze)
    monkeypatch.setattr(
        springbone_module,
        "generate_springbone_config",
        fake_springbone,
    )
    monkeypatch.setattr(export_module, "export_vrm", fake_export)
    monkeypatch.setattr(blender_module, "export_blender_from_vrm", fake_blender)
    monkeypatch.setattr(validator_module, "validate_vrm", fake_validate)

    result = AvatarPipeline(
        str(tmp_path / "out"),
        config={
            "profile": "production",
            "commercial_usage": "personalProfit",
            "reconstruction": {
                "model_save_format": "glb",
                "remove_background": False,
            },
            "fitting": {
                "fitting_objective": {
                    "lambda_landmark": 1.7,
                    "lambda_surface": 0.6,
                    "lambda_laplacian": 0.12,
                    "lambda_symmetry": 0.25,
                }
            },
        },
    ).build(str(source))

    assert result["status"] == "complete", result
    assert result["vrm_path"] == str(artifacts["avatar.vrm"])
    assert pathlib.Path(result["production_result_json"]).is_file()
    assert result["build_result"]["primary_file"] == result["vrm_path"]
    assert result["stages"]["reference_reconstruction"]["model_options"] == {
        "profile": "production",
        "model_save_format": "glb",
        "remove_background": False,
        "model_revision": TRIPOSR_MODEL_REVISION,
    }
    assert calls == [
        "input_gate",
        "reference_reconstruction",
        "template_fitting",
        "texture_transfer",
        "rig",
        "expressions",
        "gaze",
        "springbone",
        "vrm_export",
        "blender_vrm_export",
        "validator",
    ]


def test_accessory_orchestrator_runtime_handoffs(tmp_path, monkeypatch):
    from vtuber_pipeline.accessory.build import AccessoryPipeline
    import vtuber_pipeline.accessory.anchors as anchors_module
    import vtuber_pipeline.accessory.artifacts as artifacts_module
    import vtuber_pipeline.accessory.bake as bake_module
    import vtuber_pipeline.accessory.collision as collision_module
    import vtuber_pipeline.accessory.fitting as fitting_module
    import vtuber_pipeline.accessory.normalize as normalize_module
    import vtuber_pipeline.avatar.validator as validator_module

    base_vrm = tmp_path / "base.vrm"
    accessory = tmp_path / "source.glb"
    base_vrm.write_bytes(b"vrm")
    accessory.write_bytes(b"glb")

    calls = []
    seen = {}
    custom_anchor = {
        "parent_bone": "upperChest",
        "offset": [0.1, 0.2, 0.3],
        "target_size": 0.42,
    }

    def fake_normalize(input_path, output_path):
        calls.append("normalize")
        assert input_path == str(accessory)
        # The new visual alignment handler inspects actual triangle bounds.
        # Keep GPU reconstruction mocked, but use a real trivial GLB so the
        # CPU contact-pivot stage cannot be satisfied by a fake byte suffix.
        import trimesh
        trimesh.creation.box(extents=[0.2, 0.4, 0.3]).export(output_path)
        seen["normalized"] = output_path
        return {"status": "complete", "output_path": output_path}

    def fake_anchors(vrm_path, output_dir, custom_anchor=None):
        calls.append("anchors")
        assert vrm_path == str(base_vrm)
        assert custom_anchor == {
            "parent_bone": "upperChest",
            "offset": [0.1, 0.2, 0.3],
            "target_size": 0.42,
        }
        return {
            "status": "complete",
            "anchors": [
                {
                    "name": "CUSTOM",
                    "bone": "upperChest",
                    "node_index": 3,
                    "position": [1.0, 2.0, 3.0],
                    "offset": [0.1, 0.2, 0.3],
                    "target_size": 0.42,
                }
            ],
        }

    def fake_fit(mesh_path, anchor_name, anchor_manifest, output_dir, *, visual_alignment=None):
        assert isinstance(visual_alignment, dict)
        assert visual_alignment["status"] == "complete"
        assert visual_alignment["anchor_name"] == "CUSTOM"
        assert visual_alignment["parent_bone"] == "upperChest"
        assert pathlib.Path(visual_alignment["alignment_json"]).is_file()
        calls.append("fit")
        assert mesh_path == seen["normalized"]
        assert anchor_name == "CUSTOM"
        assert anchor_manifest["status"] == "complete"
        assert anchor_manifest["anchors"][0]["target_size"] == 0.42
        fitted = pathlib.Path(output_dir) / "fitted.glb"
        fitted.write_bytes(b"fitted")
        seen["fitted"] = str(fitted)
        return {
            "status": "complete",
            "output_path": str(fitted),
            "parent_bone": "upperChest",
            "transform": {
                "translation": [0.1, 0.2, 0.3],
                "rotation": [0.0, 0.0, 0.0, 1.0],
                "scale": [1.0, 1.0, 1.0],
            },
            "world_transform": {
                "translation": [1.0, 2.0, 3.0],
                "rotation": [0.0, 0.0, 0.0, 1.0],
                "scale": [1.0, 1.0, 1.0],
            },
            "world_to_local_linear": [
                [1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [0.0, 0.0, 1.0],
            ],
        }

    def fake_collision(
        mesh_path,
        vrm_path,
        world_transform=None,
        clearance=0.003,
    ):
        calls.append("collision")
        assert mesh_path == seen["fitted"]
        assert vrm_path == str(base_vrm)
        assert world_transform == {
            "translation": [1.0, 2.0, 3.0],
            "rotation": [0.0, 0.0, 0.0, 1.0],
            "scale": [1.0, 1.0, 1.0],
        }
        assert clearance == 0.007
        return {
            "status": "complete",
            "resolved": True,
            "pushout_vector": [0.01, 0.0, 0.0],
        }

    def fake_attachment(
        mesh_path,
        anchor_name,
        fit_result,
        collision_result,
        output_dir,
    ):
        calls.append("attachment")
        assert mesh_path == seen["fitted"]
        assert anchor_name == "CUSTOM"
        assert fit_result["parent_bone"] == "upperChest"
        assert fit_result["transform"]["translation"] == [
            0.11,
            0.2,
            0.3,
        ]
        output = pathlib.Path(output_dir) / "attachment.json"
        output.write_text("{}", encoding="utf-8")
        return {"status": "complete", "output_path": str(output)}

    def fake_preview(mesh_path, output_dir):
        calls.append("preview")
        assert mesh_path == seen["fitted"]
        output = pathlib.Path(output_dir) / "preview.png"
        output.write_bytes(b"preview")
        return {"status": "complete", "output_path": str(output)}

    def fake_bake(
        vrm_path,
        accessory_paths,
        output_vrm,
        *,
        attachment_config,
    ):
        calls.append("bake")
        assert vrm_path == str(base_vrm)
        assert accessory_paths == [seen["fitted"]]
        assert attachment_config == {
            pathlib.Path(seen["fitted"]).stem: {
                "translation": [0.11, 0.2, 0.3],
                "rotation": [0.0, 0.0, 0.0, 1.0],
                "scale": [1.0, 1.0, 1.0],
                "parent_bone": "upperChest",
            }
        }
        pathlib.Path(output_vrm).write_bytes(b"combined")
        seen["combined"] = output_vrm
        return {"status": "complete", "output_path": output_vrm}

    def fake_validate(vrm_path, output_dir, *, product_contract=True):
        calls.append("validator")
        assert vrm_path == seen["combined"]
        assert product_contract is True
        return {"status": "complete", "passed": True}

    monkeypatch.setattr(normalize_module, "normalize_glb", fake_normalize)
    monkeypatch.setattr(
        anchors_module,
        "generate_anchor_manifest",
        fake_anchors,
    )
    monkeypatch.setattr(fitting_module, "fit_accessory", fake_fit)
    monkeypatch.setattr(
        collision_module,
        "resolve_collision",
        fake_collision,
    )
    monkeypatch.setattr(
        artifacts_module,
        "write_attachment_manifest",
        fake_attachment,
    )
    monkeypatch.setattr(
        artifacts_module,
        "render_preview",
        fake_preview,
    )
    monkeypatch.setattr(bake_module, "bake_accessories", fake_bake)
    monkeypatch.setattr(validator_module, "validate_vrm", fake_validate)

    result = AccessoryPipeline(str(tmp_path / "acc-out")).build(
        base_vrm=str(base_vrm),
        accessory_glb=str(accessory),
        config={
            "anchor_name": "CUSTOM",
            "custom_anchor": custom_anchor,
            "collision": {"clearance": 0.007},
            "bake": True,
        },
    )

    assert result["status"] == "complete", result
    assert result["output_vrm"] == seen["combined"]
    assert result["stages"]["visual_alignment"]["pivot_rule"] == "center_of_bounds"
    assert calls == [
        "normalize",
        "anchors",
        "fit",
        "collision",
        "attachment",
        "preview",
        "bake",
        "validator",
    ]


def test_cli_multi_accessory_runtime_chain(tmp_path, monkeypatch):
    import vtuber_pipeline.accessory.build as build_module
    import vtuber_pipeline.accessory.reconstruction as reconstruction_module
    from vtuber_pipeline.cli import cli

    base = tmp_path / "base.vrm"
    image_a = tmp_path / "a.png"
    image_b = tmp_path / "b.png"
    mesh_a = tmp_path / "a.glb"
    mesh_b = tmp_path / "b.glb"
    for path in (base, image_a, image_b, mesh_a, mesh_b):
        path.write_bytes(path.name.encode("utf-8"))

    seen_bases = []

    def fake_reconstruct(images, output_dir, profile="commercial"):
        assert images == [str(image_a), str(image_b)]
        return [
            {
                "status": "complete",
                "image": str(image_a),
                "mesh": str(mesh_a),
            },
            {
                "status": "complete",
                "image": str(image_b),
                "mesh": str(mesh_b),
            },
        ]

    class FakeAccessoryPipeline:
        def __init__(self, output_dir, config=None):
            self.output_dir = pathlib.Path(output_dir)
            self.output_dir.mkdir(parents=True, exist_ok=True)

        def build(self, *, base_vrm, accessory_glb):
            seen_bases.append(base_vrm)
            output = self.output_dir / "combined.vrm"
            output.write_bytes(accessory_glb.encode("utf-8"))
            return {
                "status": "complete",
                "output_vrm": str(output),
            }

    monkeypatch.setattr(
        reconstruction_module,
        "reconstruct_accessories",
        fake_reconstruct,
    )
    monkeypatch.setattr(
        build_module,
        "AccessoryPipeline",
        FakeAccessoryPipeline,
    )

    runner = CliRunner()
    output_dir = tmp_path / "cli-output"
    result = runner.invoke(
        cli,
        [
            "accessory",
            "--base-vrm",
            str(base),
            "--images",
            str(image_a),
            "--images",
            str(image_b),
            "--output",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    first_output = output_dir / "accessory_001" / "combined.vrm"
    assert seen_bases == [str(base), str(first_output)]
    assert "VRM:" in result.output


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (["--anchor", "HEAD_TOP"], "exactly once"),
        (["--anchor", "CUSTOM", "--anchor", "HEAD_TOP"], "--custom-anchor must"),
        (
            ["--anchor", "CUSTOM", "--anchor", "HEAD_TOP",
             "--custom-anchor", "head,nan,0,0,0.2"],
            "finite numbers",
        ),
        (
            ["--anchor", "CUSTOM", "--anchor", "HEAD_TOP",
             "--custom-anchor", "head,0,0,0,nan"],
            "finite numbers",
        ),
    ],
)
def test_cli_accessory_preflight_rejects_invalid_slots_before_gpu(
    tmp_path, monkeypatch, args, expected,
):
    import vtuber_pipeline.accessory.reconstruction as reconstruction_module
    from vtuber_pipeline.cli import cli

    base = tmp_path / "base.vrm"
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    for path in (base, first, second):
        path.write_bytes(b"input")

    def should_not_reconstruct(*_args, **_kwargs):
        pytest.fail("Invalid CLI options must never trigger GPU reconstruction")

    monkeypatch.setattr(
        reconstruction_module, "reconstruct_accessories", should_not_reconstruct,
    )
    output_dir = tmp_path / "should-not-be-created"
    result = CliRunner().invoke(
        cli,
        [
            "accessory",
            "--base-vrm", str(base),
            "--images", str(first),
            "--images", str(second),
            *args,
            "--output", str(output_dir),
        ],
    )
    assert result.exit_code != 0
    assert expected in result.output
    assert not output_dir.exists()
