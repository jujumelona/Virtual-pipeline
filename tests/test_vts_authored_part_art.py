"""Tests for native Colab consumption of independently image-AI-drawn PNGs."""
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from PIL import Image, ImageDraw
import pytest

from tools.vts_authored_part_art import (
    assemble_authored_parts, has_authored_parts,
)


def rgba(box, color, size=(128, 128)):
    image = Image.new("RGBA", size)
    ImageDraw.Draw(image).rectangle(box, fill=color)
    return image


def png_bytes(im):
    buf = BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def make_pack(tmp_path, *, bad_order=None, opaque=False, size=(128, 128)):
    face = rgba((24, 12, 106, 104), (238, 180, 170, 255), size)
    closed = rgba((48, 78, 73, 82), (74, 26, 35, 255), size)
    opened = rgba((44, 77, 77, 91), (58, 20, 35, 255), size)
    tooth = rgba((51, 80, 70, 83), (246, 240, 239, 255), size)
    tongue = rgba((52, 86, 71, 89), (214, 87, 121, 255), size)
    order = [
        "part_art/mouth.close.png",
        "part_art/mouth.tooth.t.png",
        "part_art/mouth.tongue.png",
        "part_art/mouth.open.png",
        "part_art/face.png",
    ]
    assets = dict(zip(order, [closed, tooth, tongue, opened, face]))
    master = face.copy()
    master.alpha_composite(closed)
    mp = tmp_path / "master.png"
    master.save(mp)
    archive_path = tmp_path / "drawing.zip"
    with ZipFile(archive_path, "w") as z:
        z.writestr("outputs/master.png", png_bytes(master))
        z.writestr("part_art/_order.txt", "\n".join(order if bad_order is None else bad_order))
        for key, im in assets.items():
            if opaque and key.endswith("mouth.open.png"):
                im = Image.new("RGBA", im.size, "white")
            z.writestr(key, png_bytes(im))
    return archive_path, mp


def test_multiple_single_part_drawings_assembled_without_diffusion(tmp_path, monkeypatch):
    z, master = make_pack(tmp_path)
    captured = {}

    def fake_psd_writer(layers, target, *, free, compact_for_atlas):
        captured["names"] = [x["name"] for x in layers]
        captured["free"] = free
        captured["compact"] = compact_for_atlas
        target.write_bytes(b"test PSD writer stub only")
        return 1

    from tools import vts_artwork_export
    monkeypatch.setattr(vts_artwork_export, "_write_psd", fake_psd_writer)
    assert has_authored_parts(z)
    report = assemble_authored_parts(z, master, tmp_path / "out",
                                    asset="body", edition="free")
    assert captured["names"] == ["mouth.close", "mouth.tooth.t",
                                 "mouth.tongue", "mouth.open", "face"]
    assert captured["free"] and captured["compact"]
    assert report["neutral_exact_same_as_master"]
    assert set(report["neutral_hidden_alternate_parts"]) == {
        "mouth.open", "mouth.tooth.t", "mouth.tongue"}
    assert report["independent_rgba_png_count"] == 5
    assert not report["native_rig_verified"]


def test_missing_part_name_refuses_fake_merge(tmp_path):
    z, master = make_pack(tmp_path, bad_order=["part_art/mouth.close.png",
                                             "part_art/face.png"])
    with pytest.raises(ValueError, match="AUTHORED_PART_ORDER_MISMATCH"):
        has_authored_parts(z)


def test_false_transparent_white_background_refused(tmp_path):
    z, master = make_pack(tmp_path, opaque=True)
    with pytest.raises(ValueError, match="AUTHORED_PART_NOT_TRANSPARENT_OR_EMPTY"):
        assemble_authored_parts(z, master, tmp_path / "out",
                                asset="body", edition="free")


def test_actual_native_psd_roundtrip_maintains_five_original_part_names(tmp_path):
    """Real psd-tools codec, without mocking PSD writing or file decoding."""
    from tools.vts_production import psd_to_registered_rgba
    z, master = make_pack(tmp_path, size=(320, 320))
    report = assemble_authored_parts(z, master, tmp_path / "real_psd",
                                    asset="body", edition="free")
    psd_path = Path(report["psd"])
    assert psd_path.read_bytes().startswith(b"8BPS")
    from psd_tools import PSDImage
    actual = PSDImage.open(psd_path)
    assert actual.size == (320, 320)
    leaves = [x for x in actual.descendants() if not x.is_group()]
    assert len(leaves) == 5
    _, registered, count = psd_to_registered_rgba(
        psd_path, tmp_path / "registered", artmesh_max=100)
    assert count == 5
    with ZipFile(registered) as archive:
        names = archive.namelist()
    assert any(n.startswith("mouth.close.") for n in names)
    assert any(n.startswith("mouth.open.") for n in names)
    assert any(n.startswith("mouth.tooth.") for n in names)
    assert any(n.startswith("mouth.tongue.") for n in names)


def test_rgb_only_damage_is_rejected_even_when_alpha_is_identical(tmp_path):
    """Previous RGBA difference.getbbox() missed RGB-only color damage."""
    z, master = make_pack(tmp_path)
    with Image.open(master) as im:
        changed = im.copy()
    changed.putpixel((55, 80), (0, 255, 30, 255))
    changed.save(master)
    with pytest.raises(ValueError, match="AUTHORED_NEUTRAL_MASTER_RECONSTRUCTION_MISMATCH"):
        assemble_authored_parts(z, master, tmp_path / "color_fail",
                                asset="body", edition="free")


def test_missing_eye_and_limbs_rejected_in_production_gate(tmp_path):
    z, master = make_pack(tmp_path)
    with pytest.raises(ValueError, match="AUTHORED_REQUIRED_PART_ROLES_MISSING"):
        assemble_authored_parts(z, master, tmp_path / "role_fail",
                                asset="body", edition="free",
                                enforce_required_parts=True)


def test_wrong_front_to_back_order_rejected_by_rendering(tmp_path):
    z, master = make_pack(tmp_path)
    with ZipFile(z) as archive:
        values = {i.filename: archive.read(i.filename)
                  for i in archive.infolist()}
    order = values["part_art/_order.txt"].decode().splitlines()
    order = [x for x in order if x != "part_art/face.png"]
    order.insert(0, "part_art/face.png")  # face hides the mouth entirely
    values["part_art/_order.txt"] = "\\n".join(order).encode()
    new_zip = tmp_path / "bad_zorder.zip"
    with ZipFile(new_zip, "w") as output:
        for name, value in values.items():
            output.writestr(name, value)
    with pytest.raises(ValueError, match="AUTHORED_NEUTRAL_MASTER_RECONSTRUCTION_MISMATCH"):
        assemble_authored_parts(new_zip, master, tmp_path / "z_fail",
                                asset="body", edition="free")


def test_artwork_authoring_contract_requires_per_part_and_template():
    from tools.image_ai_source_only_contract import source_contract
    for mode in ("live2d_bust_up", "live2d_upper", "live2d_full",
                 "inochi2d_upper", "inochi2d_full"):
        for asset in ("body", "hair", "outfit", "accessory"):
            contract = source_contract(mode, asset)
            assert "ONE_PART_PER_GENERATION_V1" in contract
            assert "part_art/_order.txt" in contract
            assert "정확히 한 파츠" in contract
            assert "템플릿" in contract
            assert "See-through" in contract or "Colab" in contract
