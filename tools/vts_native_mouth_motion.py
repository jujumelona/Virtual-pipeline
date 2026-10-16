"""Verify native Cubism mouth keyforms interpolate rather than toggle.

This consumes actual MOC3 OpenGL screenshots, not PSD names or generated
reference art. Smoothness is only a screen-space sanity check; it cannot
guarantee lip-sync accuracy, artistic quality, or correct upper/lower lips.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

STATES = (
    "neutral", "mouth_quarter", "mouth_half",
    "mouth_three_quarters", "mouth_open",
)


def _rgb(path: Path) -> np.ndarray:
    with Image.open(path) as img:
        return np.asarray(img.convert("RGB"), dtype=np.int16)


def _pixel_difference(a: np.ndarray, b: np.ndarray) -> int:
    return int(np.count_nonzero(np.max(np.abs(a - b), axis=2) > 10))


def inspect_native_mouth_motion(root: Path) -> dict:
    root = Path(root)
    frames = {name: _rgb(root / (name + ".png")) for name in STATES}
    shape = frames["neutral"].shape
    if any(x.shape != shape for x in frames.values()):
        raise ValueError("NATIVE_MOUTH_FRAME_DIMENSIONS_MISMATCH")

    closed = frames["neutral"]
    opened = frames["mouth_open"]
    span = _pixel_difference(closed, opened)
    failures = []
    if span < 40:
        failures.append({"code": "NATIVE_MOUTH_OPEN_END_STATES_IDENTICAL",
                         "changed_pixels": span})
    # Different plausible mouth geometries yield nonlinear curves. Only
    # demand visibly distinct *intermediate* poses, never linear proportions
    # or an invented maximum opening size.
    threshold = max(12, round(span * 0.006))
    details = []
    names = list(STATES)
    for index, name in enumerate(names[1:-1], 1):
        frame = frames[name]
        to_closed = _pixel_difference(frame, closed)
        to_open = _pixel_difference(frame, opened)
        from_previous = _pixel_difference(frame, frames[names[index - 1]])
        to_next = _pixel_difference(frame, frames[names[index + 1]])
        details.append({
            "pose": name, "changed_from_closed_px": to_closed,
            "changed_from_open_px": to_open,
            "changed_from_previous_px": from_previous,
            "changed_to_next_px": to_next,
        })
        if (to_closed < threshold or to_open < threshold or
                from_previous < threshold or to_next < threshold):
            failures.append({
                "code": "NATIVE_MOUTH_INTERMEDIATE_STUCK_OR_SNAPPED",
                "pose": name, "distinct_pixels_minimum": threshold,
                "changed_from_closed_px": to_closed,
                "changed_from_open_px": to_open,
                "changed_from_previous_px": from_previous,
                "changed_to_next_px": to_next,
            })
    return {
        "schema": "vtuber/native-mouth-interpolation-v1",
        "states": list(STATES),
        "end_state_changed_pixels": span,
        "intermediate_frames": details,
        "minimum_distinct_pixels": threshold,
        "passed": not failures,
        "failures": failures,
        "actual_lips_shape_visually_certified": False,
        "note": "Checks real native pose changes at 0/0.25/0.5/0.75/1; "
                "does not replace expert review of lip closure or syllables.",
    }
