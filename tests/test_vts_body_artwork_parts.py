"""Regression coverage for independent BODY anatomy and hidden neck bridging.

Tests use synthetic PNG artwork. A 14/27-part generator must not be rejected
simply because valid anatomical names have compound tokens.
"""
from __future__ import annotations

import io
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pytest
from PIL import Image, ImageDraw

from tools.vts_multiview_runtime import validate_artwork_parts


CANVAS = (256, 256)


def rectangle(part_id: str, box: tuple[int, int, int, int]):
    image = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    ImageDraw.Draw(image).rectangle(box, fill=(244, 195, 175, 255))
    return {"id": part_id, "image": image, "left": 0, "top": 0}


def sample_parts():
    # The visible face, jaw, neck and torso do not overlap. The authored
    # concealed underpaint bridges them, as in MATTE_CLAY_FINAL.
    parts = [
        rectangle("skin_base", (4, 190, 8, 198)),
        rectangle("scalp", (42, 6, 88, 17)),
        rectangle("face", (40, 18, 90, 61)),
        rectangle("jaw", (44, 63, 85, 76)),
        rectangle("neck", (55, 78, 73, 102)),
        rectangle("torso", (22, 105, 114, 188)),
        rectangle("nose", (60, 40, 65, 42)),
        rectangle("mouth_neutral_open", (56, 54, 70, 58)),
    ]
    for side in ("L", "R"):
        parts += [
            rectangle("shoulder_" + side, (15 if side == "L" else 111, 105, 22 if side == "L" else 118, 118)),
            rectangle("upper_arm_" + side, (7 if side == "L" else 120, 119, 18 if side == "L" else 130, 153)),
            rectangle("forearm_" + side, (7 if side == "L" else 120, 155, 18 if side == "L" else 130, 177)),
            rectangle("hand_" + side, (8 if side == "L" else 121, 180, 20 if side == "L" else 131, 201)),
            rectangle("eye_" + side + "_iris", (43 if side == "L" else 75, 32, 48 if side == "L" else 80, 36)),
            rectangle("eye_" + side + "_whites", (43 if side == "L" else 75, 30, 49 if side == "L" else 81, 37)),
            rectangle("eye_" + side + "_upper_lash", (43 if side == "L" else 75, 29, 49 if side == "L" else 81, 30)),
        ]
    return parts


def hidden_bridge():
    return [rectangle("hidden_neck_underpaint", (49, 70, 79, 114))]


def test_valid_body_anatomy_and_hidden_seam_bridge():
    result = validate_artwork_parts(sample_parts(), CANVAS, asset="body",
                                    underpaint_parts=hidden_bridge())
    assert result["status"] == "SEMANTIC_SOURCE_PREFLIGHT_PASS"
    assert result["neck"]["status"] == "EXPLICIT_HIDDEN_NECK_BRIDGE_PRESENT_RIG_VISUAL_REVIEW_REQUIRED"
    assert result["neck"]["hidden_jaw_overlap_pixels"] >= 16
    assert result["neck"]["hidden_neck_overlap_pixels"] >= 16
    assert result["neck"]["hidden_torso_overlap_pixels"] >= 16
    assert result["visual_quality_verified"] is False


def test_no_hidden_bridge_must_still_be_rejected():
    with pytest.raises(ValueError, match="NECK_BODY_UNDERPAINT_MISSING"):
        validate_artwork_parts(sample_parts(), CANVAS, asset="body")


def test_hidden_layer_without_actual_joint_overlap_is_rejected():
    fake = [rectangle("hidden_neck_underpaint", (2, 2, 10, 10))]
    with pytest.raises(RuntimeError, match="ARTWORK_HIDDEN_NECK_BRIDGE_INCOMPLETE"):
        validate_artwork_parts(sample_parts(), CANVAS, asset="body",
                               underpaint_parts=fake)


@pytest.mark.parametrize("bad_part", ["outfit_collar", "hair_back", "accessory_pendant",
                                     "upper_outfit_l", "shirt_l"])
def test_cross_asset_contamination_stays_rejected(bad_part):
    parts = sample_parts() + [rectangle(bad_part, (200, 200, 210, 210))]
    with pytest.raises(RuntimeError, match="ARTWORK_PART_CROSS_ASSET_CONTAMINATION"):
        validate_artwork_parts(parts, CANVAS, asset="body",
                               underpaint_parts=hidden_bridge())


def test_importer_preserves_hidden_underpaint_in_real_psd(tmp_path: Path):
    pytest.importorskip("psd_tools")
    from tools.vts_ai_pack_import import inspect_large_ai_pack, prepare_large_ai_pack
    source = tmp_path / "source.zip"
    # Minimal valid image-only package; no upstream metadata is trusted.
    master = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    first = rectangle("face", (30, 30, 70, 80))["image"]
    second = rectangle("neck", (45, 80, 58, 111))["image"]
    master.alpha_composite(first)
    master.alpha_composite(second)
    hidden = rectangle("hidden_neck_underpaint", (44, 76, 60, 120))["image"]
    def encode(im):
        out = io.BytesIO()
        im.save(out, format="PNG")
        return out.getvalue()
    with ZipFile(source, "w") as z:
        z.writestr("outputs/master.png", encode(master))
        z.writestr("isolated_parts/face.png", encode(first))
        z.writestr("isolated_parts/neck.png", encode(second))
        z.writestr("underpaint_parts/hidden_neck_underpaint.png", encode(hidden))
        z.writestr("layer_order.txt",
                   "isolated_parts/face.png\nisolated_parts/neck.png\n")
    inspected = inspect_large_ai_pack(source, edition="free")
    assert [x["id"] for x in inspected["underpaint_parts"]] == ["hidden_neck_underpaint"]
    output = prepare_large_ai_pack(source, tmp_path / "converted", edition="free")
    from psd_tools import PSDImage
    psd = PSDImage.open(output["psd"])
    layers = [x for x in psd.descendants() if not x.is_group()]
    assert [x.name for x in layers] == ["face", "neck", "hidden_neck_underpaint"]
    assert not layers[-1].is_visible()
    assert output["metadata"]["part_count"] == 2
    assert output["metadata"]["underpaint_part_count"] == 1
