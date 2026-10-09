"""Observed facial subpart segmentation from SAM masks and full-canvas pixels.

No generated iris, eyelid or mouth pixels are invented: every child mask is a
subset of a measured parent mask. Lack of contrast leaves the parent intact.
"""
from __future__ import annotations
from pathlib import Path

import numpy as np
from PIL import Image


def _components(binary: np.ndarray, minimum: int = 5) -> np.ndarray:
    import cv2
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        binary.astype(np.uint8), connectivity=8,
    )
    if count < 2:
        return np.zeros_like(binary, dtype=bool)
    idx = max(range(1, count), key=lambda i: int(stats[i, cv2.CC_STAT_AREA]))
    if stats[idx, cv2.CC_STAT_AREA] < minimum:
        return np.zeros_like(binary, dtype=bool)
    return labels == idx


def split_facial_subparts(
    image_rgba: str, semantic_masks: list[dict], output_dir: str,
) -> list[dict]:
    """Split visibly supported eye/eyebrow/mouth layers into smaller SAM regions.

    Subpart evidence uses measured RGB contrast and mask topology. A part is
    split only if at least two nonempty regions are actually distinguishable.
    The exact union of children then equals the original SAM mask.
    """
    import cv2
    base = np.asarray(Image.open(image_rgba).convert("RGBA"))
    folder = Path(output_dir)
    folder.mkdir(parents=True, exist_ok=True)
    h, w = base.shape[:2]
    rgb = base[:, :, :3]
    light = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)[:, :, 0].astype(float)
    produced: list[dict] = []

    def emit(part: dict, ident: str, keep: np.ndarray):
        path = folder / f"sub_{len(produced):04d}.png"
        Image.fromarray((keep * 255).astype(np.uint8), "L").save(path)
        produced.append({**part, "semantic_id": ident, "mask_png": str(path),
                         "segmentation_origin": "observed_rgb_and_sam"})

    for original in semantic_masks:
        ident = original["semantic_id"]
        if (ident not in ("eye.left", "eye.right", "mouth")
                or not Path(original["mask_png"]).is_file()):
            produced.append(original)
            continue
        mask = np.asarray(Image.open(original["mask_png"]).convert("L")) > 0
        if mask.shape != (h, w):
            raise ValueError(f"{ident}: original SAM mask differs from image canvas")
        area = int(mask.sum())
        if area < 24:
            produced.append(original)
            continue
        ys, xs = np.where(mask)
        yy0, yy1 = int(ys.min()), int(ys.max()) + 1
        xx0, xx1 = int(xs.min()), int(xs.max()) + 1
        if xx1 - xx0 < 5 or yy1 - yy0 < 4:
            produced.append(original)
            continue
        lum = light[yy0:yy1, xx0:xx1]
        roi = mask[yy0:yy1, xx0:xx1]
        samples = lum[roi]
        # A real dark mouth/iris may occupy less than 20% of the broad SAM
        # parent region; 20/80 quantiles then BOTH land on bright skin and
        # silently erase visibly observed subparts. Use robust 10/90
        # separation and retain the existing minimum-area component gate.
        q10, q90 = np.quantile(samples, [0.1, 0.9])
        if q90 - q10 < 14:
            produced.append(original)
            continue
        dark = (lum < (q10 + q90) * .5) & roi
        if ident.startswith("eye."):
            # The iris is the biggest central dark connected region. Peripheral
            # eyelid strokes are identified by their proximity to the top edge.
            cy = (yy1 - yy0) * .50
            cx = (xx1 - xx0) * .50
            radius_x = max((xx1 - xx0) * .36, 1)
            radius_y = max((yy1 - yy0) * .53, 1)
            grid_y, grid_x = np.indices(roi.shape)
            interior = (((grid_x - cx) / radius_x) ** 2
                        + ((grid_y - cy) / radius_y) ** 2) <= 1
            iris = _components(dark & interior, max(5, area // 80))
            if int(iris.sum()) < max(5, area // 30) or iris.sum() >= area * .70:
                produced.append(original)
                continue
            # Visible dark strokes near the superior eye margin count as eyelid.
            lid = dark & ~iris & (grid_y < (yy1 - yy0) * .42)
            if int(lid.sum()) < max(4, area // 55):
                produced.append(original)
                continue
            white = roi & ~iris & ~lid
            if int(white.sum()) < max(5, area // 20):
                produced.append(original)
                continue
            group = [(ident + ".iris", iris), (ident + ".lid", lid),
                     (ident + ".white", white)]
        else:
            inner = _components(dark, max(5, area // 40))
            lip = roi & ~inner
            if (inner.sum() < max(5, area // 25)
                    or lip.sum() < max(5, area // 25)):
                produced.append(original)
                continue
            group = [("mouth.inner", inner), ("mouth.lip", lip)]
        full_union = np.zeros_like(mask)
        for key, region in group:
            full = np.zeros_like(mask)
            full[yy0:yy1, xx0:xx1] = region
            if np.any(full & full_union):
                raise RuntimeError(f"{ident}: detected child regions overlap")
            full_union |= full
            emit(original, key, full)
        if not np.array_equal(full_union, mask):
            raise RuntimeError(f"{ident}: child regions lost observed pixels")
    return produced
