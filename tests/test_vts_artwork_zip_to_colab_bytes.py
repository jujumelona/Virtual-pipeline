"""Generate actual artwork-result ZIP byte fixtures in exactly the published format.

No generated PSD is assumed correct from a manifest. Feed identical pixels
through the real importer, multi-view validator and PSD writer. These tests
prove I/O contract compatibility, not artistic quality or Cubism motion.
"""
from __future__ import annotations
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

import pytest
from PIL import Image, ImageDraw

from tools.vts_ai_pack_import import prepare_large_ai_pack
from tools.vts_multiview_runtime import VIEW_SETS, prepare_multiview_input

CANVAS = (320, 320)
BODY = [
    ("torso_skin", (100, 145, 220, 310)),
    ("arm_canvas_left_upper", (64, 164, 116, 266)),
    ("arm_canvas_right_upper", (204, 164, 254, 266)),
    ("hand_canvas_left", (50, 249, 118, 304)),
    ("hand_canvas_right", (207, 249, 270, 304)),
    ("neck_underpaint", (145, 114, 185, 181)),
    ("head_skin_and_jaw", (102, 36, 220, 159)),
    ("eye_canvas_left_iris", (129, 95, 145, 111)),
    ("eye_canvas_right_iris", (177, 95, 193, 111)),
    ("removable_neutral_modesty_band", (118, 171, 204, 200)),
]
OTHERS = {
    "hair": [
        ("hair_back_layer", (102, 48, 213, 198)),
        ("hair_front_layer", (119, 48, 202, 145)),
    ],
    "outfit": [
        ("outfit_front_panel", (120, 147, 207, 300)),
        ("outfit_sleeve_left", (75, 168, 127, 261)),
    ],
    "accessory": [
        ("accessory_base", (135, 20, 202, 68)),
        ("accessory_ornament", (147, 24, 182, 52)),
    ],
}

def png(image):
    stream = BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()

def make_result_zip(path: Path, asset: str):
    """No manifest.json, exact path identity and the same neutral composite."""
    parts = BODY if asset == "body" else OTHERS[asset]
    master = Image.new("RGBA", CANVAS)
    layers = []
    for i, (id_, box) in enumerate(parts):
        part = Image.new("RGBA", CANVAS)
        color = (115 + (i * 17) % 90, 105 + (i * 23) % 90, 125 + (i * 11) % 90, 255)
        ImageDraw.Draw(part).rectangle(box, fill=color)
        master.alpha_composite(part)
        layers.append((id_, png(part)))
    with ZipFile(path, "w", ZIP_DEFLATED) as z:
        z.writestr("outputs/master.png", png(master))
        z.writestr("layer_order.txt", "".join(
            "isolated_parts/" + name + ".png\n" for name, _ in layers))
        for name, bytes_ in layers:
            z.writestr("isolated_parts/" + name + ".png", bytes_)
        for i, name in enumerate(VIEW_SETS[asset]):
            sample = Image.new("RGBA", CANVAS,
                               ((29+i*19)%255, (61+i*31)%255,
                                (113+i*37)%255, 255))
            z.writestr("reference_views/" + name + ".png", png(sample))

@pytest.mark.parametrize("asset", ("body", "hair", "outfit", "accessory"))
def test_real_artwork_zip_bytes_pass_real_colab_consumer_and_psd_writer(tmp_path, asset):
    source = tmp_path / (asset + "_artwork.zip")
    make_result_zip(source, asset)
    source_qa = prepare_multiview_input(
        source, tmp_path / "source_review", edition="free",
        asset=asset, require_views=True)
    assert source_qa["views"]["valid"]
    assert source_qa["views"]["reference_angles_used_as_rig_keyforms"] is False
    assert source_qa["parts"]["status"] == "SEMANTIC_SOURCE_PREFLIGHT_PASS"
    assert source_qa["neutral_composite"]["rgb_visible_mae"] == 0
    assert source_qa["neutral_composite"]["alpha_mae"] == 0
    package = prepare_large_ai_pack(source, tmp_path / "imported", edition="free")
    from psd_tools import PSDImage
    layered = PSDImage.open(package["psd"])
    assert layered.size == CANVAS
    assert package["metadata"]["skipped_see_through"] is True
    assert len([x for x in layered.descendants() if not x.is_group()]) == (
        len(BODY) if asset == "body" else len(OTHERS[asset]))
