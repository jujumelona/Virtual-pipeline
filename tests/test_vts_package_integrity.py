"""CPU regression tests for the delivered Live2D artwork ZIP bytes."""
import json
from io import BytesIO
from zipfile import ZipFile

import pytest
from PIL import Image

from tools.vts_artwork_export import build_artwork_package
from tools.vts_package_integrity import (verify_artwork_package,
                                         render_input_vs_psd_comparison)


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


def _comparison_png(preview_bytes):
    with Image.open(BytesIO(preview_bytes)) as source:
        output = BytesIO()
        render_input_vs_psd_comparison(source, source).save(output, format="PNG")
        return output.getvalue()


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
        archive.writestr("preview/input_vs_psd_comparison.png", _comparison_png(preview))
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
        archive.writestr("preview/input_vs_psd_comparison.png", _comparison_png(preview))
        archive.writestr("preview/pro_body_asset_overlay.png", preview)
        archive.writestr("metadata/input_vs_psd_geometry.json",
                         json.dumps({"output_psd_canvas": [256, 384]}))
        archive.writestr("metadata/pro_reference_alignment.json",
                         json.dumps({"output_psd_canvas": [512, 384]}))
        archive.writestr("logs/psd_runtime/runtime.json", "{}")
    with pytest.raises(ValueError, match="PRO body alignment canvas mismatch"):
        verify_artwork_package(
            result["package"], require_final_handoff=True, require_pro_reference=True)


def test_final_handoff_rejects_pro_reference_image_with_different_canvas(tmp_path):
    """Actual PNG dimensions must match PSD canvas, not just claimed metadata."""
    result = _sample(tmp_path, edition="pro", asset_kind="hair")
    with ZipFile(result["package"], "a") as archive:
        psd = archive.read("hair.psd")
        preview = archive.read("preview/composite.png")
        archive.writestr("source_psd/see_through_layers.psd", psd)
        archive.writestr("input_reference/source_avatar.png", preview)
        archive.writestr("input_reference/body_base.png", preview)
        archive.writestr("preview/input_vs_psd_comparison.png", _comparison_png(preview))
        archive.writestr("preview/pro_body_asset_overlay.png", preview)
        archive.writestr("metadata/input_vs_psd_geometry.json",
                         json.dumps({"source_canvas": [256, 384],
                                     "output_psd_canvas": [256, 384]}))
        archive.writestr("metadata/pro_reference_alignment.json",
                         json.dumps({"output_psd_canvas": [256, 384],
                                     "input_size": [256, 384]}))
        archive.writestr("logs/psd_runtime/runtime.json", "{}")
    assert verify_artwork_package(result["package"], require_final_handoff=True,
                                  require_pro_reference=True)["status"] == "PASS"

    incorrect = BytesIO()
    Image.new("RGBA", (320, 384), (20, 40, 60, 255)).save(incorrect, "PNG")
    changed = tmp_path / "wrong_body_canvas.zip"
    _tamper(result["package"], "input_reference/body_base.png",
            incorrect.getvalue(), changed)
    with pytest.raises(ValueError, match="PRO body reference image canvas mismatch"):
        verify_artwork_package(changed, require_final_handoff=True,
                               require_pro_reference=True)

    changed_geometry = tmp_path / "wrong_source_geometry.zip"
    _tamper(result["package"], "metadata/input_vs_psd_geometry.json",
            json.dumps({"source_canvas": [320, 384],
                        "output_psd_canvas": [256, 384]}).encode(), changed_geometry)
    with pytest.raises(ValueError, match="source image canvas differs"):
        verify_artwork_package(changed_geometry, require_final_handoff=True,
                               require_pro_reference=True)


