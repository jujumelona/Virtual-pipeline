"""Unit-level evidence for native mouth interpolation checks (synthetic frames).

These tests do not certify a real model. Native MOC3 screenshot capture
is required separately to claim a specific VTuber mouth works.
"""
from pathlib import Path

import numpy as np
from PIL import Image

from tools.vts_native_mouth_motion import inspect_native_mouth_motion


NAMES = ("neutral", "mouth_quarter", "mouth_half",
         "mouth_three_quarters", "mouth_open")


def _save_states(root: Path, progress: tuple[int, ...]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for name, width in zip(NAMES, progress):
        im = np.zeros((80, 80, 3), dtype=np.uint8)
        if width:
            im[32:40, 25:25 + width] = (150, 45, 70)
        Image.fromarray(im).save(root / (name + ".png"))


def test_native_mouth_gradual_interpolation_passes(tmp_path):
    _save_states(tmp_path, (0, 5, 10, 15, 20))
    result = inspect_native_mouth_motion(tmp_path)
    assert result["passed"]
    assert len(result["intermediate_frames"]) == 3
    assert not result["actual_lips_shape_visually_certified"]


def test_native_mouth_hard_toggle_is_rejected(tmp_path):
    _save_states(tmp_path, (0, 0, 0, 20, 20))
    result = inspect_native_mouth_motion(tmp_path)
    assert not result["passed"]
    assert any(x["code"] == "NATIVE_MOUTH_INTERMEDIATE_STUCK_OR_SNAPPED"
               for x in result["failures"])


def test_native_mouth_no_opening_is_rejected(tmp_path):
    _save_states(tmp_path, (0, 0, 0, 0, 0))
    result = inspect_native_mouth_motion(tmp_path)
    assert not result["passed"]
    assert any(x["code"] == "NATIVE_MOUTH_OPEN_END_STATES_IDENTICAL"
               for x in result["failures"])
