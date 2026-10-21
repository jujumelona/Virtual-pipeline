"""Optional real-MOC3 expression frames cover more than mouth open alone."""
from tools.vts_native_moc_pose_worker import POSES, OPTIONAL_MOUTH_FORM_POSES


def test_advanced_combinations_are_real_parameter_inputs():
    assert len(OPTIONAL_MOUTH_FORM_POSES) >= 6
    known = {name for name, _ in POSES}
    optional = {name for name, _ in OPTIONAL_MOUTH_FORM_POSES}
    assert not (known & optional)
    assert {"smile_talking", "smile_yaw_left",
            "smile_yaw_right", "smile_blink"} <= optional
    for name, params in OPTIONAL_MOUTH_FORM_POSES:
        assert "ParamMouthForm" in params
        assert all(isinstance(x, (int, float)) for x in params.values())
    assert any(params.get("ParamMouthForm") == -1
               for _, params in OPTIONAL_MOUTH_FORM_POSES)


def test_only_actual_optional_parameter_controls_may_trigger_extra_poses():
    from pathlib import Path
    source = Path(__file__).resolve().parents[1] / "tools/vts_native_moc_pose_worker.py"
    text = source.read_text(encoding="utf-8")
    assert 'if "ParamMouthForm" in available else ()' in text
    assert 'defaults["ParamMouthForm"] = 0' in text
    assert '"complex_expression_visual_quality_verified": False' in text
