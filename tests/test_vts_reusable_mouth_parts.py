"""Evidence that high-reuse oral assets are actually three independent PNGs.

Mouth graphics are source art supplements, NOT verified native keyforms.
"""
from io import BytesIO

from PIL import Image, ImageDraw

from tools.vts_reusable_mouth_parts import generate_reusable_mouth_assets


def part(name, box, canvas=(320, 320)):
    img = Image.new("RGBA", canvas, (0, 0, 0, 0))
    ImageDraw.Draw(img).rectangle(box, fill=(48, 28, 40, 255))
    return {"name": name, "image": img, "depth": 0}


def base():
    return [part("face", (88, 35, 230, 220)),
            part("mouth.001", (134, 173, 187, 177))]


def test_mouth_parts_are_separate_transparent_registered_png():
    layers = base()
    before = [x["image"].tobytes() for x in layers]
    items, report = generate_reusable_mouth_assets(layers, (320, 320))
    assert report["status"] == "generated"
    assert [x[0] for x in items] == [
        "reusable_parts/mouth/mouth_open.png",
        "reusable_parts/mouth/tooth_t.png",
        "reusable_parts/mouth/tongue.png",
    ]
    alpha_boxes = []
    for path, data in items:
        assert data[:4] == bytes((137, 80, 78, 71))
        with Image.open(BytesIO(data)) as png:
            assert png.mode == "RGBA"
            assert png.size == (320, 320)
            alpha_boxes.append(png.getchannel("A").getbbox())
    assert all(box is not None for box in alpha_boxes)
    assert len({x[1] for x in items}) == 3
    assert [x["image"].tobytes() for x in layers] == before
    assert report["original_visible_artwork_unchanged"]
    assert not report["native_psd2live_keyform_binding_verified"]


def test_existing_authored_open_mouth_never_overlaid():
    layers = base() + [part("mouth.open", (132, 174, 189, 199))]
    entries, report = generate_reusable_mouth_assets(layers, (320, 320))
    assert entries == []
    assert report["reason"] == "existing_open_mouth_or_internals_preserved"


def test_missing_mouth_source_never_guessed():
    entries, report = generate_reusable_mouth_assets(base()[:1], (320, 320))
    assert not entries
    assert report["reason"] == "no_unique_closed_mouth_layer"


def test_non_closed_geometry_is_not_covered_by_heuristic():
    data = [base()[0], part("mouth.001", (134, 171, 187, 207))]
    entries, report = generate_reusable_mouth_assets(data, (320, 320))
    assert entries == []
    assert report["reason"] == "closed_mouth_geometry_ambiguous"


def test_mouth_outside_face_not_generated():
    data = [base()[0], part("mouth.001", (134, 258, 187, 262))]
    entries, report = generate_reusable_mouth_assets(data, (320, 320))
    assert entries == []
    assert report["reason"] == "mouth_outside_lower_face"


def test_explicit_tooth_tongue_parts_preserved():
    for label in ("mouth.tongue", "tooth-t", "mouth.tooth.upper", "mouth.inside"):
        entries, report = generate_reusable_mouth_assets(
            base() + [part(label, (135, 179, 185, 191))], (320, 320))
        assert entries == []
        assert report["reason"] == "existing_open_mouth_or_internals_preserved"
