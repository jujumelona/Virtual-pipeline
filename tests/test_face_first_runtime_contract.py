"""Production FACE-only pathway smoke tests with real (synthetic) PNG bytes."""
import ast
import io
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from PIL import Image, ImageDraw

from tools.colab_mode_ui import ASSET_KINDS, select_mode
from tools.vts_multiview_runtime import VIEW_SETS, process_completed_ai_2d_zip
from tools.vts_segmentation_profiles import get_segmentation_profile


def test_face_is_visible_and_no_body_choice():
    assert tuple(ASSET_KINDS) == ("face", "hair", "accessory", "outfit")
    assert select_mode("face", "face").asset_label == "얼굴만"
    assert "body" not in ASSET_KINDS
    face = get_segmentation_profile("face", "face")
    assert face["requires_reference_body"] is False
    assert face["route"] == "face_source_needs_eye_mouth_segmentation"
    assert VIEW_SETS["face"][0] == "face_front"


def test_face_art_cannot_claim_body_native_rig(tmp_path):
    art = tmp_path / "face_source.zip"
    names = ["outputs/master.png", *(
        "reference_views/" + v + ".png" for v in VIEW_SETS["face"]
    )]
    with ZipFile(art, "w", ZIP_DEFLATED) as z:
        for i, name in enumerate(names):
            image = Image.new("RGB", (512, 512), (245, 235, 230))
            draw = ImageDraw.Draw(image)
            draw.ellipse((100+i*11, 40+i*5, 380-i*4, 430-i*3),
                         fill=(105+i*9, 60+i*6, 20+i*7))
            draw.line([(140+i, 70), (310, 320-i*8)], fill=(255, 255, 255), width=6)
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            z.writestr(name, buffer.getvalue())
    result = process_completed_ai_2d_zip(
        art, tmp_path / "produced", edition="free", scope="upper",
        asset="face", mode="face")
    assert result["stage"] == "FACE_ART_VERIFIED_NOT_SEGMENTED"
    assert result["native"]["moc3_generated"] is False
    assert result["moc3_application_verified"] is False
    package = Path(result["native"]["package"])
    with ZipFile(package) as z:
        assert z.testzip() is None
        assert "artwork/face_master.png" in z.namelist()
        assert "reference_views/face_front.png" in z.namelist()
        assert not any(x.endswith(".moc3") for x in z.namelist())


def test_notebook_has_face_only_branch_and_parses():
    path = Path(__file__).resolve().parents[1] / "notebooks/VTuber_Finished_AI_ZIP_All_Modes.ipynb"
    book = json.loads(path.read_text(encoding="utf-8"))
    snippets = []
    for i, cell in enumerate(book["cells"]):
        if cell["cell_type"] != "code":
            continue
        code = "".join(cell["source"])
        ast.parse(code, filename=f"cell-{i}")
        snippets.append(code)
    joined = "\n".join(snippets)
    assert "ASSET_LABEL='얼굴만'" in joined
    assert "if ASSET=='face':" in joined
    assert "FACE_SOURCE_ONLY_NOT_RIGGED" in joined
    assert "'native_files_created':RIGGED" in joined
