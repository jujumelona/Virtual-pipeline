"""Prevent generic kit updaters from erasing manually reviewed VTuber art.

The actual 24 binary ZIP documents are reviewed separately. These synthetic
tests exercise the source normalizer's no-overwrite safety boundary.
"""
import pytest

from tools.image_ai_source_only_contract import (
    BEGIN, END, normalize_source_only, source_contract,
)


def reviewed_doc(mode, asset, filename):
    src = BEGIN + "\n" + source_contract(mode, asset) + "\n" + END
    src += "\n## [VTUBER_SIDE_NECK_RIG_ACCEPTANCE_V1]\nverified native limitation\n"
    if filename == "02_ADVANCED_PARTS.md":
        src += "\n## [EXPLICIT_DRAWING_STEPS_V1]\npaint neck hidden up to mouth\n"
        src += "## [/EXPLICIT_DRAWING_STEPS_V1]\n"
        if mode != "3d":
            src += ("\n## [SINGLE_PART_VISUAL_TASK_CARDS_V1]\n"
                    "only one part per paint job\n"
                    "## [/SINGLE_PART_VISUAL_TASK_CARDS_V1]\n")
    elif filename == "07_REVIEW_BEFORE_FINAL_ZIP.md":
        src += ("\n## [REAL_VISUAL_REVIEW_V1]\n"
                "inspect mouth and neck on 3/4 yaw\n"
                "## [/REAL_VISUAL_REVIEW_V1]\n")
    return src


@pytest.mark.parametrize("filename", [
    "02_ADVANCED_PARTS.md", "04_OUTPUT_FILES.md",
    "07_REVIEW_BEFORE_FINAL_ZIP.md",
])
@pytest.mark.parametrize("mode,asset", [
    ("live2d_bust_up", "body"), ("inochi2d_full", "outfit"),
    ("3d", "body"),
])
def test_manual_artwork_documents_never_silently_rebuilt(mode, asset, filename):
    document = reviewed_doc(mode, asset, filename)
    assert normalize_source_only(document, mode, asset, filename) == document


def test_missing_manual_paint_recipe_is_fatal():
    doc = reviewed_doc("live2d_bust_up", "body", "02_ADVANCED_PARTS.md")
    doc = doc.replace("## [EXPLICIT_DRAWING_STEPS_V1]", "")
    with pytest.raises(ValueError, match="MANUAL_IMAGE_KIT_DRAWING_STEPS_MISSING"):
        normalize_source_only(doc, "live2d_bust_up", "body",
                              "02_ADVANCED_PARTS.md")


def test_duplicate_manual_acceptance_is_fatal():
    doc = reviewed_doc("live2d_upper", "body", "00_READ_FIRST.md")
    doc += "\n[VTUBER_SIDE_NECK_RIG_ACCEPTANCE_V1]"
    with pytest.raises(ValueError, match="MANUAL_IMAGE_KIT_CONTRACT_CORRUPT"):
        normalize_source_only(doc, "live2d_upper", "body", "00_READ_FIRST.md")


def test_legacy_output_file_preserves_embedded_artwork_appendix():
    doc = ("# old instructions\n"
           "## [EXPLICIT_DRAWING_STEPS_V1]\n"
           "Keep artist-reviewed hidden neckline.\n"
           "## [/EXPLICIT_DRAWING_STEPS_V1]\n")
    updated = normalize_source_only(
        doc, "live2d_bust_up", "body", "04_OUTPUT_FILES.md")
    assert "Keep artist-reviewed hidden neckline." in updated
    assert "ONE_PART_PER_GENERATION_V1" in updated
