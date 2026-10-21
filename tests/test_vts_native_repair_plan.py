"""Repair actions are explicit, data-driven, never claims of completed edits."""
from tools.vts_native_repair_plan import quality_repair_plan


def test_failure_family_routes_to_correct_tools():
    report = quality_repair_plan({
        "native_pose_rendered": True,
        "native_pose_geometry_passed": False,
        "native_mouth_interpolation_passed": False,
        "pose_activity_passed": False,
        "parameter_isolation": {"passed": False},
    })
    actions = {x["tool"] for x in report["actions"]}
    assert {"vts_modern_mesh_refiner", "vts_reference_keyform_author",
            "mouth_art_and_keyforms"} <= actions
    assert not any(x["executed"] for x in report["actions"])
    assert not report["artistic_quality_verified"]


def test_source_master_mismatch_cannot_be_fixed_by_just_head_strength():
    report = quality_repair_plan({
        "native_pose_rendered": True, "native_pose_geometry_passed": True,
        "native_mouth_interpolation_passed": True, "pose_activity_passed": True,
        "parameter_isolation": {"passed": True},
    }, source_art={"neutral_exact_same_as_master": False})
    assert report["actions"][0]["tool"] == "source_art_regenerate"
    assert all("head_strength" not in str(a) for a in report["actions"])


def test_missing_native_render_is_not_called_good_rig():
    result = quality_repair_plan({})
    assert result["actions"][0]["tool"] == "native_runtime_debug"
    assert not result["actual_vtube_studio_tracking_verified"]


def test_passing_technical_checks_still_require_visual_review():
    result = quality_repair_plan({
        "native_pose_rendered": True, "native_pose_geometry_passed": True,
        "native_mouth_interpolation_passed": True, "pose_activity_passed": True,
        "parameter_isolation": {"passed": True},
    })
    assert result["actions"][0]["tool"] == "human_visual_and_vts_tracking"
