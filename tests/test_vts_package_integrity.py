"""CPU regression tests for the delivered Live2D artwork ZIP bytes."""
import json
from io import BytesIO
from zipfile import ZipFile

import pytest
from PIL import Image

from tools.vts_artwork_export import build_artwork_package
from tools.vts_package_integrity import verify_artwork_package


def _sample(tmp_path, edition="free", asset_kind=None, color=(150, 100, 200)):
    tmp_path.mkdir(parents=True, exist_ok=True)
    source = tmp_path / "source.zip"
    with ZipFile(source, "w") as archive:
        for index in range(2):
            rgba = Image.new("RGBA", (256, 384), (0, 0, 0, 0))
            rgba.paste((*color, 255), (20 + index * 30, 30, 140, 200))
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


def test_package_integrity_rejects_header_only_psd(tmp_path):
    result = _sample(tmp_path)
    with ZipFile(result["package"]) as archive:
        header = archive.read("avatar.psd")[:26]
    tampered = tmp_path / "header_only.zip"
    _tamper(result["package"], "avatar.psd", header, tampered)
    with pytest.raises(ValueError, match="PSD cannot be parsed"):
        verify_artwork_package(tampered)


def test_package_integrity_rejects_different_valid_psd_same_canvas(tmp_path):
    original = _sample(tmp_path / "original")
    different = _sample(tmp_path / "different", color=(12, 208, 63))
    with ZipFile(different["package"]) as archive:
        replacement = archive.read("avatar.psd")
    tampered = tmp_path / "swapped_psd.zip"
    _tamper(original["package"], "avatar.psd", replacement, tampered)
    with pytest.raises(ValueError, match="PSD layer RGBA mismatch"):
        verify_artwork_package(tampered)


def test_package_integrity_verifies_real_psd_layers_for_pro(tmp_path):
    result = _sample(tmp_path, edition="pro", asset_kind="hair")
    report = verify_artwork_package(result["package"])
    assert report["psd_layers_verified"] == 2
    assert report["editor_import_verified"] is False



def test_package_integrity_detects_modified_composite_same_canvas(tmp_path):
    result = _sample(tmp_path)
    replacement = BytesIO()
    Image.new("RGBA", (256, 384), (1, 2, 3, 255)).save(replacement, "PNG")
    tampered = tmp_path / "modified_composite.zip"
    _tamper(result["package"], "preview/composite.png",
            replacement.getvalue(), tampered)
    with pytest.raises(ValueError, match="preview composite RGBA mismatch"):
        verify_artwork_package(tampered)


def test_final_handoff_requires_input_psd_and_comparison(tmp_path):
    result = _sample(tmp_path)
    with pytest.raises(ValueError, match="final handoff missing"):
        verify_artwork_package(result["package"], require_final_handoff=True)


def test_final_handoff_checks_appended_pro_reference(tmp_path):
    result = _sample(tmp_path, edition="pro", asset_kind="hair")
    with ZipFile(result["package"], "a") as archive:
        psd = archive.read("hair.psd")
        preview = archive.read("preview/composite.png")
        archive.writestr("source_psd/see_through_layers.psd", psd)
        archive.writestr("input_reference/source_avatar.png", preview)
        archive.writestr("input_reference/body_base.png", preview)
        archive.writestr("preview/input_vs_psd_comparison.png", preview)
        archive.writestr("preview/pro_body_asset_overlay.png", preview)
        archive.writestr("metadata/input_vs_psd_geometry.json",
                         json.dumps({"output_psd_canvas": [256, 384]}))
        archive.writestr("metadata/pro_reference_alignment.json",
                         json.dumps({"output_psd_canvas": [256, 384]}))
        archive.writestr("logs/psd_runtime/runtime.json", "{}")
    report = verify_artwork_package(
        result["package"], require_final_handoff=True, require_pro_reference=True)
    assert report["composite_pixels_verified"] is True
    assert report["final_handoff_verified"] is True
    assert report["pro_reference_files_verified"] is True


def test_final_handoff_rejects_misaligned_pro_reference_json(tmp_path):
    result = _sample(tmp_path, edition="pro", asset_kind="hair")
    with ZipFile(result["package"], "a") as archive:
        psd = archive.read("hair.psd")
        preview = archive.read("preview/composite.png")
        archive.writestr("source_psd/see_through_layers.psd", psd)
        archive.writestr("input_reference/source_avatar.png", preview)
        archive.writestr("input_reference/body_base.png", preview)
        archive.writestr("preview/input_vs_psd_comparison.png", preview)
        archive.writestr("preview/pro_body_asset_overlay.png", preview)
        archive.writestr("metadata/input_vs_psd_geometry.json",
                         json.dumps({"output_psd_canvas": [256, 384]}))
        archive.writestr("metadata/pro_reference_alignment.json",
                         json.dumps({"output_psd_canvas": [512, 384]}))
        archive.writestr("logs/psd_runtime/runtime.json", "{}")
    with pytest.raises(ValueError, match="PRO body alignment canvas mismatch"):
        verify_artwork_package(
            result["package"], require_final_handoff=True, require_pro_reference=True)
