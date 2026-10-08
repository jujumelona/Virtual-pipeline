"""Official Cubism handoff must not accept renamed files or unsafe references."""
import json

import pytest
from PIL import Image
from vtuber_pipeline.two_d.cubism_handoff import validate_official_export


def make_export(root):
    folder = root / "download" / "character"
    (folder / "textures").mkdir(parents=True)
    (folder / "avatar.moc3").write_bytes(b"MOC3" + bytes([1]) * 64)
    Image.new("RGBA", (4, 4), (255, 20, 20, 255)).save(folder / "textures" / "tex.png")
    document = {
        "Version": 3,
        "FileReferences": {"Moc": "avatar.moc3", "Textures": ["textures/tex.png"]},
    }
    (folder / "avatar.model3.json").write_text(json.dumps(document))
    return folder, document


def test_ancestor_directory_can_contain_one_export(tmp_path):
    folder, _ = make_export(tmp_path)
    got = validate_official_export(str(tmp_path / "download"))
    assert got["model3_json"] == str(folder / "avatar.model3.json")
    assert got["moc3"] == str(folder / "avatar.moc3")


def test_renamed_file_is_not_cubism_moc(tmp_path):
    folder, _ = make_export(tmp_path)
    (folder / "avatar.moc3").write_bytes(b"not-a-model")
    with pytest.raises(ValueError, match="signature"):
        validate_official_export(str(tmp_path / "download"))


def test_renamed_file_is_not_cubism_png(tmp_path):
    folder, _ = make_export(tmp_path)
    (folder / "textures" / "tex.png").write_bytes(b"not-an-image")
    with pytest.raises(ValueError, match="texture"):
        validate_official_export(str(tmp_path / "download"))


def test_parent_traversal_is_rejected(tmp_path):
    folder, document = make_export(tmp_path)
    document["FileReferences"]["Moc"] = "../avatar.moc3"
    (folder / "avatar.model3.json").write_text(json.dumps(document))
    with pytest.raises(ValueError, match="invalid Cubism export reference"):
        validate_official_export(str(tmp_path / "download"))
