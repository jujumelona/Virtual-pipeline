"""Real CPU integration for the post-reconstruction avatar product path."""

from __future__ import annotations

import pathlib

import numpy as np


def _write_dense_avatar_seed(path: pathlib.Path) -> None:
    import trimesh

    mesh = trimesh.creation.icosphere(subdivisions=4, radius=1.0)
    mesh.apply_scale([0.55, 1.0, 0.48])
    mesh.apply_translation([0.0, 1.0, 0.0])
    mesh.export(path)
    assert path.is_file() and path.stat().st_size > 0


def _write_source_image(path: pathlib.Path) -> None:
    from PIL import Image

    width = height = 256
    yy, xx = np.mgrid[0:height, 0:width]
    rgba = np.empty((height, width, 4), dtype=np.uint8)
    rgba[..., 0] = np.clip(80 + xx // 2, 0, 255)
    rgba[..., 1] = np.clip(70 + yy // 3, 0, 255)
    rgba[..., 2] = np.clip(180 - yy // 4, 0, 255)
    rgba[..., 3] = 255
    Image.fromarray(rgba, mode="RGBA").save(path)


def test_real_cpu_avatar_post_reconstruction_chain(tmp_path):
    from vtuber_pipeline.avatar.expressions import (
        generate_expressions,
        validate_expressions,
    )
    from vtuber_pipeline.avatar.gaze import configure_gaze
    from vtuber_pipeline.avatar.rigging import rig_avatar
    from vtuber_pipeline.avatar.springbone import generate_springbone_config
    from vtuber_pipeline.avatar.texture_transfer import transfer_texture
    from vtuber_pipeline.avatar.validator import validate_vrm
    from vtuber_pipeline.avatar.vrm_export import export_vrm
    from vtuber_pipeline.core.gltf import load_gltf

    mesh_path = tmp_path / "fitted.glb"
    image_path = tmp_path / "source.png"
    _write_dense_avatar_seed(mesh_path)
    _write_source_image(image_path)

    texture = transfer_texture(
        str(image_path),
        str(mesh_path),
        str(tmp_path / "texture"),
        face_bbox=[44.0, 28.0, 212.0, 206.0],
    )
    assert texture["status"] == "complete", texture
    texture_path = pathlib.Path(texture["texture_png"])
    uv_path = pathlib.Path(texture["uv_path"])
    assert texture_path.is_file() and texture_path.stat().st_size > 0
    assert uv_path.is_file() and uv_path.stat().st_size > 0

    source_uv = np.load(uv_path)
    source = load_gltf(mesh_path)
    position_accessor = source.meshes[0].primitives[0].attributes.POSITION
    assert source_uv.shape == (source.accessors[position_accessor].count, 2)

    rigged_path = tmp_path / "rigged.glb"
    rigged = rig_avatar(
        str(mesh_path),
        str(rigged_path),
        texture_path=str(texture_path),
        uv_path=str(uv_path),
    )
    assert pathlib.Path(rigged).is_file()

    rig_gltf = load_gltf(rigged)
    node_names = {node.name for node in (rig_gltf.nodes or []) if node.name}
    for required in (
        "hips", "spine", "chest", "neck", "head",
        "leftEye", "rightEye",
        "leftUpperArm", "leftLowerArm", "leftHand",
        "rightUpperArm", "rightLowerArm", "rightHand",
        "leftUpperLeg", "leftLowerLeg", "leftFoot",
        "rightUpperLeg", "rightLowerLeg", "rightFoot",
        "hairRoot", "hairMid", "hairTip",
    ):
        assert required in node_names
    assert len(rig_gltf.skins or []) == 1
    assert rig_gltf.images and rig_gltf.textures and rig_gltf.materials

    generated = generate_expressions(rigged)
    assert generated["status"] != "error", generated
    expressions = generated["expressions"]
    expression_validation = validate_expressions(
        expressions,
        str(tmp_path / "expressions"),
    )
    assert expression_validation["pass"] is True, expression_validation

    gaze = configure_gaze(rigged, str(tmp_path / "gaze"))
    assert gaze["status"] == "complete", gaze
    assert gaze["config"]["type"] == "bone"
    assert gaze["config"]["yaw_limit_deg"] == 30.0
    assert gaze["config"]["pitch_limit_deg"] == 20.0

    spring = generate_springbone_config(
        rigged,
        str(tmp_path / "spring"),
    )
    assert spring["status"] == "complete", spring
    assert spring["joint_count"] >= 3
    assert any(item["name"] == "hair" for item in spring["springs"])

    export = export_vrm(
        rig_path=rigged,
        output_dir=str(tmp_path / "vrm"),
        expressions=expressions,
        commercial_usage="personalProfit",
        springbone_config=spring,
        gaze_config=gaze["config"],
    )
    assert export["status"] == "complete", export
    vrm_path = pathlib.Path(export["vrm_path"])
    assert vrm_path.is_file() and vrm_path.stat().st_size > 0

    vrm = load_gltf(vrm_path)
    assert "VRMC_vrm" in (vrm.extensions or {})
    assert "VRMC_springBone" in (vrm.extensions or {})
    vrm_ext = vrm.extensions["VRMC_vrm"]
    assert vrm_ext["meta"]["commercialUsage"] == "personalProfit"
    assert vrm_ext["lookAt"]["rangeMapHorizontalInner"]["outputScale"] == 30.0
    assert vrm_ext["lookAt"]["rangeMapVerticalUp"]["outputScale"] == 20.0

    validation = validate_vrm(
        str(vrm_path),
        str(tmp_path / "validation"),
        product_contract=True,
    )
    failed_checks = {
        name: check
        for name, check in validation.get("checks", {}).items()
        if not check.get("valid", False)
    }
    assert validation["status"] == "complete", failed_checks
    assert validation["passed"] is True, failed_checks