def _append_final_handoff_for_regression(package, *, pro=False):
    with ZipFile(package, "a") as archive:
        psd_name = "hair.psd" if pro else "avatar.psd"
        source_psd = archive.read(psd_name)
        preview = archive.read("preview/composite.png")
        archive.writestr("source_psd/see_through_layers.psd", source_psd)
        archive.writestr("input_reference/source_avatar.png", preview)
        archive.writestr("preview/input_vs_psd_comparison.png", _comparison_png(preview))
        archive.writestr("metadata/input_vs_psd_geometry.json",
                         json.dumps({"source_canvas": [256, 384],
                                     "output_psd_canvas": [256, 384]}))
        archive.writestr("logs/psd_runtime/runtime.json", "{}")
        if pro:
            archive.writestr("input_reference/body_base.png", preview)
            archive.writestr("preview/pro_body_asset_overlay.png", preview)
            archive.writestr("metadata/pro_reference_alignment.json",
                             json.dumps({"output_psd_canvas": [256, 384],
                                         "input_size": [256, 384]}))


def test_final_handoff_rejects_wrong_comparison_pixels_same_dimensions(tmp_path):
    result = _sample(tmp_path)
    _append_final_handoff_for_regression(result["package"])
    assert verify_artwork_package(
        result["package"], require_final_handoff=True)["status"] == "PASS"
    wrong = BytesIO()
    Image.new("RGB", (1440, 770), (10, 20, 30)).save(wrong, format="PNG")
    changed = tmp_path / "wrong_comparison_pixels.zip"
    _tamper(result["package"], "preview/input_vs_psd_comparison.png",
            wrong.getvalue(), changed)
    with pytest.raises(ValueError, match="comparison pixels mismatch"):
        verify_artwork_package(changed, require_final_handoff=True)


def test_final_handoff_rejects_stale_comparison_after_source_pixel_change(tmp_path):
    result = _sample(tmp_path)
    _append_final_handoff_for_regression(result["package"])
    with ZipFile(result["package"]) as archive:
        with Image.open(BytesIO(archive.read("input_reference/source_avatar.png"))) as im:
            source = im.convert("RGBA")
    source.putpixel((60, 60), (1, 2, 3, 255))
    changed_bytes = BytesIO()
    source.save(changed_bytes, format="PNG")
    changed = tmp_path / "stale_comparison.zip"
    _tamper(result["package"], "input_reference/source_avatar.png",
            changed_bytes.getvalue(), changed)
    with pytest.raises(ValueError, match="comparison pixels mismatch"):
        verify_artwork_package(changed, require_final_handoff=True)


def test_final_handoff_rejects_header_only_source_psd(tmp_path):
    result = _sample(tmp_path)
    _append_final_handoff_for_regression(result["package"])
    assert verify_artwork_package(
        result["package"], require_final_handoff=True)["status"] == "PASS"
    invalid = tmp_path / "invalid_source_psd.zip"
    with ZipFile(result["package"]) as archive:
        header = archive.read("source_psd/see_through_layers.psd")[:26]
    _tamper(result["package"], "source_psd/see_through_layers.psd",
            header, invalid)
    with pytest.raises(ValueError, match="source PSD cannot be parsed"):
        verify_artwork_package(invalid, require_final_handoff=True)


def test_final_handoff_rejects_wrong_pro_overlay_dimensions(tmp_path):
    result = _sample(tmp_path, edition="pro", asset_kind="hair")
    _append_final_handoff_for_regression(result["package"], pro=True)
    assert verify_artwork_package(
        result["package"], require_final_handoff=True,
        require_pro_reference=True)["status"] == "PASS"
    wrong = BytesIO()
    Image.new("RGBA", (320, 384), (50, 80, 90, 255)).save(wrong, "PNG")
    changed = tmp_path / "wrong_overlay_dimensions.zip"
    _tamper(result["package"], "preview/pro_body_asset_overlay.png",
            wrong.getvalue(), changed)
    with pytest.raises(ValueError, match="overlay preview size mismatch"):
        verify_artwork_package(
            changed, require_final_handoff=True, require_pro_reference=True)


def _rewrite_archive_member(source, target, value, destination):
    with ZipFile(source) as original, ZipFile(destination, "w") as altered:
        for member in original.namelist():
            if member == target and value is None:
                continue
            altered.writestr(
                member,
                json.dumps(value).encode("utf-8") if member == target
                else original.read(member))


