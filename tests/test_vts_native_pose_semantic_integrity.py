"""Regression: real native-pose topology and PSD2Live body part identities.

Do not mistake a valid alpha/PSD or changed pixels for a usable articulated rig.
"""
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from tools.vts_native_pose_integrity import POSES, inspect_native_pose_frames
from tools.vts_psd2live_names import normalize_layer_names
from tools.vts_production import _semantic_family
from tools.vts_multiview_runtime import check_psd2live_body_semantics


def connected_body():
    im = Image.new("RGB", (320, 320), "black")
    d = ImageDraw.Draw(im)
    d.ellipse((110, 20, 210, 120), fill=(240, 195, 167))
    d.rectangle((153, 100, 166, 158), fill=(240, 195, 167))
    d.rectangle((85, 150, 235, 259), fill=(240, 195, 167))
    d.rectangle((55, 165, 95, 286), fill=(240, 195, 167))
    d.rectangle((225, 165, 265, 286), fill=(240, 195, 167))
    return im


def test_actual_rotating_body_cannot_lose_head_and_arms(tmp_path: Path):
    original = connected_body()
    for pose in POSES:
        frame = original.copy()
        if pose == "pitch_up":
            d = ImageDraw.Draw(frame)
            d.rectangle((120, 100, 205, 162), fill="black")
        if pose == "roll_right":
            d = ImageDraw.Draw(frame)
            d.rectangle((1, 220, 7, 240), fill=(240, 195, 167))
        frame.save(tmp_path / (pose + ".png"))
    result = inspect_native_pose_frames(tmp_path)
    assert result["geometry_passed"] is False
    found = {(x["pose"], x["code"]) for x in result["failures"]}
    assert ("pitch_up", "NATIVE_BODY_LIMBS_OR_HEAD_DETACHED") in found
    assert ("roll_right", "NATIVE_BODY_ROTATION_CLIPPED_AT_CANVAS") in found


def test_connected_complete_body_is_not_falsely_rejected(tmp_path: Path):
    for pose in POSES:
        connected_body().save(tmp_path / (pose + ".png"))
    assert inspect_native_pose_frames(tmp_path)["geometry_passed"] is True


@pytest.mark.parametrize("original,expected", [
    ("upper_arm_L", "arm.left.upper"),
    ("upper_arm_R", "arm.right.upper"),
    ("forearm_L", "arm.left.forearm"),
    ("forearm_R", "arm.right.forearm"),
    ("shoulder_L", "arm.left.shoulder"),
    ("shoulder_R", "arm.right.shoulder"),
    ("scalp", "face.scalp"),
    ("jaw", "face.jaw"),
    ("skin_base", "body.skin"),
])
def test_original_body_names_survive_normalization(original, expected):
    assert _semantic_family(original) == expected


def test_eye_whites_remain_separate_from_iris():
    picture = Image.new("RGBA", (300, 300), (0, 0, 0, 0))
    names = ("eye.left.whites.012", "eye.right.whites.013",
             "eye.left.iris.010", "eye.right.iris.011")
    norm, report = normalize_layer_names([
        {"name": name, "image": picture} for name in names
    ])
    assert norm[0]["name"].startswith("eyewhite_")
    assert norm[1]["name"].startswith("eyewhite_")
    assert norm[2]["name"].startswith("irides_")
    assert norm[3]["name"].startswith("irides_")
    assert report["records"][0]["side"] == "l"
    assert report["records"][1]["side"] == "r"


def test_undirected_forearms_recover_character_sides_from_canvas():
    left = Image.new("RGBA", (512, 512))
    right = left.copy()
    ImageDraw.Draw(left).rectangle((60, 130, 110, 230), fill=(200, 180, 140, 255))
    ImageDraw.Draw(right).rectangle((400, 130, 452, 230), fill=(200, 180, 140, 255))
    norm, report = normalize_layer_names([
        {"name": "arm.004", "image": right},
        {"name": "arm.005", "image": left},
    ])
    assert norm[0]["name"].endswith("-l")
    assert norm[1]["name"].endswith("-r")
    assert report["records"][0]["evidence"].endswith("character_left")


def test_semantic_rig_bindings_fail_on_old_four_irises():
    old = {"records": [
        {"semantic_tag": "irides", "side": side} for side in ("l", "r")
    ] * 2 + [
        {"semantic_tag": "eyelash", "side": side} for side in ("l", "r")
    ] + [
        {"semantic_tag": "handwear", "side": side} for side in ("l", "r")
    ]}
    with pytest.raises(RuntimeError, match="NATIVE_RIG_LAYER_ROLE_LOST"):
        check_psd2live_body_semantics(old)


def test_semantic_bindings_pass_after_whites_and_arm_fix():
    fixed = {"records": [
        {"semantic_tag": kind, "side": side}
        for kind in ("irides", "eyelash", "eyewhite", "handwear")
        for side in ("l", "r")
    ]}
    assert check_psd2live_body_semantics(fixed)["passed"] is True
