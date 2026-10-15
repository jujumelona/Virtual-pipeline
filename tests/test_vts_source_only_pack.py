"""Byte-level contract for image-AI source-only ZIP → See-through handoff."""
from __future__ import annotations

import io
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

import pytest
from PIL import Image, ImageDraw

from tools.vts_source_only_pack import is_source_only_zip, prepare_source_only_2d
from tools.vts_multiview_runtime import VIEW_SETS


def png(color, *, size=(512, 512)):
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(image).rectangle((100, 70, 410, 475), fill=(*color, 255))
    file = io.BytesIO()
    image.save(file, format="PNG")
    return file.getvalue()


def write_art_zip(path: Path, asset: str):
    with ZipFile(path, "w", ZIP_DEFLATED) as z:
        z.writestr("outputs/master.png", png((200, 160, 140)))
        for i, stem in enumerate(VIEW_SETS[asset]):
            z.writestr("reference_views/" + stem + ".png",
                       png((i * 24 % 255, (i * 43 + 70) % 255,
                            (i * 67 + 30) % 255)))
    return path


@pytest.mark.parametrize("asset", ("body", "hair", "outfit", "accessory"))
def test_png_master_and_angles_do_not_need_pre_split_parts(tmp_path, asset):
    source = write_art_zip(tmp_path / "source.zip", asset)
    assert is_source_only_zip(source)
    info = prepare_source_only_2d(source, tmp_path / "art", asset=asset)
    assert Path(info["master"]).read_bytes()
    assert info["parts"]["count"] == 0
    assert info["parts"]["status"] == "SOURCE_ONLY_NEEDS_SEETHROUGH"
    assert info["views"]["valid"] is True
    assert info["multiview_reference_applied_to_native_keyforms"] is False
    assert len(info["views"]["observed"]) == len(VIEW_SETS[asset])


def test_source_only_rejects_fake_mask_or_psd_instead_of_pretending_success(tmp_path):
    path = write_art_zip(tmp_path / "bad.zip", "body")
    with ZipFile(path, "a") as z:
        z.writestr("isolated_parts/face.png", png((50, 100, 120)))
    with pytest.raises(ValueError, match="SOURCE_ONLY_MUST_NOT_SUPPLY_SPLIT_PARTS"):
        prepare_source_only_2d(path, tmp_path / "out", asset="body")


def test_authored_legacy_part_pack_uses_original_path(tmp_path):
    source = tmp_path / "legacy.zip"
    with ZipFile(source, "w") as z:
        z.writestr("outputs/master.png", png((120, 90, 80)))
        z.writestr("layer_order.txt", "isolated_parts/face.png\n")
        z.writestr("isolated_parts/face.png", png((120, 90, 80)))
    assert not is_source_only_zip(source)