@pytest.mark.parametrize("invalid", ["", "duplicate"])
def test_integrity_rejects_ambiguous_semantic_layers(tmp_path, invalid):
    result = _sample(tmp_path)
    with ZipFile(result["package"]) as z:
        manifest = json.loads(z.read("metadata/layer_manifest.json"))
    manifest["layers"][1]["semantic_name"] = (
        "" if invalid == "" else manifest["layers"][0]["semantic_name"])
    changed = tmp_path / "bad_semantic_names.zip"
    _rewrite_archive_member(result["package"], "metadata/layer_manifest.json",
                            manifest, changed)
    with pytest.raises(ValueError, match="duplicate or empty semantic"):
        verify_artwork_package(changed)


def test_handoff_rejects_mismatched_qwen_trace(tmp_path):
    result = _sample(tmp_path)
    _append_final_handoff_for_regression(result["package"])
    with ZipFile(result["package"]) as z:
        trace = json.loads(z.read("metadata/segmentation_trace.json"))
    trace.update({
        "attempts": [{"source_layer": "hair.front.000",
                      "accepted": True, "requested_count": 4}],
        "accepted_source_names": ["unrelated_layer"],
        "qwen_attempt_count": 1,
        "qwen_accepted_count": 1,
    })
    changed = tmp_path / "mismatched_qwen_trace.zip"
    _rewrite_archive_member(result["package"], "metadata/segmentation_trace.json",
                            trace, changed)
    with pytest.raises(ValueError, match="segmentation trace is inconsistent"):
        verify_artwork_package(changed, require_final_handoff=True)


@pytest.mark.parametrize("member,field,value,error", [
    ("metadata/integrity_report.json", "moc3_exported", True,
     "integrity report contradicts"),
    ("metadata/manual_rig_reference.json", "auto_rigged", True,
     "manual Editor reference contradicts"),
    ("metadata/texture_budget.json", "editor_packing_verified", True,
     "texture budget claims native packing"),
])
def test_handoff_rejects_unverified_editor_claims(tmp_path, member, field, value, error):
    result = _sample(tmp_path)
    _append_final_handoff_for_regression(result["package"])
    with ZipFile(result["package"]) as z:
        metadata = json.loads(z.read(member))
    metadata[field] = value
    altered = tmp_path / "fake_native_completion.zip"
    _rewrite_archive_member(result["package"], member, metadata, altered)
    with pytest.raises(ValueError, match=error):
        verify_artwork_package(altered, require_final_handoff=True)


def test_handoff_rejects_manual_reference_different_from_actual_psd(tmp_path):
    result = _sample(tmp_path)
    _append_final_handoff_for_regression(result["package"])
    with ZipFile(result["package"]) as z:
        manual = json.loads(z.read("metadata/manual_rig_reference.json"))
    manual["suggested_layer_entries"][0]["observed_bounds_xyxy"] = [1, 2, 3, 4]
    altered = tmp_path / "wrong_manual_coordinates.zip"
    _rewrite_archive_member(result["package"], "metadata/manual_rig_reference.json",
                            manual, altered)
    with pytest.raises(ValueError, match="manual Editor reference contradicts"):
        verify_artwork_package(altered, require_final_handoff=True)


@pytest.mark.parametrize("member", ["metadata/segmentation_trace.json",
                                    "metadata/manual_rig_reference.json",
                                    "OFFICIAL_EDITOR_SETTINGS.md"])
def test_final_handoff_requires_editor_evidence(tmp_path, member):
    result = _sample(tmp_path)
    _append_final_handoff_for_regression(result["package"])
    altered = tmp_path / "missing_handoff_evidence.zip"
    _rewrite_archive_member(result["package"], member, None, altered)
    with pytest.raises(ValueError, match="final handoff missing"):
        verify_artwork_package(altered, require_final_handoff=True)


def test_final_handoff_rejects_native_cubism_file_in_artwork_zip(tmp_path):
    result = _sample(tmp_path)
    _append_final_handoff_for_regression(result["package"])
    with ZipFile(result["package"], "a") as z:
        z.writestr("rig/claimed_model.MOC3", b"not a real model")
    with pytest.raises(ValueError, match="cannot claim native Cubism artifacts"):
        verify_artwork_package(result["package"], require_final_handoff=True)
