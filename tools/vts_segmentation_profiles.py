"""Canonical shared FACE + mode-scoped asset routing contract.

See-through V3 has FIXED upstream tag prompts. These profiles select a safe
consumer route; they do not change pretrained prompts or pretend that one
semantic tag equals a Cubism-ready limb/eye/garment rig part.
"""
from __future__ import annotations

from pathlib import Path
import json

MODES_2D = ("live2d_bust_up", "live2d_upper", "live2d_full",
            "inochi2d_upper", "inochi2d_full")
MODES_3D = ("3d",)
ASSETS = ("face", "body", "hair", "outfit", "accessory", "character")  # body remains a legacy backend key only

# Verified against upstream common/live2d/scrap_model.py VALID_BODY_PARTS_V3.
SEE_THROUGH_V3_TAGS = (
    "front hair", "back hair", "headwear", "face", "irides",
    "eyebrow", "eyewhite", "eyelash", "eyewear", "ears", "earwear",
    "nose", "mouth", "neck", "neckwear", "topwear", "handwear",
    "bottomwear", "legwear", "footwear", "tail", "wings", "objects",
)

ASSET_TAGS = {
    "character": (),
    "face": ("face", "irides", "eyebrow", "eyewhite", "eyelash", "ears", "nose", "mouth", "neck"),
    "body": ("face", "irides", "eyebrow", "eyewhite", "eyelash",
             "ears", "nose", "mouth", "neck"),
    "hair": ("front hair", "back hair"),
    "outfit": ("topwear", "neckwear", "handwear", "bottomwear",
               "legwear", "footwear"),
    "accessory": ("headwear", "earwear", "eyewear", "neckwear",
                  "tail", "wings", "objects"),
}

# Additional actual separate RGBA layers required by the artwork use case;
# the V3 tags alone do not prove that these layers exist.
FINE_LAYERS = {
    "character": (),
    "face": ("eye_L_white", "eye_L_iris", "eye_L_upper_lash", "eye_R_white", "eye_R_iris", "eye_R_upper_lash", "brow_L", "brow_R", "mouth_closed", "mouth_open", "face_without_eyes", "ear_L", "ear_R", "neck_extended"),
    "body": ("eye_L_white", "eye_L_iris", "eye_L_upper_lash",
             "eye_R_white", "eye_R_iris", "eye_R_upper_lash",
             "brow_L", "brow_R", "mouth_closed", "mouth_open",
             "face_without_eyes", "neck_extended", "torso",
             "upper_arm_L", "upper_arm_R", "forearm_L", "forearm_R",
             "hand_L", "hand_R"),
    "hair": ("front_bangs", "side_lock_L", "side_lock_R",
             "back_hair", "hidden_hair_roots"),
    "outfit": ("front_panel", "back_panel", "sleeve_L", "sleeve_R",
               "inner_seams", "joint_overlap"),
    "accessory": ("requested_object_only", "attachment_anchor",
                  "hidden_attachment_surface"),
}
FULL_BODY_EXTRA = {
    "character": (),
    "face": (),
    "body": ("pelvis", "thigh_L", "thigh_R", "shin_L", "shin_R",
             "foot_L", "foot_R"),
    "hair": (),
    "outfit": ("lower_garment_or_explicitly_absent",),
    "accessory": (),
}

# This is not a claim that V3 can split individual fingers or rig keyforms.
NOT_NATIVE_V3 = {
    "character": (),
    "face": ("independent_eye_components", "hidden_face_paint", "jaw_neck_overlap", "mouth_inner"),
    "body": ("separate_left_right_eye_layers", "upper_arm",
             "forearm", "bare_hand", "fingers", "eyelids",
             "inner_mouth", "torso_underpaint", "joint_overlaps"),
    "hair": ("individual_hair_strands", "side_locks",
             "hidden_hair_roots", "hair_motion_groups"),
    "outfit": ("individual_sleeves", "front_back_panels",
               "lining", "inner_seams", "rig_joint_overlaps"),
    "accessory": ("individual_moving_components",
                  "attachment_anchor", "occluded_object_back"),
}

