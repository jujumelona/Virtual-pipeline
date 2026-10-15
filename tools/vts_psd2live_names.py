"""Semantic, pixel-preserving PSD layer labels for PSD2Live v3.3.1.

The upstream layer classifier recognizes aliases and -l/-r suffixes, but not
dot-separated See-through hierarchy such as 'eye.left.iris.pass2.01'.
This adapter only changes names, never raster pixels, part count or order.
Reference: psd2live/core/LayerClassifier.kt at v3.3.1.
"""
from __future__ import annotations

import re

# Only aliases listed in PSD2Live's LayerClassifier, not invented tags.
SAM_ALIASES = {
    "hair": "front hair", "headwear": "headwear", "face": "face",
    "eyewear": "eyewear", "ears": "ears",
    "earwear": "earwear", "nose": "nose", "mouth": "mouth",
    "neck": "neck", "neckwear": "neckwear", "topwear": "topwear",
    "handwear": "handwear", "bottomwear": "bottomwear",
    "legwear": "legwear", "footwear": "footwear", "tail": "tail",
    "wings": "wings", "objects": "objects",
}
FAMILY_ALIASES = {
    "face": "face", "head": "face", "body": "topwear", "torso": "topwear",
    "pelvis": "bottomwear", "thigh": "legwear", "shin": "legwear",
    "hair": "front hair", "eyebrow": "eyebrow", "brow": "eyebrow",
    "mouth": "mouth",
    "nose": "nose", "ear": "ears", "ears": "ears",
    "neck": "neck", "cloth": "topwear", "outfit": "topwear",
    "sleeve": "handwear", "hand": "handwear", "arm": "handwear",
    "leg": "legwear", "foot": "footwear", "shoe": "footwear",
    "accessory": "objects", "ornament": "headwear",
    "topwear": "topwear", "bottomwear": "bottomwear",
    "legwear": "legwear", "footwear": "footwear",
    "handwear": "handwear", "headwear": "headwear",
    "eyewear": "eyewear", "earwear": "earwear",
    "neckwear": "neckwear", "tail": "tail", "wings": "wings",
    "objects": "objects", "irides": "irides",
    "eyewhite": "eyewhite", "eyelash": "eyelash",
    "tooth": "tooth-t", "tongue": "tongue",
}

def _alias(original: str, sam_label: str | None) -> tuple[str | None, str]:
    tokens = [t for t in re.split(r"[.\s_\-]+", original.casefold()) if t]
    family = tokens[0] if tokens else ""
    tail = set(tokens[1:])

    # Some first-pass names nest face/skin under a generic BODY panel.
    # Preserve the more specific anatomy when the parent isn't proof of
    # clothing; visible SAM may be absent for imported/external PSDs.
    if family == "body" and tail & {"head", "face"}:
        return "face", "specific_body_source"
    # A removable plain privacy cover is a legitimate BODY-only display
    # overlay, not another face or an unrelated character outfit.
    if family == "removable" and tail >= {"neutral", "modesty", "band"}:
        return "topwear", "explicit_privacy_cover"
    if family == "face" and tail & {"detail", "blush", "cheek"}:
        return "facedetail", "specific_face_source"
    # A generated second-pass face.*.pass2.* layer is intentionally SAM-partitioned.
    # Unlike authored face_skin, its class comes from the observed SAM mask.
    if sam_label == "eyes" and family in {"unknown", "mystery", "raw"}:
        return None, "sam_generic_eyes_not_iris"
    if family == "face" and "pass2" in tail and sam_label in SAM_ALIASES:
        return SAM_ALIASES[sam_label], "sam_second_pass_partition"

    # Explicit anatomy has higher confidence than global visible-only SAM
    # masks when the original source part is hidden by hair or clothing.
    if family in ("eye", "eyes", "eyewhite", "eyelash", "irides"):
        if family == "eyewhite" or tail & {"sclera", "white", "whites", "eyewhite", "eyewhites"}:
            return "eyewhite", "fine_eye_source"
        if tail & {"closed", "close", "shut"}:
            return "eye close", "fine_closed_eye_source"
        if family == "eyelash" or tail & {"lash", "lashes", "eyelash", "lid", "eyelid"}:
            return "eyelash", "fine_eye_source"
        if family == "irides" or tail & {"iris", "irides", "pupil", "highlight"}:
            return "irides", "fine_eye_source"
        # A whole eye/eyes mask includes lashes, whites and irises; it is NOT
        # safe to send to the iris-only driver. Require a finer split.
        return None, "unsplit_eye_not_iris"
    if family == "hair":
        if "back" in tail or "rear" in tail:
            return "back hair", "explicit_hair_depth"
        if "front" in tail or "side" in tail or "bang" in tail:
            return "front hair", "explicit_hair_depth"
    if family == "mouth":
        # Image-AI authored mouth parts need exclusive states rather than
        # three independent preset MOUTH drawables shown simultaneously.
        # The actual layer pixels stay untouched and the animation/occlusion
        # must still be visually checked in Cubism/VTube Studio.
        if "tongue" in tail:
            return "tongue", "explicit_mouth_part"
        if "teeth" in tail or "tooth" in tail:
            return ("tooth-b" if tail & {"bottom", "lower", "b"} else "tooth-t"), "explicit_mouth_part"
        if tail & {"inside", "inner", "interior", "open", "opened"}:
            return "mouth open", "explicit_open_mouth_source"
        if tail & {"upper", "lower", "closed", "close", "lip"}:
            return "mouth close", "explicit_closed_lip_source"
        if "open" in tail:
            return "mouth open", "explicit_mouth_part"
        if "close" in tail or "closed" in tail:
            return "mouth close", "explicit_mouth_part"
    if family in {"cloth", "outfit"}:
        if tail & {"skirt", "pants", "bottom", "lower", "bottomwear"}:
            return "bottomwear", "specific_clothing"
        if tail & {"shoe", "foot", "footwear"}:
            return "footwear", "specific_clothing"
        if tail & {"sleeve", "gloves", "handwear"}:
            return "handwear", "specific_clothing"
    if family in ("ornament", "accessory"):
        if "eyes" in tail or "eyewear" in tail:
            return "eyewear", "explicit_accessory"
        if "ears" in tail or "earwear" in tail:
            return "earwear", "explicit_accessory"
        if "neck" in tail or "neckwear" in tail:
            return "neckwear", "explicit_accessory"
        if "head" in tail or "headwear" in tail:
            return "headwear", "explicit_accessory"
    # Body/face source layers can contain several independently labelled SAM
    # regions. Otherwise prefer the original source's semantic identity.
    # Authored anatomy is authoritative. A visible-only See-through SAM
    # prediction must NEVER turn "body" into FACE or "arm" into TOPWEAR.
    # PSD2Live v3.3.1 calls torso skin TOPWEAR and arms HANDWEAR: those are
    # its internal tags, not evidence that the artist drew clothing.
    if family in FAMILY_ALIASES and family not in {"unknown", "mystery", "raw"}:
        return FAMILY_ALIASES[family], "author_declared_anatomy_or_asset"
    if sam_label in SAM_ALIASES:
        return SAM_ALIASES[sam_label], "sam_observed_class"
    if sam_label in SAM_ALIASES:
        return SAM_ALIASES[sam_label], "sam_observed_class"
    return None, "unclassified_preserved"


