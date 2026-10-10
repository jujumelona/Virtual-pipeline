"""Numerical preprocessing/restoration contract from pinned SkyTNT inference."""
import cv2
import numpy as np
import pytest

from tools.model_workers import anime_alpha_worker as worker


def test_preprocess_matches_official_float_resize_and_truncated_short_edge():
    rgb = np.random.default_rng(7).integers(0, 256, (31, 17, 3), dtype=np.uint8)
    actual, size, offset = worker.prepare_input(rgb)
    h, w = 1024, int(1024 * 17 / 31)
    expected = np.zeros((1024, 1024, 3), dtype=np.float32)
    expected[:, (1024-w)//2:(1024-w)//2+w] = cv2.resize(
        (rgb / 255).astype(np.float32), (w, h))
    assert size == (w, h)
    assert offset == ((1024-w)//2, 0)
    np.testing.assert_array_equal(actual, expected)


def test_restore_resizes_float_prediction_before_uint8_quantization():
    size, offset = (561, 1024), (231, 0)
    pred = np.random.default_rng(4).random((1, 1, 1024, 1024), dtype=np.float32)
    actual = worker.restore_alpha(pred, size, offset, (17, 31))
    cropped = pred[0, 0, :, 231:231+561]
    expected = np.uint8(cv2.resize(cropped, (17, 31)) * 255)
    np.testing.assert_array_equal(actual, expected)


@pytest.mark.parametrize("bad", [np.zeros((1, 1, 32, 32)),
                                 np.full((1, 1, 1024, 1024), np.nan)])
def test_restore_rejects_invalid_prediction(bad):
    with pytest.raises(RuntimeError, match="prediction"):
        worker.restore_alpha(bad, (1024, 1024), (0, 0), (16, 16))
