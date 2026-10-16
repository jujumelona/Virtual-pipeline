"""Static tests for all 24 asset-specific See-through selection routes."""
import pytest

from tools.vts_segmentation_profiles import (
    ASSETS, MODE_SPECS, SEE_THROUGH_V3_TAGS,
    get_segmentation_profile, select_source_segmentation,
    write_segmentation_plan,
)

def test_exactly_24_unique_routes():
    cases = [(mode, asset) for mode in MODE_SPECS for asset in ASSETS]
    assert len(cases) == len(set(cases)) == 24
    plans = [get_segmentation_profile(m, a) for m, a in cases]
    assert all(p["mode"] == m and p["asset"] == a
               for p, (m, a) in zip(plans, cases))
    assert len(SEE_THROUGH_V3_TAGS) == 23
    for p in plans:
        assert set(p["v3_candidate_tags"]) <= set(SEE_THROUGH_V3_TAGS)

@pytest.mark.parametrize("mode", (
    "live2d_bust_up", "live2d_upper", "live2d_full",
    "inochi2d_upper", "inochi2d_full"))
def test_body_uses_full_person_see_through_only(mode):
    p = get_segmentation_profile(mode, "body")
    assert p["see_through"] == "V3_TWO_PASS_BODY_HEAD"
    assert "eyewhite" in p["v3_candidate_tags"]
    assert "irides" in p["v3_candidate_tags"]
    assert "eyelash" in p["v3_candidate_tags"]
    assert "upper_arm" in p["not_guaranteed_by_v3"]
    assert "handwear" not in p["v3_candidate_tags"]
    assert "fingers" in p["not_guaranteed_by_v3"]
    if mode.endswith("full"):
        assert "foot_L" in p["followup_rgba_layers"]
    else:
        assert "foot_L" not in p["followup_rgba_layers"]

@pytest.mark.parametrize("mode", (
    "live2d_bust_up", "live2d_upper", "live2d_full",
    "inochi2d_upper", "inochi2d_full"))
@pytest.mark.parametrize("asset", ("hair", "outfit", "accessory"))
def test_detached_asset_skips_full_person_head_crop(mode, asset):
    p = get_segmentation_profile(mode, asset)
    assert p["see_through"] == "SKIP_V3_ON_DETACHED_MASTER"
    assert p["requires_reference_body"] is True
    assert select_source_segmentation(mode, asset).startswith("detached_alpha")
    if asset == "hair":
        assert p["v3_candidate_tags"] == ["front hair", "back hair"]
    if asset == "accessory":
        assert "objects" in p["v3_candidate_tags"]

@pytest.mark.parametrize("asset", ("hair", "outfit"))
def test_3d_detached_is_explicitly_unsupported(asset):
    p = get_segmentation_profile("3d", asset)
    assert p["see_through"] == "FORBIDDEN_3D"
    with pytest.raises(NotImplementedError, match="3D_DETACHED"):
        select_source_segmentation("3d", asset)

@pytest.mark.parametrize("asset", ("body", "accessory"))
def test_3d_supported_routes_still_do_not_use_see_through(asset):
    p = get_segmentation_profile("3d", asset)
    assert "3d_" in p["route"]
    assert p["v3_candidate_tags"] == []
    assert select_source_segmentation("3d", asset) == p["route"]

def test_invalid_profiles_and_json_output(tmp_path):
    with pytest.raises(ValueError, match="UNKNOWN_24"):
        get_segmentation_profile("3d", "unknown")
    with pytest.raises(ValueError, match="UNKNOWN_24"):
        get_segmentation_profile("inexistent", "body")
    p = write_segmentation_plan("live2d_bust_up", "body",
                                tmp_path / "plan.json")
    import json
    assert json.loads((tmp_path / "plan.json").read_text(encoding="utf-8")) == p