def normalize_layer_names(layers: list[dict]) -> tuple[list[dict], dict]:
    """Rename without modifying pixels, re-splitting or re-ordering layers."""
    normalized = []
    records = []
    for i, layer in enumerate(layers, 1):
        old = str(layer["name"])
        tag, evidence = _alias(old, layer.get("sam_label"))
        tokens = re.split(r"[.\s_\-]+", old.casefold())
        side = None
        if "left" in tokens or "l" in tokens:
            side = "l"
        elif "right" in tokens or "r" in tokens:
            side = "r"
        # Synthetic PSD intermediates such as arm.004/arm.005 lost their
        # original left/right name. Recover side only from a strong,
        # isolated on-canvas silhouette: screen-left is character RIGHT.
        # Never classify torso/head or broad centered silhouettes this way.
        if side is None and tag in {"handwear", "legwear", "footwear", "ears"}:
            image = layer.get("image")
            if image is not None:
                rgba = image.convert("RGBA")
                bbox = rgba.getchannel("A").getbbox()
                if bbox and rgba.width >= 100:
                    center = (bbox[0] + bbox[2]) / 2.0
                    relative = center / rgba.width
                    span = (bbox[2] - bbox[0]) / rgba.width
                    if span < 0.42 and relative < 0.38:
                        side = "r"
                        evidence += "+inferred_screen_left_character_right"
                    elif span < 0.42 and relative > 0.62:
                        side = "l"
                        evidence += "+inferred_screen_right_character_left"
        # In v3.3.1 both side and variant suffix are recognized by the
        # classifier. Deterministic numeric IDs prevent collisions.
        new = (f"{tag}_{i:04d}" + (f"-{side}" if side else "")) if tag else old
        normalized.append({**layer, "name": new, "source_name": old})
        records.append({"source": old, "psd2live": new, "sam_label": layer.get("sam_label"),
                        "semantic_tag": tag, "evidence": evidence,
                        "side": side})
    return normalized, {
        "schema": "vtuber/psd2live-semantic-names-v1",
        "source_layer_count": len(layers),
        "output_layer_count": len(normalized),
        "unclassified_count": sum(x["semantic_tag"] is None for x in records),
        "pixel_operations": 0, "extra_inference_passes": 0,
        "vendor_classifier_version": "v3.3.1",
        "records": records,
    }
