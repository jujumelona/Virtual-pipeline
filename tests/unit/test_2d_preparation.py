"""CPU-only contract tests for the independent 2D preparation output."""
import json
from pathlib import Path
from io import BytesIO
from xml.etree import ElementTree as ET
from zipfile import ZipFile, ZIP_DEFLATED

from PIL import Image
import pytest

from vtuber_pipeline.two_d import (prepare_2d_artwork, prepare_inochi2d_artwork, prepare_live2d_artwork)


def _artwork(path, rgba=(20, 40, 60, 255)):
    Image.new("RGBA", (512, 768), rgba).save(path)


def _png(rgba=(20, 40, 60, 100)):
    buf = BytesIO()
    Image.new("RGBA", (512, 768), rgba).save(buf, "PNG")
    return buf.getvalue()


def test_flat_image_never_claims_finished_cubism_model(tmp_path):
    artwork = tmp_path / "flat.png"
    _artwork(artwork)
    result = prepare_live2d_artwork(str(artwork), str(tmp_path / "2d"))
    assert result["status"] == "needs_layering"
    manifest = result["manifest"]
    assert manifest["is_live2d_model"] is False
    assert manifest["vtube_studio_ready"] is False
    assert manifest["can_export_moc3"] is False
    with ZipFile(result["package_path"]) as archive:
        assert "artwork.ora" in archive.namelist()
        assert "README_NEXT_STEPS.txt" in archive.namelist()
        assert not any(n.endswith(".moc3") for n in archive.namelist())
        with ZipFile(BytesIO(archive.read("artwork.ora"))) as ora:
            assert ora.read("mimetype") == b"image/openraster"
            assert len(ET.fromstring(ora.read("stack.xml")).find("stack")) == 1
            assert "mergedimage.png" in ora.namelist()


def test_real_user_part_layers_are_preserved_not_generated(tmp_path):
    artwork = tmp_path / "art.png"
    _artwork(artwork)
    zip_path = tmp_path / "layers.zip"
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as layers:
        layers.writestr("001_hair_front.png", _png((12, 34, 56, 127)))
        layers.writestr("002_face.png", _png((20, 10, 30, 180)))
    result = prepare_live2d_artwork(
        str(artwork), str(tmp_path / "out"), layers_zip=str(zip_path),
        commercial_usage="personalProfit",
    )
    assert result["status"] == "prepared"
    assert result["manifest"]["layer_names_top_to_bottom"] == [
        "001_hair_front", "002_face"]
    with ZipFile(result["package_path"]) as archive:
        with ZipFile(BytesIO(archive.read("artwork.ora"))) as ora:
            with Image.open(BytesIO(ora.read("data/layer_000.png"))) as first:
                assert first.getpixel((0, 0)) == (12, 34, 56, 127)
            assert len(ET.fromstring(ora.read("stack.xml")).find("stack")) == 2


def test_rejects_zip_traversal_before_parsing_layers(tmp_path):
    artwork = tmp_path / "art.png"
    _artwork(artwork)
    archive = tmp_path / "unsafe.zip"
    with ZipFile(archive, "w") as zipfile:
        zipfile.writestr("../escape.png", _png())
    with pytest.raises(ValueError, match="invalid layer ZIP member"):
        prepare_live2d_artwork(
            str(artwork), str(tmp_path / "out"), layers_zip=str(archive))


def test_rejects_different_layer_canvas(tmp_path):
    artwork = tmp_path / "art.png"
    _artwork(artwork)
    payload = BytesIO()
    Image.new("RGBA", (300, 400), "red").save(payload, "PNG")
    archive = tmp_path / "mismatch.zip"
    with ZipFile(archive, "w") as zipfile:
        zipfile.writestr("face.png", payload.getvalue())
    with pytest.raises(ValueError, match="layer canvas"):
        prepare_live2d_artwork(
            str(artwork), str(tmp_path / "out"), layers_zip=str(archive))


@pytest.mark.parametrize("target,final_extension", [
    ("inochi2d", ".inp"),
    ("live2d", ".moc3"),
])
def test_both_named_2d_modes_are_independent_and_cannot_claim_completion(
    tmp_path, target, final_extension,
):
    artwork = tmp_path / "original.png"
    _artwork(artwork)
    output = tmp_path / target
    result = prepare_2d_artwork(str(artwork), str(output), target=target)
    assert result["status"] == "needs_layering"
    assert Path(result["package_path"]).name == f"{target}_artwork_prep.zip"
    manifest = result["manifest"]
    assert manifest["mode"] == target
    assert manifest["expected_completed_extension"] == final_extension
    assert manifest["rig_generated"] is False
    assert manifest["vtube_studio_ready"] is False
    assert manifest["inochi_session_ready"] is False
    with ZipFile(result["package_path"]) as archive:
        assert not any(name.endswith((".inp", ".moc3")) for name in archive.namelist())
        instructions = archive.read("README_NEXT_STEPS.txt").decode("utf-8")
        if target == "inochi2d":
            assert "Inochi Creator" in instructions
            assert "Inochi Session" in instructions
        else:
            assert "Cubism Editor" in instructions
            assert "VTube Studio" in instructions


def test_named_2d_wrappers_cannot_route_to_other_target(tmp_path):
    artwork = tmp_path / "ref.png"
    _artwork(artwork)
    inochi = prepare_inochi2d_artwork(str(artwork), str(tmp_path / "i"))
    live2d = prepare_live2d_artwork(str(artwork), str(tmp_path / "l"))
    assert inochi["manifest"]["mode"] == "inochi2d"
    assert live2d["manifest"]["mode"] == "live2d"


def test_2d_rejects_unrecognized_target(tmp_path):
    artwork = tmp_path / "ref.png"
    _artwork(artwork)
    with pytest.raises(ValueError, match="unsupported 2D target"):
        prepare_2d_artwork(str(artwork), str(tmp_path / "output"), target="2d")
