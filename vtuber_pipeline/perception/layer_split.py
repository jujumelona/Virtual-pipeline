"""Separate observed full-canvas RGBA parts and identify genuine overlay occlusions.

Unknown pixels are never silently invented. Hidden-fill masks are proposals
restricted to a higher-z foreground part; ordinary outer silhouettes are not
occlusions and must not trigger an expensive FLUX editing pass.
"""
from pathlib import Path
import json

import numpy as np
from PIL import Image, ImageFilter

from vtuber_pipeline.common.schemas import Part, PartsDocument
from vtuber_pipeline.common.part_taxonomy import z_order


def _landmark_subset(semantic_id: str, all_points: list) -> list:
    """Choose aligned semantic HRNet points in character-relative coordinates."""
    if len(all_points) != 28:
        return []
    points = np.asarray(all_points, dtype=float)
    if semantic_id in {"face", "head"}:
        return all_points
    if semantic_id.startswith("mouth"):
        return points[23:28].tolist()
    if semantic_id.startswith("eye."):
        groups = [points[11:17], points[17:23]]
        groups.sort(key=lambda g: float(g[:, 0].mean()), reverse=True)
        if semantic_id.startswith("eye.left"):
            return groups[0].tolist()
        if semantic_id.startswith("eye.right"):
            return groups[1].tolist()
        return points[11:23].tolist()
    if semantic_id.startswith("brow.") or semantic_id.startswith("eyebrow."):
        groups = [points[5:8], points[8:11]]
        groups.sort(key=lambda g: float(g[:, 0].mean()), reverse=True)
        return (groups[0] if ".left" in semantic_id else groups[1]).tolist()
    if semantic_id in {"brow", "eyebrow"}:
        return points[5:11].tolist()
    return []


def split_semantic_layers(original_rgba: str, masks_json: str,
                          landmarks_json: str, output_dir: str) -> PartsDocument:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    base = Image.open(original_rgba).convert("RGBA")
    width, height = base.size
    # Store actual detector points in the same source canvas only; a separate
    # zoomed face reference cannot be mapped without image registration.
    face_keypoints = []
    landmark_path = Path(landmarks_json)
    if landmark_path.is_file():
        record = json.loads(landmark_path.read_text(encoding="utf-8"))
        if record.get("image_size") == [width, height]:
            candidate = np.asarray(record.get("landmarks", []), dtype=float)
            if candidate.shape == (28, 2) and np.isfinite(candidate).all():
                face_keypoints = candidate.tolist()
    masks = json.loads(Path(masks_json).read_text(encoding="utf-8"))
    if not masks.get("parts"):
        raise ValueError("SAM produced no semantic part masks")

    observed = []
    for entry in masks["parts"]:
        identity = entry["semantic_id"]
        alpha = Image.open(entry["mask_png"]).convert("L")
        if alpha.size != (width, height):
            raise ValueError("mask not in original image coordinates: " + identity)
        raw = np.asarray(alpha)
        if not np.any(raw):
            continue
        observed.append((identity, z_order(identity), entry["mask_png"], alpha, raw))

    if not observed:
        raise ValueError("empty segmented character")

    # Process highest depth first. A part has only the masks of STRICTLY
    # higher-depth parts as possible occluders; same-depth features cannot
    # incorrectly invent missing regions in one another.
    observed.sort(key=lambda item: (item[1], item[0]), reverse=True)
    higher_priority_union = np.zeros((height, width), dtype=bool)
    parts = []
    index = 0
    position = 0
    while position < len(observed):
        depth = observed[position][1]
        following = position
        while following < len(observed) and observed[following][1] == depth:
            following += 1

        for identity, _, mask_path, alpha, raw in observed[position:following]:
            ys, xs = np.nonzero(raw > 0)
            rgba = np.asarray(base).copy()
            rgba[:, :, 3] = np.minimum(rgba[:, :, 3], raw)
            rgba_path = out / f"part_{index:03d}.png"
            Image.fromarray(rgba, "RGBA").save(rgba_path)

            expanded = np.asarray(alpha.filter(ImageFilter.MaxFilter(15))) > 0
            hidden = expanded & (raw == 0) & higher_priority_union
            hidden_path = None
            if np.any(hidden):
                target = out / f"hidden_{index:03d}.png"
                Image.fromarray((hidden * 255).astype(np.uint8), "L").save(target)
                hidden_path = str(target)

            parts.append(Part(
                identity, str(rgba_path), mask_path, hidden_path,
                [int(xs.min()), int(ys.min()), int(xs.max() + 1), int(ys.max() + 1)],
                depth, _landmark_subset(identity, face_keypoints), "sam2.1",
            ))
            index += 1

        for _identity, _depth, _path, _image, raw in observed[position:following]:
            higher_priority_union |= raw > 0
        position = following

    parts.sort(key=lambda part: (part.z_order, part.semantic_id))
    result = PartsDocument(width, height, parts, None, "")
    result.write(str(out / "parts.json"))
    return result
