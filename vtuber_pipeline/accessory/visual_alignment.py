"""Estimate attachment pivot from real accessory geometry and the chosen VRM anchor.

No camera orientation is fabricated from a single accessory GLB. The output
defines a source-mesh pivot in its *own* coordinates; fitting bakes this pivot
before the bone-local attachment transform is applied.
"""
from __future__ import annotations

import json
from pathlib import Path


# Explicit attachment geometry conventions. Do not infer left/right from
# screen positions; they are VRM character-relative anchor names.
_BOTTOM_ANCHORS = {"HEAD_TOP", "LEFT_FOOT", "RIGHT_FOOT"}
_TOP_ANCHORS = {"LEFT_EAR", "RIGHT_EAR", "NECK"}
_BACK_ANCHORS = {"BACK"}
_CENTER_ANCHORS = {
    "FACE", "CHEST", "LEFT_SHOULDER", "RIGHT_SHOULDER",
    "LEFT_HAND", "RIGHT_HAND", "HIPS", "CUSTOM",
}


def estimate_visual_alignment(
    accessory_path: str,
    anchor_name: str,
    anchor_manifest: dict,
    output_dir: str,
    image_path: str | None = None,
) -> dict:
    """Calculate a physically meaningful source pivot without guessing pose.

    Anchor "HEAD_TOP" places the lowest hat point on the head attachment.
    Earrings/neck pieces hang down from their upper contact surface.
    Remaining anchors use the mesh center; a back item uses its foremost
    local-Z face. User-provided actual image may be recorded but is not
    claimed to calibrate a 3D camera automatically.
    """
    import numpy as np
    import trimesh

    candidates = [
        anchor for anchor in anchor_manifest.get("anchors", [])
        if anchor.get("name") == anchor_name
    ]
    if len(candidates) != 1:
        raise ValueError(f"exactly one VRM attachment anchor required: {anchor_name}")
    anchor = candidates[0]
    for field in ("bone", "target_size", "node_index", "position", "offset"):
        if field not in anchor:
            raise ValueError(f"{anchor_name}: anchor missing {field}")
    allowed = _BOTTOM_ANCHORS | _TOP_ANCHORS | _BACK_ANCHORS | _CENTER_ANCHORS
    if anchor_name not in allowed:
        raise ValueError(f"unsupported attachment anchor: {anchor_name}")

    source = Path(accessory_path)
    if not source.is_file() or source.stat().st_size == 0:
        raise FileNotFoundError(source)
    loaded = trimesh.load(str(source), process=False)
    if isinstance(loaded, trimesh.Scene):
        loaded = loaded.to_mesh()
    if not isinstance(loaded, trimesh.Trimesh):
        raise ValueError("accessory contains no triangle mesh")
    vertices = np.asarray(loaded.vertices, dtype=np.float64)
    if len(vertices) < 3 or not np.isfinite(vertices).all():
        raise ValueError("accessory geometry must contain finite vertices")
    lower, upper = vertices.min(axis=0), vertices.max(axis=0)
    extents = upper - lower
    if float(np.max(extents)) < 1e-8:
        raise ValueError("accessory is degenerate")
    midpoint = (lower + upper) / 2.0
    pivot = midpoint.copy()
    pivot_rule = "center_of_bounds"
    if anchor_name in _BOTTOM_ANCHORS:
        pivot[1] = lower[1]
        pivot_rule = "lower_contact"
    elif anchor_name in _TOP_ANCHORS:
        pivot[1] = upper[1]
        pivot_rule = "upper_suspension"
    elif anchor_name in _BACK_ANCHORS:
        # -Z is the rear-facing contact surface for the Y-up VRM rig.
        pivot[2] = upper[2]
        pivot_rule = "forward_contact"

    if image_path is not None:
        from PIL import Image
        with Image.open(image_path) as image:
            image.verify()
    result = {
        "status": "complete",
        "source_mesh": str(source.resolve()),
        "anchor_name": anchor_name,
        "parent_bone": anchor["bone"],
        "anchor_node_index": anchor["node_index"],
        "source_bounds_min": lower.tolist(),
        "source_bounds_max": upper.tolist(),
        "source_pivot": pivot.astype(float).tolist(),
        "pivot_rule": pivot_rule,
        "source_forward_axis": "+Z",
        "camera_orientation_verified": False,
        "rotation_override": None,
        "reference_image": str(Path(image_path).resolve()) if image_path else None,
        "convention": "Y-up, avatar character-relative anchor, local pivot only",
    }
    path = Path(output_dir) / "visual_alignment.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    result["alignment_json"] = str(path)
    return result
