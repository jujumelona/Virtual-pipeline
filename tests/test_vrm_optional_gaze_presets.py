"""VRM 1.0 bone-driven look presets may have no morph bind; core faces may not."""
from vtuber_pipeline.avatar.validator import VRMValidator, REQUIRED_EXPRESSIONS


def _validator(extras):
    obj = VRMValidator("/not/a/file.vrm", product_contract=True)
    presets = {n: {"morphTargetBinds": [{"verified": True}]}
               for n in REQUIRED_EXPRESSIONS}
    presets.update(extras)
    obj.parse_vrm = lambda: {"expressions": {"preset": presets}}
    obj._validate_morph_bind = lambda b: b.get("verified") is True
    return obj


def test_optional_bone_driven_gaze_and_neutral_preset_are_valid():
    v = _validator({n: {} for n in (
        "lookLeft", "lookRight", "lookUp", "lookDown", "neutral")})
    report = v.validate_expressions()
    assert report["valid"] is True
    assert report["invalid_binds"] == []


def test_required_morph_expression_still_cannot_be_empty():
    v = _validator({"blink": {}})
    report = v.validate_expressions()
    assert not report["valid"] and "blink" in report["invalid_binds"]


def test_optional_malformed_nonempty_bind_still_rejected():
    v = _validator({"lookLeft": {"morphTargetBinds": [{}]}})
    report = v.validate_expressions()
    assert not report["valid"] and "lookLeft" in report["invalid_binds"]
