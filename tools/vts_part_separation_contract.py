"""Live2D/PSD2Live cutting inventory for an already generated illustration.

An observed semantic name proves neither clean RGBA extraction nor hidden
underpaint. Report those facts separately; never turn an unsplit 'eyes' mask
into verified whites, irises or lashes.

Sources:
- https://docs.live2d.com/en/cubism-editor-manual/divide-the-material/
- https://docs.live2d.com/en/cubism-editor-tutorials/psd/
- https://github.com/tsunehimatoi/psd2live/blob/master/docs/en/spec/PSD_LAYER_SPEC.md
"""
from __future__ import annotations

import re
from typing import Any


BODY_REQUIRED = (
    "face", "neck", "torso", "nose", "mouth_open",
    "ear_left", "ear_right",
    "eye_left_white", "eye_left_iris", "eye_left_upper_lash", "brow_left",
    "eye_right_white", "eye_right_iris", "eye_right_upper_lash", "brow_right",
    "upper_arm_left", "forearm_left", "hand_left",
    "upper_arm_right", "forearm_right", "hand_right",
)
FULL_EXTRA = (
    "pelvis", "thigh_left", "shin_left", "foot_left",
    "thigh_right", "shin_right", "foot_right",
)
# These are role descriptions, NOT magic fixed layer counts or guaranteed
# See-through/SAM19 segmentation classes.
OPTIONAL = {
    "body": ("eye_left_lower_lash", "eye_right_lower_lash",
             "eye_left_lid", "eye_right_lid", "eye_left_pupil",
             "eye_right_pupil", "eye_left_highlight",
             "eye_right_highlight", "mouth_upper_lip", "mouth_lower_lip",
             "tongue", "upper_teeth", "lower_teeth", "cheek",
             "modesty_cover", "shoulder_left", "shoulder_right"),
    "hair": ("hair_front", "hair_back", "hair_side_left",
             "hair_side_right", "hair_loose_strands", "hair_shadow"),
    "outfit": ("outfit_front", "outfit_back", "sleeve_left",
               "sleeve_right", "collar", "hem", "ribbon", "skirt"),
    "accessory": ("attachment_anchor", "accessory_front", "accessory_back",
                  "separate_moving_pieces"),
}
REQUIREMENTS_BY_ASSET = {
    "body": BODY_REQUIRED,
    "hair": ("hair_front_or_back",),
    "outfit": ("outfit_base",),
    "accessory": ("accessory_item",),
}


def classify_name(name: str) -> set[str]:
    """Conservative observable-label classifier, never image verification."""
    words = [x for x in re.split(r"[^a-z0-9]+", str(name).casefold()) if x]
    t = set(words)
    out: set[str] = set()
    side = ("left" if t & {"left", "l"} and not t & {"right", "r"} else
            "right" if t & {"right", "r"} and not t & {"left", "l"} else None)
    joined = "".join(words)
    if t & {"face", "head"} and not t & {"detail", "blush", "scalp", "jaw"}:
        out.add("face")
    if "neck" in t and not t & {"neckwear", "necklace"}:
        out.add("neck")
    if t & {"body", "torso"}:
        out.add("torso")
    if "nose" in t:
        out.add("nose")
    if "pelvis" in t:
        out.add("pelvis")
    if t & {"mouth", "lip"} or "mouth" in joined:
        if t & {"open", "inside", "inner", "interior"} or "mouthopen" in joined:
            out.add("mouth_open")
        if t & {"upper", "top"}:
            out.add("mouth_upper_lip")
        if t & {"lower", "bottom"}:
            out.add("mouth_lower_lip")
    if side:
        if t & {"eye", "eyes", "eyewhite", "irides", "eyelash"}:
            if t & {"white", "whites", "sclera", "eyewhite"}:
                out.add("eye_" + side + "_white")
            if t & {"iris", "irides"}:
                out.add("eye_" + side + "_iris")
            if t & {"lash", "lashes", "eyelash"} and not t & {"lower", "bottom"}:
                out.add("eye_" + side + "_upper_lash")
            if t & {"lid", "eyelid"}:
                out.add("eye_" + side + "_lid")
            if "pupil" in t:
                out.add("eye_" + side + "_pupil")
            if t & {"highlight", "glint"}:
                out.add("eye_" + side + "_highlight")
        if t & {"ear", "ears"} and not t & {"earwear", "earring"}:
            out.add("ear_" + side)
        if t & {"brow", "eyebrow"}:
            out.add("brow_" + side)
        if "hand" in t:
            out.add("hand_" + side)
        if "forearm" in t or ("arm" in t and t & {"fore", "lower"}):
            out.add("forearm_" + side)
        if ("arm" in t and "upper" in t) or ("upperarm" in t):
            out.add("upper_arm_" + side)
        if "shoulder" in t:
            out.add("shoulder_" + side)
        if "thigh" in t:
            out.add("thigh_" + side)
        if t & {"shin", "calf"}:
            out.add("shin_" + side)
        if t & {"foot", "footwear"}:
            out.add("foot_" + side)
        if t & {"sleeve"}:
            out.add("sleeve_" + side)
        if "hair" in t and "side" in t:
            out.add("hair_side_" + side)
    if "hair" in t:
        if t & {"front", "bang", "bangs"}: out.add("hair_front")
        if t & {"back", "rear"}: out.add("hair_back")
    if t & {"outfit", "cloth", "garment", "topwear", "shirt", "dress"}:
        out.add("outfit_base")
        if "front" in t: out.add("outfit_front")
        if "back" in t: out.add("outfit_back")
    if t & {"accessory", "ornament", "headwear", "earwear", "objects", "prop"}:
        out.add("accessory_item")
    return out


def audit_part_separation(names: list[str], *, asset: str, scope: str) -> dict[str, Any]:
    if asset not in REQUIREMENTS_BY_ASSET or scope not in {"upper", "full"}:
        raise ValueError("Invalid part audit asset/scope")
    observed = sorted({kind for name in names for kind in classify_name(name)})
    set_observed = set(observed)
    required = list(REQUIREMENTS_BY_ASSET[asset])
    if asset == "body" and scope == "full":
        required.extend(FULL_EXTRA)
    missing = [
        name for name in required
        if name not in set_observed and
        not (name == "hair_front_or_back" and set_observed & {"hair_front", "hair_back"})
    ]
    ambiguous = [name for name in names if
                 re.search(r"(?:^|[.\\_ -])eyes?(?:[.\\_ -]|$)",
                           name.casefold())
                 and not classify_name(name) & {
                     "eye_left_white", "eye_right_white",
                     "eye_left_iris", "eye_right_iris",
                     "eye_left_upper_lash", "eye_right_upper_lash"
                 }]
    return {
        "schema": "vtuber/part-separation-audit-v1",
        "asset": asset, "scope": scope, "input_layer_names": list(names),
        "required_semantic_roles": required, "observed_named_roles": observed,
        "missing_or_unproven_roles": missing,
        "ambiguous_whole_eye_layers": ambiguous,
        "named_role_coverage": len(required) - len(missing),
        "named_role_total": len(required),
        "named_role_requirements_met": not missing,
        "geometry_or_underpaint_verified": False,
        "native_animation_verified": False,
        "warning": "Layer names are not proof of separate alpha content. "
                   "SAM19 'eyes' is a coarse region, not iris/white/lash. "
                   "Missing roles require targeted re-segmentation or newly "
                   "painted hidden artwork before a quality PASS.",
        "optional_roles_by_asset": list(OPTIONAL[asset]),
    }
