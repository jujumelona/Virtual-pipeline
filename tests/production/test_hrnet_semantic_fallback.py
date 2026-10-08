"""Landmark-assisted semantic boxes are observed, not guessed.

The upstream 28-point HRNet flip map pairs left/right eye and eyebrow
index ranges. Facial close-ups from a different canvas are never reused.
"""
import numpy as np
import pytest

from tools.model_workers.florence_worker import landmark_fallback_boxes


def _data():
    points = np.zeros((28, 2), dtype=float)
    points[:] = [120, 130]
    points[5:8] = [[60, 55], [70, 54], [82, 56]]
    points[8:11] = [[180, 55], [190, 54], [201, 56]]
    points[11:17] = [[58, 80], [62, 76], [70, 76], [82, 81], [70, 86], [62, 84]]
    points[17:23] = [[175, 80], [180, 75], [188, 75], [202, 81], [188, 86], [181, 85]]
    points[23:28] = [[112, 165], [118, 163], [126, 163], [133, 165], [123, 175]]
    return {"image_size": [256, 256], "landmarks": points.tolist(),
            "landmark_scores": [0.99] * 28}


def test_faces_generate_correct_character_relative_eye_brow_boxes():
    boxes = landmark_fallback_boxes(_data(), (256, 256), set())
    assert {box["semantic_id"] for box in boxes} == {
        "eye.left", "eye.right", "brow.left", "brow.right", "mouth",
    }
    by_name = {box["semantic_id"]: box for box in boxes}
    assert by_name["eye.left"]["bbox_xyxy"][0] > by_name["eye.right"]["bbox_xyxy"][0]
    assert by_name["brow.left"]["bbox_xyxy"][0] > by_name["brow.right"]["bbox_xyxy"][0]
    assert all(box["source"].endswith("HRNetV2-28") for box in boxes)


def test_close_up_landmarks_are_not_reused_on_a_different_canvas():
    assert landmark_fallback_boxes(_data(), (768, 1024), set()) == []


def test_unknown_or_untrusted_landmarks_never_create_rois():
    document = _data()
    document["landmark_scores"] = [0.01] * 28
    assert landmark_fallback_boxes(document, (256, 256), set()) == []
    document["landmarks"] = [[1, 2]]
    with pytest.raises(ValueError, match="28 finite"):
        landmark_fallback_boxes(document, (256, 256), set())


def test_florence_detected_part_is_not_duplicated():
    result = landmark_fallback_boxes(_data(), (256, 256), {"mouth", "eye.left"})
    assert "mouth" not in {box["semantic_id"] for box in result}
    assert "eye.left" not in {box["semantic_id"] for box in result}
