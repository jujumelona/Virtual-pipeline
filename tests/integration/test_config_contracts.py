"""Fail-closed configuration contract tests."""

from __future__ import annotations

from vtuber_pipeline.accessory.build import AccessoryPipeline
from vtuber_pipeline.avatar.build import AvatarPipeline
from vtuber_pipeline.avatar.template_fitting import fit_template


def _avatar(tmp_path, config):
    return AvatarPipeline(
        str(tmp_path / "avatar"),
        config=config,
    ).build(str(tmp_path / "input.png"))


def _accessory(tmp_path, config, **kwargs):
    return AccessoryPipeline(
        str(tmp_path / "accessory"),
        config=config,
    ).build(
        base_vrm=str(tmp_path / "base.vrm"),
        accessory_glb=str(tmp_path / "item.glb"),
        **kwargs,
    )


def test_avatar_constructor_config_type_is_fail_closed(tmp_path):
    result = _avatar(tmp_path, "")
    assert result["status"] == "failed"
    assert result["failed_stages"] == ["orchestrator"]
    assert "config must be an object" in result["failed_reason"]


def test_avatar_build_override_type_is_fail_closed(tmp_path):
    pipeline = AvatarPipeline(str(tmp_path / "avatar"))
    result = pipeline.build(str(tmp_path / "input.png"), config="")
    assert result["status"] == "failed"
    assert result["failed_stages"] == ["orchestrator"]
    assert "override" in result["failed_reason"]


def test_avatar_rejects_unknown_and_invalid_options_before_models(tmp_path):
    cases = [
        ({"profiel": "commercial"}, "Unknown avatar config"),
        ({"profile": "prod"}, "Unsupported profile"),
        ({"commercial_usage": "yes"}, "commercial_usage"),
        (
            {"reconstruction": {"remove_bg": True}},
            "Unknown reconstruction config",
        ),
        (
            {"reconstruction": {"model_save_format": "fbx"}},
            "model_save_format",
        ),
        (
            {"reconstruction": {"remove_background": "false"}},
            "remove_background",
        ),
        ({"fitting": "defaults"}, "fitting config"),
    ]
    for config, message in cases:
        result = _avatar(tmp_path, config)
        assert result["status"] == "failed", (config, result)
        assert result["failed_stages"] == ["orchestrator"]
        assert message in result["failed_reason"]


def test_fitting_rejects_unknown_invalid_and_nonfinite_weights(tmp_path):
    cases = [
        ({"typo": {}}, "Unknown fitting config"),
        (
            {"fitting_objective": {"lambda_surfac": 0.5}},
            "Unknown fitting_objective",
        ),
        (
            {"fitting_objective": {"lambda_surface": -0.1}},
            "finite non-negative",
        ),
        (
            {"fitting_objective": {"lambda_surface": float("nan")}},
            "finite non-negative",
        ),
        (
            {"fitting_objective": {"lambda_surface": True}},
            "finite non-negative",
        ),
    ]

    for index, (config, message) in enumerate(cases):
        result = fit_template(
            template_path=str(tmp_path / "missing.glb"),
            landmarks_2d=[[0.0, 0.0] for _ in range(28)],
            output_dir=str(tmp_path / f"fit-{index}"),
            config=config,
            reference_mesh_path=str(tmp_path / "missing-reference.glb"),
        )
        assert result["status"] == "error", (config, result)
        assert message in result["error"]


def test_accessory_constructor_config_type_is_fail_closed(tmp_path):
    result = _accessory(tmp_path, "")
    assert result["status"] == "failed"
    assert result["failed_stages"] == ["orchestrator"]
    assert "config must be an object" in result["failed_reason"]


def test_accessory_rejects_unknown_and_invalid_options_before_geometry(tmp_path):
    cases = [
        ({"ancor_name": "HEAD_TOP"}, "Unknown accessory config"),
        ({"anchor_name": "NOPE"}, "anchor_name"),
        ({"bake": "true"}, "bake must be boolean"),
        ({"physics": True}, "physics config"),
        (
            {"physics": {"enabled": "yes"}},
            "physics.enabled",
        ),
        (
            {"physics": {"enabled": False, "typo": 1}},
            "Unknown physics config",
        ),
        (
            {"collision": "defaults"},
            "collision config",
        ),
        (
            {"collision": {"clearance": "0.003"}},
            "collision.clearance",
        ),
        (
            {"collision": {"clearance": 0.0}},
            "collision.clearance",
        ),
        (
            {"collision": {"clearance": 0.003, "typo": 1}},
            "Unknown collision config",
        ),
        (
            {
                "anchor_name": "HEAD_TOP",
                "custom_anchor": {
                    "parent_bone": "head",
                    "offset": [0, 0, 0],
                    "target_size": 0.1,
                },
            },
            "custom_anchor is only valid",
        ),
    ]

    for config, message in cases:
        result = _accessory(tmp_path, config)
        assert result["status"] == "failed", (config, result)
        assert result["failed_stages"] == ["orchestrator"]
        assert message in result["failed_reason"]


def test_accessory_output_dir_override_cannot_escape_bound_pipeline(tmp_path):
    pipeline = AccessoryPipeline(str(tmp_path / "bound"))
    result = pipeline.build(
        base_vrm=str(tmp_path / "base.vrm"),
        accessory_glb=str(tmp_path / "item.glb"),
        output_dir=str(tmp_path / "other"),
    )
    assert result["status"] == "failed"
    assert result["failed_stages"] == ["orchestrator"]
    assert "bound to one output directory" in result["failed_reason"]
