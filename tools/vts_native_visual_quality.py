"""Explain observable native-rig visual risks; never certify artistic quality from JSON.

A valid MOC3/texture manifest only proves the artifact can be inspected as
a Cubism model. Front artwork alone cannot prove anime proportions, proper
side poses or seam-free keyforms. This produces an honest review companion.
"""
from __future__ import annotations

import io
import json
from pathlib import Path
from zipfile import ZipFile, BadZipFile

from PIL import Image


def _matching(archive: ZipFile, name: str) -> str | None:
    names = archive.namelist()
    matches = [
        n for n in names if n.startswith("layers_png/") and n.endswith(".png")
        and n.rsplit("/", 1)[-1].split("_", 1)[-1].casefold().startswith(
            (name + "_").casefold())
    ]
    if len(matches) == 1:
        return matches[0]
    # Older release preserves dot names (e.g., 0019_neck.019.png).
    found = [n for n in names if n.startswith("layers_png/") and n.endswith(".png")
             and ("_" + name + ".") in n.casefold()]
    return found[0] if len(found) == 1 else None


def _actual_overlap(archive: ZipFile) -> dict:
    path_neck = _matching(archive, "neck")
    path_body = _matching(archive, "topwear") or _matching(archive, "body")
    path_face = _matching(archive, "face")
    if not path_neck or not path_body:
        return {"neck_body_overlap_pixels": None,
                "face_neck_overlap_pixels": None,
                "reason": "Relevant source skin layer names not uniquely available"}
    import numpy as np
    def mask(name: str):
        with Image.open(io.BytesIO(archive.read(name))) as image:
            return np.asarray(image.convert("RGBA").getchannel("A")) > 10
    neck, body = mask(path_neck), mask(path_body)
    if neck.shape != body.shape:
        return {"neck_body_overlap_pixels": None,
                "face_neck_overlap_pixels": None,
                "reason": "Layer canvas sizes do not match"}
    joined = int((neck & body).sum())
    overlap_face = None
    if path_face:
        face = mask(path_face)
        if face.shape == neck.shape:
            overlap_face = int((neck & face).sum())
    return {
        "neck_body_overlap_pixels": joined,
        "face_neck_overlap_pixels": overlap_face,
        "source_neck": path_neck, "source_body": path_body,
    }


def review_psd2live_export(model_dir: Path, artwork_zip: Path | None = None) -> dict:
    """No GPU/Cubism invocation. Preserve measured evidence and unknown states."""
    model_dir = Path(model_dir)
    report = {
        "schema": "vtuber/native-visual-review-v1",
        "model_artifacts_created": True,
        "visual_quality_verified": False,
        "anime_style_verified": False,
        "single_visible_mouth_at_all_poses_verified": False,
        "neck_seamless_at_extreme_poses_verified": False,
        "true_side_profile_keyforms_verified": False,
        "app_tracking_verified": False,
        "status": "CUBISM_EDITOR_VISUAL_REVIEW_REQUIRED",
        "warnings": [],
    }
    debug_files = sorted(model_dir.glob("*.psd2live.json"))
    if len(debug_files) == 1:
        config = json.loads(debug_files[0].read_text(encoding="utf-8"))
        sources = [str(layer.get("source", "")) for layer in config.get("layers", [])]
        lips = [name for name in sources if
                "/ upper lip outline" in name.casefold() or
                "/ lower lip outline" in name.casefold()]
        report["synthetic_extra_mouth_outline_count"] = len(lips)
        report["synthetic_extra_mouth_outline_layers"] = lips
        yaw = config.get("faceRig", {}).get("angleX")
        report["head_yaw_keyforms"] = yaw
        if lips:
            report["warnings"].append(
                "GENERATED_LIP_OUTLINES_OVER_AUTHORED_ART: extra visible mouth contours")
        if (isinstance(yaw, list) and len(yaw) >= 2
                and max(abs(float(x)) for x in yaw) < 85):
            report["warnings"].append(
                "FULL_SIDE_PROFILE_NOT_MODELLED: automatic head yaw keyforms "
                "do not extend to actual +/-90 degree profiles")
    else:
        report["warnings"].append("PSD2LIVE_DEBUG_JSON_NOT_AVAILABLE")

    if artwork_zip:
        try:
            with ZipFile(Path(artwork_zip)) as archive:
                observed = _actual_overlap(archive)
                report["source_overlap"] = observed
                if observed.get("neck_body_overlap_pixels") == 0:
                    report["warnings"].append(
                        "NECK_BODY_UNDERPAINT_ABSENT: zero shared alpha pixels "
                        "between authored neck and torso")
        except (BadZipFile, OSError, KeyError, ValueError, TypeError):
            report["source_overlap"] = {
                "neck_body_overlap_pixels": None,
                "reason": "Source ZIP unavailable or not a layer PNG artwork package",
            }
    report["warnings"].append(
        "STYLE_EARS_PROPORTIONS_BODY_SHADING_NEED_VISUAL_REVIEW: "
        "a ZIP/JSON or MOC3 signature check is not artistic verification")
    return report
