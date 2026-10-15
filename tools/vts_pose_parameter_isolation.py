"""Native frame QA: a head-yaw parameter must not merely translate the eyes.

This is a conservative pixel-level isolation test, not a certification of
facial anatomy or garment fitting. Native model renders are mandatory.
"""
from pathlib import Path

import numpy as np
from PIL import Image


def _read_rgb(root: Path, pose: str) -> np.ndarray:
    with Image.open(root / (pose + ".png")) as img:
        return np.asarray(img.convert("RGB"), dtype=np.int16)


def _difference(one: np.ndarray, two: np.ndarray) -> np.ndarray:
    return np.max(np.abs(one - two), axis=2) > 12


def inspect_pose_parameter_isolation(root: Path) -> dict:
    from scipy.ndimage import binary_dilation

    root = Path(root)
    neutral = _read_rgb(root, "neutral")
    gaze_l, gaze_r = (_read_rgb(root, name)
                      for name in ("gaze_left", "gaze_right"))
    yaw_l, yaw_r = (_read_rgb(root, name)
                    for name in ("yaw_left", "yaw_right"))
    if any(im.shape != neutral.shape for im in (gaze_l, gaze_r, yaw_l, yaw_r)):
        raise ValueError("NATIVE_POSE_FRAME_DIMENSIONS_MISMATCH")

    # A gaze-only change should remain inside the face, not animate garments.
    gaze_changed = _difference(neutral, gaze_l) | _difference(neutral, gaze_r)
    gaze_count = int(gaze_changed.sum())
    changed_near_eyes = binary_dilation(gaze_changed, iterations=12)
    foreground = np.max(neutral, axis=2) > 40  # native black clear buffer
    row, _col = np.nonzero(foreground)
    failures = []
    if len(row) < 1000:
        failures.append({"code": "NATIVE_PARAMETER_ISOLATION_NO_CHARACTER"})
        head_bottom = neutral.shape[0]
    else:
        top, bottom = int(row.min()), int(row.max())
        head_bottom = top + round((bottom - top) * .64)
    outside_face = int(gaze_changed[head_bottom:, :].sum())
    if gaze_count >= 50 and outside_face > max(100, round(gaze_count * .20)):
        failures.append({
            "code": "NATIVE_GAZE_ANIMATES_BODY_OR_OUTFIT",
            "changed_below_face": outside_face, "gaze_changed_pixels": gaze_count,
        })
    yaw_diagnostics = []
    for name, image in (("yaw_left", yaw_l), ("yaw_right", yaw_r)):
        changed = _difference(neutral, image)
        outside_gaze = int(np.count_nonzero(changed & ~changed_near_eyes))
        total = int(changed.sum())
        yaw_diagnostics.append({
            "pose": name, "changed_pixels": total,
            "changed_outside_gaze_region": outside_gaze,
        })
        # Truly turning a head changes facial outlines/nose/ears/hair too.
        # It cannot be visually identical to moving only the pupils.
        if gaze_count >= 50 and outside_gaze < max(100, round(gaze_count * .20)):
            failures.append({
                "code": "NATIVE_HEAD_YAW_IS_EYEBALL_ONLY",
                "pose": name, "changed_outside_gaze_region": outside_gaze,
                "gaze_changed_pixels": gaze_count,
            })
    return {
        "schema": "vtuber/native-pose-parameter-isolation-v1",
        "gaze_changed_pixels": gaze_count,
        "gaze_changed_below_face_pixels": outside_face,
        "head_roi_bottom_row": head_bottom,
        "yaw": yaw_diagnostics,
        "failures": failures,
        "passed": bool(gaze_count >= 50) and not failures,
        "note": "Heuristic pixel QA; cannot prove part IDs or garment volume conservation.",
    }
