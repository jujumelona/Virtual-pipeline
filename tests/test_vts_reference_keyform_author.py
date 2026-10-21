"""Reference-keyform authoring must use real paired art and native pose evidence."""
from pathlib import Path

import pytest
from PIL import Image
from tools.vts_reference_keyform_author import (
    compile_native_reference_edits, apply_reference_keyforms,
)


def _art(root):
    for folder in ("reference_views", "native_poses"):
        target = root / folder
        target.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (320, 320), "white").save(
            target / "head_three_quarter_R.png")


def _manifest():
    rendered = {
        "face_contour": [140, 150],
        "nose_tip": [164, 155],
        "jaw": [154, 180],
        "eye_left": [135, 120],
    }
    desired = {name: [xy[0]+6, xy[1]+4] for name, xy in rendered.items()}
    return {
        "canvas": [320, 320],
        "warp_bindings": {
            "face_contour": "warp:faceContour",
            "nose_tip": "warp:nose",
            "jaw": "warp:jaw",
            "eye_left": "warp:leftEye",
        },
        "poses": [{
            "view": "head_three_quarter_R", "angle_x": 30,
            "observed": rendered, "desired": desired,
        }],
    }


def test_reference_pairs_produce_real_parameter_key_edits(tmp_path):
    _art(tmp_path)
    plan = compile_native_reference_edits(_manifest(), tmp_path)
    assert len(plan["changes"]) == 4
    assert all(change["key"] == {"ParamAngleX": 30}
               for change in plan["changes"])
    assert all(change["operations"][0]["type"] == "translate"
               for change in plan["changes"])
    assert plan["reference_angles_used_as_rig_keyforms"] is False
    assert plan["native_execution_required"] is True


def test_missing_real_pose_images_are_not_accepted(tmp_path):
    with pytest.raises(FileNotFoundError):
        compile_native_reference_edits(_manifest(), tmp_path)


def test_90_degree_profile_cannot_be_faked_as_frontal_warp(tmp_path):
    _art(tmp_path)
    manifest = _manifest()
    manifest["poses"][0]["view"] = "head_profile_R"
    manifest["poses"][0]["angle_x"] = 90
    with pytest.raises(ValueError, match="90-degree"):
        compile_native_reference_edits(manifest, tmp_path)


def test_reference_cannot_erase_wrong_warp_mapping_or_silhouette(tmp_path):
    _art(tmp_path)
    manifest = _manifest()
    manifest["warp_bindings"]["nose_tip"] = "warp:jaw"
    with pytest.raises(ValueError, match="independent warp"):
        compile_native_reference_edits(manifest, tmp_path)
    manifest = _manifest()
    del manifest["poses"][0]["observed"]["jaw"]
    with pytest.raises(ValueError, match="Missing/bad correspondences"):
        compile_native_reference_edits(manifest, tmp_path)


def test_excessive_shift_rejected(tmp_path):
    _art(tmp_path)
    manifest = _manifest()
    manifest["poses"][0]["desired"]["nose_tip"] = [290, 290]
    with pytest.raises(ValueError, match="12%"):
        compile_native_reference_edits(manifest, tmp_path)


def test_compiler_does_not_claim_native_execution(tmp_path):
    _art(tmp_path)
    plan = compile_native_reference_edits(_manifest(), tmp_path)
    assert "exported_model3" not in plan
    assert plan["missing_full_profile"]
