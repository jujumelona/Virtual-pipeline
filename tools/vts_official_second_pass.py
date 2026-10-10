"""Exact-source-pixel partition using masks from one extra See-through pass.

No semantic assumptions, no recursive calls and no generated RGB substitutions.
A failed/unchanged split returns the original source layer unchanged.
"""
from __future__ import annotations

import numpy as np
from PIL import Image


def partition_from_masks(layer: dict, masks: list[Image.Image],
                         *, min_fraction: float = 0.03) -> tuple[list[dict], dict]:
    source = layer["image"].convert("RGBA")
    rgba = np.asarray(source, dtype=np.uint8)
    visible = rgba[:, :, 3] > 0
    count = int(np.count_nonzero(visible))
    if count == 0 or len(masks) < 2:
        return [layer], {"accepted": False, "reason": "empty_or_single_mask"}
    for mask in masks:
        if mask.size != source.size:
            raise ValueError("Official second-pass masks must use the source canvas")
    alpha = np.stack(
        [np.asarray(x.getchannel("A"), dtype=np.uint8) for x in masks], axis=0
    )
    # No upscaled model RGB enters the output. Masks assign pixels; all actual
    # RGBA pixel values come from the first-pass PSD, including soft edges.
    cover = (alpha.max(axis=0) > 16) & visible
    covered = int(np.count_nonzero(cover))
    coverage = covered / count
    if coverage < 0.75:
        return [layer], {"accepted": False, "reason": "insufficient_mask_coverage",
                         "coverage": round(coverage, 5)}
    assigned = alpha.argmax(axis=0)
    minimum = max(24, int(count * min_fraction))
    meaningful = [i for i in range(len(masks))
                  if int(np.count_nonzero(visible & (assigned == i))) >= minimum]
    if len(meaningful) < 2:
        return [layer], {"accepted": False, "reason": "no_meaningful_division",
                         "regions": len(meaningful)}
    # Any weakly-covered pixels are assigned to a real accepted mask rather
    # than deleted. Rejects masks with no material second independent region.
    assignment = np.asarray(meaningful, dtype=np.int32)[
        alpha[meaningful].argmax(axis=0)]
    children = []
    for order, idx in enumerate(meaningful, start=1):
        block = np.zeros_like(rgba)
        owns = visible & (assignment == idx)
        block[owns] = rgba[owns]
        if not np.any(owns):
            continue
        out = Image.fromarray(block, "RGBA")
        children.append({"name": f'{layer["name"]}.pass2.{order:02d}',
                         "image": out,
                         "depth": layer.get("depth", 0) + 1})
    if len(children) < 2:
        return [layer], {"accepted": False, "reason": "empty_children"}
    reconstructed = np.zeros_like(rgba)
    for child in children:
        pixels = np.asarray(child["image"], dtype=np.uint8)
        owns = pixels[:, :, 3] > 0
        reconstructed[owns] = pixels[owns]
    if (not np.array_equal(reconstructed[:, :, 3], rgba[:, :, 3])
            or not np.array_equal(reconstructed[visible, :3], rgba[visible, :3])):
        raise RuntimeError("Second-pass mask partition failed exact source reconstruction")
    return children, {"accepted": True, "reason": "exact_rgba_source_partition",
                      "coverage": round(coverage, 5),
                      "child_count": len(children)}
