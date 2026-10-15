"""Reject BODY rigs that tear apart in *native MOC3 screenshots*.

A render changing with a parameter is not evidence that the head, arm, hand,
or torso stayed connected. This is a conservative geometric sanity check for
the existing black-background OpenGL renderer, not a certificate of artistic
quality. Geometry failures are preserved in native_pose_report.json.
"""
from __future__ import annotations

from pathlib import Path

POSES = (
    "neutral", "yaw_left", "yaw_right", "pitch_up", "pitch_down",
    "roll_left", "roll_right", "blink_neutral", "mouth_open",
)


def inspect_native_pose_frames(root: Path) -> dict:
    import numpy as np
    from PIL import Image
    try:
        from scipy.ndimage import label
    except ImportError as exc:
        raise RuntimeError("NATIVE_GEOMETRY_QA_REQUIRES_SCIPY") from exc

    root = Path(root)
    entries, failures = [], []
    neutral = None
    for pose in POSES:
        path = root / (pose + ".png")
        with Image.open(path) as frame:
            rgb = np.asarray(frame.convert("RGB"))
        # This specific renderer clears to black. Threshold is intentionally
        # permissive for colored artwork and rejects all-black output.
        foreground = np.max(rgb, axis=2) > 40
        total = int(foreground.sum())
        if total < 1000:
            failures.append({"pose": pose, "code": "NATIVE_GEOMETRY_NEAR_EMPTY",
                             "foreground_pixels": total})
            continue
        labels, count = label(foreground, structure=np.ones((3, 3), dtype=np.uint8))
        counts = np.bincount(labels.ravel(), minlength=count + 1)[1:]
        components = sorted((int(n) for n in counts if n >= 200), reverse=True)
        largest = components[0] if components else 0
        fraction = largest / total
        sides = int(foreground[:, :3].sum() + foreground[:, -3:].sum())
        record = {"pose": pose, "foreground_pixels": total,
                  "largest_connected_fraction": round(fraction, 6),
                  "largest_components_px": components[:8],
                  "side_border_foreground_pixels": sides}
        entries.append(record)
        if pose == "neutral":
            neutral = record
            if fraction < 0.95:
                failures.append({"code": "NATIVE_BODY_NEUTRAL_ALREADY_DISCONNECTED", **record})
            continue
        if neutral and neutral["largest_connected_fraction"] >= 0.95:
            if fraction < 0.95:
                failures.append({"code": "NATIVE_BODY_LIMBS_OR_HEAD_DETACHED", **record})
            if sides > 30 and neutral["side_border_foreground_pixels"] < 5:
                failures.append({"code": "NATIVE_BODY_ROTATION_CLIPPED_AT_CANVAS", **record})

    return {
        "schema": "vtuber/native-body-pose-geometry-v1",
        "method": "native MOC3 RGB connected-component and border checks",
        "background": "OpenGL black clear buffer",
        "geometry_passed": not failures,
        "poses": entries,
        "failures": failures,
        "warning": "Geometry PASS does not prove gaze, clipping masks, exact keyforms or artistic quality.",
    }
