"""Source-reference geometry diagnostics for high-quality full-body VRM builds.

This is deliberately *not* a pose or anatomical quality classifier. It checks
measurable image/cutout geometry, and explicitly reports what it cannot prove.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def inspect_references(
    front_image: str,
    *,
    face_image: str | None = None,
    back_image: str | None = None,
    full_body: bool = False,
    output_dir: str,
) -> dict[str, Any]:
    from PIL import Image
    import numpy as np

    paths = {"front": front_image, "face": face_image, "back": back_image}
    report: dict[str, Any] = {
        "status": "error", "full_body": full_body,
        "images": {}, "errors": [], "warnings": [],
        "anatomy_verified": False,
    }
    for role, supplied in paths.items():
        if not supplied:
            continue
        path = Path(supplied)
        if not path.is_file():
            report["errors"].append(f"{role}: missing image: {path}")
            continue
        try:
            with Image.open(path) as image:
                image.load()
                width, height = image.size
                if width < 256 or height < 256:
                    report["errors"].append(f"{role}: image smaller than 256 pixels")
                has_alpha = "A" in image.getbands()
                alpha_bounds = None
                if has_alpha:
                    alpha = np.asarray(image.getchannel("A"))
                    fg = alpha > 32
                    # An entirely opaque RGBA image is *not* an alpha cutout.
                    if np.any(fg) and np.any(~fg):
                        yy, xx = np.nonzero(fg)
                        alpha_bounds = [int(xx.min()), int(yy.min()),
                                        int(xx.max()) + 1, int(yy.max()) + 1]
                report["images"][role] = {
                    "path": str(path.resolve()), "size": [width, height],
                    "alpha_foreground_bbox": alpha_bounds,
                }
                if full_body and role in {"front", "back"}:
                    aspect = width / max(height, 1)
                    if not (0.32 <= aspect <= 1.0 and height >= 768):
                        report["errors"].append(
                            f"{role}: full-body reference requires portrait "
                            "aspect 0.32..1.0 and height >= 768")
                    if alpha_bounds is not None:
                        left, top, right, bottom = alpha_bounds
                        coverage = (bottom - top) / height
                        margin = min(left, top, width - right, height - bottom)
                        if coverage < 0.62:
                            report["errors"].append(
                                f"{role}: alpha silhouette occupies only {coverage:.1%} of height")
                        if margin < max(2, round(min(width, height) * 0.005)):
                            report["errors"].append(
                                f"{role}: alpha silhouette touches image border (cropped body?)")
                    else:
                        report["warnings"].append(
                            f"{role}: opaque image: complete feet/hands and silhouette "
                            "cannot be verified automatically; a cutout is recommended")
        except Exception as exc:
            report["errors"].append(f"{role}: image decode failed: {exc}")

    if full_body and not face_image:
        report["errors"].append(
            "full-body mode requires an independent high-resolution face reference "
            "for the 28-point facial landmark gate")
    report["status"] = "error" if report["errors"] else "complete"
    path = Path(output_dir) / "reference_quality.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["report_path"] = str(path)
    return report
