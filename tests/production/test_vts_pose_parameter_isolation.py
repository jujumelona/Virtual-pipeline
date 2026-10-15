"""Native-pose guard must catch a moving eyeball masquerading as head yaw."""
import numpy as np
from PIL import Image

from tools.vts_pose_parameter_isolation import inspect_pose_parameter_isolation


def _save(folder, label, rgb):
    Image.fromarray(rgb.astype(np.uint8), "RGB").save(folder / (label + ".png"))


def _frame(*, head_shift=0, eye_shift=0, garment_offset=False):
    rgb = np.zeros((160, 160, 3), dtype=np.uint8)
    rgb[10:75, 25+head_shift:125+head_shift] = [210, 160, 150]
    rgb[75:150, 35:115] = [80, 120, 190]
    for x in (49, 91):
        rgb[36:48, x-12+head_shift:x+12+head_shift] = [245, 245, 245]
        rgb[38:47, x-4+head_shift+eye_shift:x+4+head_shift+eye_shift] = [40, 30, 60]
    if garment_offset:
        rgb[105:125, 55:105] = [200, 30, 30]
    return rgb


def test_correct_head_yaw_and_independent_gaze_pass(tmp_path):
    _save(tmp_path, "neutral", _frame())
    _save(tmp_path, "gaze_left", _frame(eye_shift=-5))
    _save(tmp_path, "gaze_right", _frame(eye_shift=5))
    _save(tmp_path, "yaw_left", _frame(head_shift=-8))
    _save(tmp_path, "yaw_right", _frame(head_shift=8))
    report = inspect_pose_parameter_isolation(tmp_path)
    assert report["passed"], report["failures"]


def test_iris_only_fake_head_turn_fails(tmp_path):
    _save(tmp_path, "neutral", _frame())
    _save(tmp_path, "gaze_left", _frame(eye_shift=-5))
    _save(tmp_path, "gaze_right", _frame(eye_shift=5))
    _save(tmp_path, "yaw_left", _frame(eye_shift=-5))
    _save(tmp_path, "yaw_right", _frame(eye_shift=5))
    report = inspect_pose_parameter_isolation(tmp_path)
    assert not report["passed"]
    assert any(f["code"] == "NATIVE_HEAD_YAW_IS_EYEBALL_ONLY"
               for f in report["failures"])


def test_gaze_driving_clothing_is_rejected(tmp_path):
    _save(tmp_path, "neutral", _frame())
    _save(tmp_path, "gaze_left", _frame(eye_shift=-5, garment_offset=True))
    _save(tmp_path, "gaze_right", _frame(eye_shift=5, garment_offset=True))
    _save(tmp_path, "yaw_left", _frame(head_shift=-8))
    _save(tmp_path, "yaw_right", _frame(head_shift=8))
    report = inspect_pose_parameter_isolation(tmp_path)
    assert not report["passed"]
    assert any(f["code"] == "NATIVE_GAZE_ANIMATES_BODY_OR_OUTFIT"
               for f in report["failures"])
