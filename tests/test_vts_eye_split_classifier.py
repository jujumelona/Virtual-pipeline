"""Upstream PSD2Live expects white, iris and upper lash as distinct layers.

A generic See-through 'eyes' mask is an entire eye region, NOT an iris.
"""
import pytest

from tools.vts_psd2live_names import normalize_layer_names


@pytest.mark.parametrize("name", ["eye", "eyes", "eye.left",
                                 "eye.right", "eye.sam.eyes"])
def test_unsplit_eye_must_not_become_iris(name):
    normalized, report = normalize_layer_names([{"name": name}])
    assert report["records"][0]["semantic_tag"] is None
    assert normalized[0]["name"] == name


def test_generic_sam_eyes_must_not_become_iris():
    normalized, report = normalize_layer_names(
        [{"name": "unknown.raw", "sam_label": "eyes"}])
    assert report["records"][0]["semantic_tag"] is None


@pytest.mark.parametrize(
    "name,expected",
    [
        ("eye.left.white", "eyewhite"),
        ("eye.right.iris", "irides"),
        ("eye.left.upper.lash", "eyelash"),
        ("eye.right.pupil", "irides"),
        ("eyelash-l", "eyelash"),
        ("irides-r", "irides"),
    ],
)
def test_fine_eye_names_remain_recognized(name, expected):
    _, report = normalize_layer_names([{"name": name}])
    assert report["records"][0]["semantic_tag"] == expected


def test_unknown_eye_does_not_pass_from_generic_sam_label():
    _, report = normalize_layer_names(
        [{"name": "raw_mystery", "sam_label": "eyes"}])
    assert report["unclassified_count"] == 1
