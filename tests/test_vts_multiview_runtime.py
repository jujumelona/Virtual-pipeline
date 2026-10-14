"""CPU-only checks for actual artwork-source and native-backend handoff contracts.

These do not pretend to verify Cubism rendering or author quality.
"""
from __future__ import annotations

import io
from pathlib import Path
from zipfile import ZipFile

import pytest
from PIL import Image

from tools.vts_multiview_runtime import (
    VIEW_SETS, VIEWS_FOR_3D, _check_view_members,
    prepare_3d_turnaround_input, _safe_view_name,
)
from tools.vts_psd2live_names import normalize_layer_names


def _png(rgb):
    image = Image.new("RGBA", (256, 256), (*rgb, 255))
    data = io.BytesIO()
    image.save(data, format="PNG")
    return data.getvalue()


def test_art_views_validate_without_requiring_runtime_in_image_ai_zip(tmp_path):
    path = tmp_path / "input.zip"
    with ZipFile(path, "w") as archive:
        for i, name in enumerate(VIEW_SETS["body"]):
            archive.writestr("reference_views/" + name + ".png",
                             _png((i * 30, 40, 200 - i * 25)))
    report = _check_view_members(
        path, asset="body", output=tmp_path / "references", required=True)
    assert report["valid"]
    assert len(report["observed"]) == len(VIEW_SETS["body"])
    assert report["reference_angles_used_as_rig_keyforms"] is False
    assert not list((tmp_path / "references").glob("*.py"))


def test_missing_view_is_regeneration_not_false_pass(tmp_path):
    path = tmp_path / "missing.zip"
    with ZipFile(path, "w") as archive:
        archive.writestr("reference_views/head_three_quarter_L.png", _png((12, 13, 14)))
    with pytest.raises(RuntimeError, match="MULTIVIEW_ARTWORK_NEEDS_REGENERATION"):
        _check_view_members(path, asset="body", output=tmp_path / "references")


def test_3d_eight_way_turnaround_detects_duplicate_frames(tmp_path):
    path = tmp_path / "model.zip"
    with ZipFile(path, "w") as archive:
        for i, view in enumerate(VIEWS_FOR_3D):
            archive.writestr("views/body_" + view + ".png", _png((i * 18, 20, 70 + i)))
    report = prepare_3d_turnaround_input(path, tmp_path / "3d", asset="body")
    assert not report["missing"]
    assert report["diagonal_views_automatically_consumed_by_vrm_mesh"] is False

    wrong = tmp_path / "wrong.zip"
    with ZipFile(wrong, "w") as archive:
        for view in VIEWS_FOR_3D:
            archive.writestr("views/body_" + view + ".png", _png((1, 2, 3)))
    with pytest.raises(RuntimeError, match="3D_TURNAROUND_REGENERATION_REQUIRED"):
        prepare_3d_turnaround_input(wrong, tmp_path / "bad", asset="body")


def test_explicit_skin_and_second_pass_face_semantics_are_distinct():
    layers = [
        {"name": "body_torso", "sam_label": "face"},
        {"name": "torso", "sam_label": "face"},
        {"name": "arm_L", "sam_label": "topwear"},
        {"name": "face.pass2.01", "sam_label": "mouth"},
    ]
    _, evidence = normalize_layer_names(layers)
    tags = [item["semantic_tag"] for item in evidence["records"]]
    assert tags == ["topwear", "topwear", "handwear", "mouth"]
    assert evidence["records"][0]["evidence"] == "author_declared_anatomy_or_asset"
