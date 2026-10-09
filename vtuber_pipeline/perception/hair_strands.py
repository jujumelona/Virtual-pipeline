"""Split only genuinely disconnected observed hair mask components into strands.

Contiguous painted hair stays one part: there is no evidence for boundaries
without individual alpha/mask islands, so the pipeline must not draw fake cuts.
"""
from __future__ import annotations

from pathlib import Path
import numpy as np
from PIL import Image


def split_observed_hair_islands(
    masks: list[dict], output_dir: str, *, min_pixels: int = 14,
) -> list[dict]:
    import cv2
    dest = Path(output_dir)
    dest.mkdir(parents=True, exist_ok=True)
    output = []
    for entry in masks:
        name = str(entry.get("semantic_id", ""))
        if not name.startswith(("hair.front", "hair.side", "hair.back")):
            output.append(entry)
            continue
        mask_path = Path(entry["mask_png"])
        if not mask_path.is_file():
            raise FileNotFoundError(mask_path)
        binary = np.asarray(Image.open(mask_path).convert("L")) > 0
        count, labels, stats, _centers = cv2.connectedComponentsWithStats(
            binary.astype(np.uint8), connectivity=8,
        )
        eligible = [
            idx for idx in range(1, count)
            if stats[idx, cv2.CC_STAT_AREA] >= min_pixels
        ]
        if len(eligible) < 2:
            output.append(entry)
            continue
        # No observed foreground is thrown out, even isolated small tufts.
        small = [
            idx for idx in range(1, count)
            if stats[idx, cv2.CC_STAT_AREA] < min_pixels
        ]
        for idx in small:
            # Attach a tiny genuine island to the closest big component in the
            # semantic group, rather than changing its actual pixel mask.
            ys, xs = np.where(labels == idx)
            x, y = np.mean(xs), np.mean(ys)
            choices = []
            for parent in eligible:
                py, px = np.where(labels == parent)
                choices.append((float((np.mean(px)-x)**2 + (np.mean(py)-y)**2), parent))
            parent = min(choices)[1]
            labels[labels == idx] = parent
        for offset, group in enumerate(sorted(eligible,
                                              key=lambda idx: float(stats[idx, cv2.CC_STAT_LEFT]))):
            selected = labels == group
            name_suffix = f".island{offset:02d}"
            p = dest / f"hair_{len(output):04d}.png"
            Image.fromarray((selected * 255).astype(np.uint8), "L").save(p)
            output.append({
                **entry, "semantic_id": name + name_suffix,
                "mask_png": str(p),
                "segmentation_origin": "sam_connected_component",
            })
        # Every actual foreground pixel must appear in exactly one child.
        assembled = np.zeros_like(binary, dtype=bool)
        for item in output[-len(eligible):]:
            child = np.asarray(Image.open(item["mask_png"]).convert("L")) > 0
            if (assembled & child).any():
                raise RuntimeError("Hair strand pixels overlap")
            assembled |= child
        if not np.array_equal(assembled, binary):
            raise RuntimeError("Hair strand decomposition did not preserve observed pixels")
    return output
