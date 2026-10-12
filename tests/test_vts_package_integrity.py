"""CPU regression tests for the delivered Live2D artwork ZIP bytes."""
import json
from io import BytesIO
from zipfile import ZipFile

import pytest
from PIL import Image

from tools.vts_artwork_export import build_artwork_package
from tools.vts_package_integrity import verify_artwork_package


def _sample(tmp_path, edition="free", asset_kind=None):
    source = tmp_path / "source.zip"
    with ZipFile(source, "w") as archive:
        for index in range(2):
            rgba = Image.new("RGBA", (256, 384), (0, 0, 0, 0))
            rgba.paste((150, 100, 200, 255), (20 + index * 30, 30, 140, 200))
            buffer = BytesIO()
            rgba.save(buffer, "PNG")
            archive.writestr(f"hair.front.{index:03d}.png", buffer.getvalue())
    return build_artwork_package(source, tmp_path / "out", edition=edition,
                                 scope="upper", asset_kind=asset_kind)


def _tamper(source, target, replacement, output):
    with ZipFile(source) as original, ZipFile(output, "w") as altered:
        for member in original.namelist():
            altered.writestr(member, replacement if member == target else original.read(member))


def test_package_integrity_detects_modified_alpha_mask(tmp_path):
    result = _sample(tmp_path)
    assert result["archive_verification"]["status"] == "PASS"
    assert result["archive_verification"]["verified_rgba_mask_pairs"] == 2
    with ZipFile(result["package"]) as archive:
        manifest = json.loads(archive.read("metadata/layer_manifest.json"))
    target = manifest["layers"][0]["alpha_mask_png"]
    buf = BytesIO()
    Image.new("L", (256, 384), 0).save(buf, "PNG")
    tampered = tmp_path / "bad_mask.zip"
    _tamper(result["package"], target, buf.getvalue(), tampered)
    with pytest.raises(ValueError, match="mask SHA256 mismatch"):
        verify_artwork_package(tampered)


def test_package_integrity_detects_modified_rgba(tmp_path):
    result = _sample(tmp_path)
    with ZipFile(result["package"]) as archive:
        manifest = json.loads(archive.read("metadata/layer_manifest.json"))
    target = manifest["layers"][0]["rgba_png"]
    buf = BytesIO()
    Image.new("RGBA", (256, 384), (50, 50, 50, 255)).save(buf, "PNG")
    tampered = tmp_path / "bad_rgba.zip"
    _tamper(result["package"], target, buf.getvalue(), tampered)
    with pytest.raises(ValueError, match="RGBA SHA256 mismatch"):
        verify_artwork_package(tampered)


def test_package_integrity_detects_corrupted_psd_header(tmp_path):
    result = _sample(tmp_path)
    tampered = tmp_path / "bad_psd.zip"
    _tamper(result["package"], "avatar.psd", b"not a PSD", tampered)
    with pytest.raises(ValueError, match="PSD header"):
        verify_artwork_package(tampered)


def test_package_integrity_pro_independent_asset(tmp_path):
    result = _sample(tmp_path, edition="pro", asset_kind="hair")
    assert result["archive_verification"]["verified_rgba_mask_pairs"] == 2
    with ZipFile(result["package"]) as archive:
        assert "hair.psd" in archive.namelist()
        assert "avatar.psd" not in archive.namelist()
