"""Production FACE-only pathway smoke tests with real (synthetic) PNG bytes."""
import ast
import io
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from PIL import Image, ImageDraw

from tools.colab_mode_ui import ASSET_KINDS, select_mode
from tools.vts_multiview_runtime import VIEW_SETS, process_completed_ai_2d_zip
from tools.vts_source_only_pack import prepare_source_only_2d
import pytest
from tools.vts_segmentation_profiles import get_segmentation_profile


def test_face_is_visible_and_no_body_choice():
    assert tuple(ASSET_KINDS) == ("face", "character", "hair", "accessory", "outfit")
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
    names += ["expression_refs/mouth_closed.png", "expression_refs/mouth_open.png"]
    with ZipFile(art, "w", ZIP_DEFLATED) as z:
        for i, name in enumerate(names):
            image = Image.new("RGB", (1024, 1280), (245, 235, 230))
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
    assert result["stage"] == "FACE_STRUCTURE_VALID_VISUAL_REVIEW_REQUIRED"
    assert result["manual_visual_review_required"] is True
    assert result["visual_quality_verified"] is False
    assert result["native"]["moc3_generated"] is False
    assert result["moc3_application_verified"] is False
    package = Path(result["native"]["package"])
    with ZipFile(package) as z:
        assert z.testzip() is None
        assert "artwork/face_master.png" in z.namelist()
        assert "reference_views/face_front.png" in z.namelist()
        assert "expression_refs/mouth_open.png" in z.namelist()
        assert "expression_refs/mouth_closed.png" in z.namelist()
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

def _synthetic_face_input(path, *, canvas=(1024, 1280), missing=None,
                          duplicate_angle=False):
    names = ["outputs/master.png", *(f"reference_views/{v}.png"
             for v in VIEW_SETS["face"]),
             "expression_refs/mouth_closed.png",
             "expression_refs/mouth_open.png"]
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        for i, name in enumerate(names):
            if name == missing:
                continue
            image = Image.new("RGBA", canvas, (242, 212, 190, 255))
            draw = ImageDraw.Draw(image)
            offset = 0 if (duplicate_angle and
                           name == "reference_views/head_profile_L.png") else i
            draw.ellipse((50 + offset * 7, 55, 490, 850),
                         fill=(210, 120 + offset * 3, 110, 255))
            if name.endswith("mouth_open.png"):
                draw.ellipse((235, 650, 280, 715), fill=(50, 0, 0, 255))
            payload = io.BytesIO()
            image.save(payload, format="PNG")
            archive.writestr(name, payload.getvalue())


def test_face_mouth_expression_missing_is_rejected(tmp_path):
    art = tmp_path / "no_open_mouth.zip"
    _synthetic_face_input(art, missing="expression_refs/mouth_open.png")
    with pytest.raises(ValueError, match="MOUTH_EXPRESSION_REFERENCE_MISSING"):
        prepare_source_only_2d(art, tmp_path / "result", asset="face")


def test_face_low_resolution_placeholder_is_not_production_ready(tmp_path):
    art = tmp_path / "low_res.zip"
    _synthetic_face_input(art, canvas=(512, 512))
    with pytest.raises(ValueError, match="MASTER_TOO_SMALL"):
        prepare_source_only_2d(art, tmp_path / "result", asset="face")


def test_face_source_is_never_visually_certified_by_technical_preflight(tmp_path):
    art = tmp_path / "simple_shapes.zip"
    _synthetic_face_input(art)
    report = prepare_source_only_2d(art, tmp_path / "result", asset="face")
    assert report["visual_review_required"] is True
    assert report["parts"]["visual_quality_verified"] is False
    assert report["state"] == "FACE_STRUCTURE_VALID_VISUAL_REVIEW_REQUIRED"
    assert report["mouth_expression_reference_qa"]["status"] == "CLOSED_OPEN_PNG_CONTENT_DISTINCT"


def test_face_closed_and_open_same_pixels_rejected(tmp_path):
    art = tmp_path / "same_mouth.zip"
    _synthetic_face_input(art)
    with ZipFile(art) as z:
        entries = {n: z.read(n) for n in z.namelist()}
    entries["expression_refs/mouth_open.png"] = entries["expression_refs/mouth_closed.png"]
    with ZipFile(art, "w", ZIP_DEFLATED) as z:
        for name, payload in entries.items():
            z.writestr(name, payload)
    with pytest.raises(ValueError, match="MOUTH_EXPRESSION_REFERENCES_IDENTICAL"):
        prepare_source_only_2d(art, tmp_path / "result", asset="face")

