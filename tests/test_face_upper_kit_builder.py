"""A synthetic source FACE must register once, with reproducible ZIP references."""
import json
from pathlib import Path
from zipfile import ZipFile

from PIL import Image

from tools.build_face_upper_alignment_kits import build


def test_upper_refpack_uses_fixed_canvas_and_no_fake_artwork(tmp_path):
    face = Image.new("RGBA", (1536, 1920), (0, 0, 0, 0))
    # Synthetic large scalp/neck proxy only for pixel geometry test.
    face.paste((240, 212, 186, 255), (76, 69, 1484, 1871))
    src = tmp_path / "face__ARTWORK.zip"
    pic = tmp_path / "front.png"
    face.save(pic)
    with ZipFile(src, "w") as archive:
        archive.write(pic, "outputs/master.png")
    result = build(src, tmp_path / "aligned")
    assert result["canvas"] == [1536, 2304]
    assert result["source_master_alpha_bbox"] == [76, 69, 1484, 1871]
    assert result["registered_face_alpha_bbox"] == [380, 140, 1156, 1132]
    image = Image.open(tmp_path / "aligned" / "face_registered_upper.png")
    assert image.size == (1536, 2304)
    assert image.mode == "RGBA"
    assert image.getchannel("A").getbbox() == (380, 140, 1156, 1132)
    assert result["full_character_generated"] is False
    for role in ("COMPLETE_CHARACTER", "OUTFIT", "HAIR", "ACCESSORY"):
        kit = tmp_path / "aligned" / f"GENERATOR_{role}_UPPER_REFERENCE.zip"
        with ZipFile(kit) as archive:
            assert archive.testzip() is None
            assert archive.read("face_registered_upper.png")
            assert archive.read("01_GENERATION_PROMPT.txt")
            assert "outputs/master.png" not in archive.namelist()
    assert json.loads((tmp_path / "aligned" / "registration_contract.json").read_text())["full_character_generated"] is False
