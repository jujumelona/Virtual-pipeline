"""Integration tests for the fail-closed VTuber pipeline."""

import os
import pathlib

import pytest


@pytest.mark.skipif(
    os.environ.get("VTUBER_E2E") != "1",
    reason="Full TripoSR/anime-face-detector E2E requires an explicitly prepared GPU runtime",
)
def test_e2e_pipeline(test_char_image, tmp_path):
    """Run the real image -> VRM path and require a strict complete result."""
    from pygltflib import GLTF2
    from vtuber_pipeline.avatar.build import build_avatar

    output_dir = str(tmp_path / "output")
    result = build_avatar(str(test_char_image), output_dir)

    assert result["status"] == "complete", result
    assert result["stages"]["validator"]["passed"] is True
    assert result["stages"]["reference_reconstruction"]["source"] == "triposr"

    vrm_path = pathlib.Path(result["vrm_path"])
    assert vrm_path.is_file()
    assert vrm_path.stat().st_size > 0

    gltf = GLTF2().load(str(vrm_path))
    assert isinstance(gltf.extensions, dict)
    assert "VRMC_vrm" in gltf.extensions
    assert "VRMC_springBone" in gltf.extensions

    vrm_ext = gltf.extensions["VRMC_vrm"]
    assert vrm_ext["specVersion"] == "1.0"
    assert vrm_ext["meta"]["commercialUsage"] == "corporation"

    required = {
        "hips", "spine", "chest", "neck", "head",
        "leftEye", "rightEye",
        "leftUpperArm", "leftLowerArm", "leftHand",
        "rightUpperArm", "rightLowerArm", "rightHand",
        "leftUpperLeg", "leftLowerLeg", "leftFoot",
        "rightUpperLeg", "rightLowerLeg", "rightFoot",
    }
    bones = vrm_ext["humanoid"]["humanBones"]
    assert required <= set(bones)

    required_expr = {
        "blink", "blinkLeft", "blinkRight",
        "aa", "ih", "ou", "ee", "oh",
        "happy", "angry", "sad", "relaxed", "surprised",
    }
    assert required_expr <= set(vrm_ext["expressions"]["preset"])


def test_vrm_schema_compliance():
    """Test the generated VRMC_vrm metadata/humanoid object shape."""
    from pygltflib import GLTF2, Node
    from vtuber_pipeline.avatar.vrm_builder import create_vrm_extension

    gltf = GLTF2()
    gltf.nodes = [Node(name=name) for name in ("hips", "spine", "chest", "neck", "head")]

    vrm_ext = create_vrm_extension(
        gltf,
        bone_mapping={
            "hips": 0,
            "spine": 1,
            "chest": 2,
            "neck": 3,
            "head": 4,
        },
        commercial_usage="corporation",
    )

    assert vrm_ext["specVersion"] == "1.0"
    assert isinstance(vrm_ext["humanoid"]["humanBones"], dict)
    assert vrm_ext["meta"]["commercialUsage"] == "corporation"
    assert vrm_ext["meta"]["licenseUrl"] == "https://vrm.dev/licenses/1.0/"
    assert vrm_ext["meta"]["name"]
    assert vrm_ext["meta"]["authors"]


def test_commercial_usage_option():
    """All VRM 1.0 commercialUsage enum values remain selectable."""
    from pygltflib import GLTF2
    from vtuber_pipeline.avatar.vrm_builder import create_vrm_extension

    gltf = GLTF2()
    for usage in ("personalNonProfit", "personalProfit", "corporation"):
        vrm_ext = create_vrm_extension(gltf, commercial_usage=usage)
        assert vrm_ext["meta"]["commercialUsage"] == usage


def test_springbone_extension_schema():
    """VRMC_springBone uses current joints schema and omits empty optional arrays."""
    from pygltflib import GLTF2, Node
    from vtuber_pipeline.avatar.vrm_builder import create_springbone_extension

    gltf = GLTF2()
    gltf.nodes = [
        Node(name="hairRoot", children=[1]),
        Node(name="hairMid", children=[2]),
        Node(name="hairTip"),
    ]
    springs = [{
        "name": "hair",
        "joints": [
            {
                "node": "hairRoot",
                "hitRadius": 0.02,
                "stiffness": 0.5,
                "gravityPower": 0.1,
                "gravityDir": [0.0, -1.0, 0.0],
                "dragForce": 0.2,
            },
            {
                "node": "hairMid",
                "hitRadius": 0.02,
                "stiffness": 0.5,
                "gravityPower": 0.1,
                "gravityDir": [0.0, -1.0, 0.0],
                "dragForce": 0.2,
            },
            {
                "node": "hairTip",
                "hitRadius": 0.02,
                "stiffness": 0.5,
                "gravityPower": 0.1,
                "gravityDir": [0.0, -1.0, 0.0],
                "dragForce": 0.2,
            },
        ],
        "colliderGroups": [],
    }]

    ext = create_springbone_extension(gltf, springs=springs)
    assert ext["specVersion"] == "1.0"
    assert "colliders" not in ext
    assert "colliderGroups" not in ext
    assert len(ext["springs"]) == 1
    assert [j["node"] for j in ext["springs"][0]["joints"]] == [0, 1, 2]
    assert "colliderGroups" not in ext["springs"][0]


def test_commercial_profile_reconstruction_failure_is_fail_closed(
    tmp_path,
    monkeypatch,
):
    """Production never substitutes a canonical mesh when TripoSR fails."""
    import vtuber_pipeline.avatar.build as build_module
    import vtuber_pipeline.avatar.input_gate as input_gate_module
    import vtuber_pipeline.avatar.reconstruction as reconstruction_module

    monkeypatch.setattr(
        input_gate_module,
        "validate_input",
        lambda image_path, output_dir: {
            "status": "complete",
            "valid": True,
            "landmarks": [[float(i), float(i)] for i in range(28)],
            "bbox": [10.0, 10.0, 200.0, 200.0],
        },
    )
    monkeypatch.setattr(
        reconstruction_module,
        "reconstruct_avatar",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("synthetic TripoSR failure")
        ),
    )

    image = tmp_path / "input.png"
    image.write_bytes(b"not-used-because-input-gate-is-mocked")

    result = build_module.AvatarPipeline(
        str(tmp_path / "out"),
        config={"profile": "production"},
    ).build(str(image))

    assert result["status"] == "failed"
    stage = result["stages"]["reference_reconstruction"]
    assert stage["status"] == "error"
    assert stage["source"] == "triposr"
    assert "synthetic TripoSR failure" in stage["error"]
    assert "fallback" not in stage


@pytest.fixture
def test_char_image():
    """Path to the explicit GPU E2E fixture."""
    fixture_path = pathlib.Path(__file__).parent.parent / "fixtures" / "test_char.png"
    assert fixture_path.is_file(), f"E2E fixture is missing: {fixture_path}"
    assert fixture_path.stat().st_size > 0, f"E2E fixture is empty: {fixture_path}"
    return fixture_path
