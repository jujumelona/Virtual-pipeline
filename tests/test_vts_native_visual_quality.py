"""Executable regression for the real problems observed in a broken Live2D MOC3."""
from __future__ import annotations

import io
import json
from zipfile import ZipFile

from PIL import Image

from tools.vts_native_visual_quality import review_psd2live_export


def _png(y1, y2):
    image = Image.new("RGBA", (256, 384), (0, 0, 0, 0))
    for y in range(y1, y2):
        for x in range(64, 128):
            image.putpixel((x, y), (80, 120, 140, 255))
    b = io.BytesIO()
    image.save(b, "PNG")
    return b.getvalue()


def test_real_source_seam_gap_and_synthetic_lip_lines_are_reported(tmp_path):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "avatar.psd2live.json").write_text(
        json.dumps({
            "faceRig": {"angleX": [-45, 0, 45]},
            "layers": [
                {"source": "mouth_0017"},
                {"source": "mouth_0017 / Upper lip outline"},
                {"source": "mouth_0017 / Lower lip outline"},
            ],
        }), encoding="utf-8")
    source = tmp_path / "source.zip"
    with ZipFile(source, "w") as archive:
        archive.writestr("layers_png/0010_neck_0001.png", _png(110, 190))
        archive.writestr("layers_png/0020_topwear_0002.png", _png(190, 260))
        archive.writestr("layers_png/0000_face_0000.png", _png(85, 140))
    report = review_psd2live_export(model_dir, source)
    assert report["synthetic_extra_mouth_outline_count"] == 2
    assert report["head_yaw_keyforms"] == [-45, 0, 45]
    assert report["source_overlap"]["neck_body_overlap_pixels"] == 0
    assert report["source_overlap"]["face_neck_overlap_pixels"] > 0
    assert any("NECK_BODY_UNDERPAINT_ABSENT" in text for text in report["warnings"])
    assert any("FULL_SIDE_PROFILE_NOT_MODELLED" in text for text in report["warnings"])
    assert report["visual_quality_verified"] is False
    assert report["true_side_profile_keyforms_verified"] is False


def test_no_real_psd2live_diagnostics_never_claims_anime_quality(tmp_path):
    report = review_psd2live_export(tmp_path)
    assert report["visual_quality_verified"] is False
    assert "source_overlap" not in report
    assert "PSD2LIVE_DEBUG_JSON_NOT_AVAILABLE" in report["warnings"]


def test_preflight_refuses_zero_underpaint_before_native_compile():
    from tools.vts_native_visual_quality import require_live2d_body_underpaint
    from PIL import Image
    import pytest
    neck = Image.new("RGBA", (256, 384), (0, 0, 0, 0))
    torso = Image.new("RGBA", (256, 384), (0, 0, 0, 0))
    for y in range(50, 170):
        for x in range(90, 140):
            neck.putpixel((x, y), (160, 120, 100, 255))
    for y in range(170, 310):
        for x in range(90, 140):
            torso.putpixel((x, y), (160, 120, 100, 255))
    parts = [
        {"id": "neck", "image": neck, "left": 0, "top": 0},
        {"id": "torso", "image": torso, "left": 0, "top": 0},
    ]
    with pytest.raises(ValueError, match="NECK_BODY_UNDERPAINT_MISSING"):
        require_live2d_body_underpaint(parts, (256, 384))
    for y in range(150, 170):
        for x in range(90, 140):
            torso.putpixel((x, y), (160, 120, 100, 255))
    report = require_live2d_body_underpaint(parts, (256, 384))
    assert report["neck_body_overlap_pixels"] == 20 * 50
    assert report["editor_review_required"] is True