MODE_SPECS = {
    "face": ("face", "head", False),
    "live2d_bust_up": ("live2d", "bust_up", False),
    "live2d_upper": ("live2d", "upper", False),
    "live2d_full": ("live2d", "full", True),
    "inochi2d_upper": ("inochi2d", "upper", False),
    "inochi2d_full": ("inochi2d", "full", True),
    "3d": ("vrm", "full", True),
}

def get_segmentation_profile(mode: str, asset: str) -> dict:
    """Return routing for one shared FACE or one of 18 framed assets."""
    if (mode == "face") != (asset == "face"):
        raise ValueError("FACE_NEVER_REQUIRES_FRAMING")
    if mode == "3d" and asset not in ("character","accessory"):
        raise ValueError("3D_REQUIRES_FULL_2D_CHARACTER_OR_ACCESSORY")
    if mode not in ("face","3d") and asset == "character":
        raise ValueError("2D_CHARACTER_ASSET_NOT_SEPARATELY_CREATED")
    if mode not in MODE_SPECS or asset not in ASSETS:
        raise ValueError("UNKNOWN_24_ASSET_PROFILE: " + str((mode, asset)))
    engine, frame, is_full = MODE_SPECS[mode]
    if mode == "3d":
        if asset == "character":
            route = "3d_multiview_complete_2d_character_to_vrm"
        elif asset == "face":
            route = "3d_face_reference_only_no_native_vrm"
        elif asset == "body":
            route = "3d_multiview_body_mesh"
        elif asset == "accessory":
            route = "3d_multiview_accessory_existing_vrm"
        else:
            route = "unsupported_3d_detached_asset"
        return {
            "mode": mode, "asset": asset, "engine": engine, "frame": frame,
            "route": route, "see_through": "FORBIDDEN_3D",
            "v3_candidate_tags": [], "followup_rgba_layers": [],
            "limitations": [
                "3D needs geometry/material/skin/VRM; a PSD is not a mesh.",
                "Individual 3D hair/outfit creation is not implemented."
                if route.startswith("unsupported_") else
                "Reference images are not a validated mesh or animation."],
        }
    # A detached source-only hair/outfit/accessory PNG is not a full
    # person. V3's compulsory head crop can be empty on these inputs;
    # route to genuine alpha/foreground acquisition and require more
    # work for secondary moving layers. Do not label it complete.
    is_body = asset == "body"
    route = ("face_source_needs_eye_mouth_segmentation" if asset == "face"
             else "v3_full_character_then_fine_anatomy" if is_body
             else "detached_alpha_then_asset_specific_refinement")
    return {
        "mode": mode, "asset": asset, "engine": engine, "frame": frame,
        "route": route,
        "see_through": ("FACE_ONLY_HEAD_SEGMENTATION_NOT_YET_VERIFIED" if asset == "face"
                        else "V3_TWO_PASS_BODY_HEAD" if is_body
                        else "SKIP_V3_ON_DETACHED_MASTER"),
        "v3_candidate_tags": list(ASSET_TAGS[asset]),
        "followup_rgba_layers": list(FINE_LAYERS[asset] +
            (FULL_BODY_EXTRA[asset] if is_full else ())),
        "not_guaranteed_by_v3": list(NOT_NATIVE_V3[asset]),
        "forbid_other_asset_pixels": asset != "body",
        "requires_reference_body": asset not in ("body", "face"),
        "needs_human_visual_qc": True,
        "source_master_has_no_rigged_parts": True,
        "status_before_real_segmentation": "ARTWORK_ONLY_UNVERIFIED",
    }

def select_source_segmentation(mode: str, asset: str) -> str:
    profile = get_segmentation_profile(mode, asset)
    if profile["route"].startswith("unsupported_"):
        raise NotImplementedError(
            "3D_DETACHED_HAIR_OUTFIT_UNSUPPORTED: "
            + str((mode, asset)) + "; no PSD-to-VRM fake conversion"
        )
    return profile["route"]

def write_segmentation_plan(mode: str, asset: str, output: Path) -> dict:
    profile = get_segmentation_profile(mode, asset)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(profile, ensure_ascii=False, indent=2),
                      encoding="utf-8")
    return profile

def infer_live2d_mode(scope: str) -> str:
    if scope == "upper":
        return "live2d_upper"
    if scope == "full":
        return "live2d_full"
    raise ValueError("INVALID_2D_SCOPE")
