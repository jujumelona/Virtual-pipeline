"""Prevent reintroduction of the oversized FACE -> upper-body mismatch."""
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks" / "FACE_SeeThrough_OfficialAligned_v3.ipynb"
GUIDE = ROOT / "docs" / "SEE_THROUGH_REGISTERED_UPPER_INPUT_2026-10-22.md"

def test_registered_upper_notebook_input_contract():
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    codes = ["".join(c["source"]) for c in notebook["cells"] if c["cell_type"] == "code"]
    assert len(codes) == 7
    for i, code in enumerate(codes):
        ast.parse(code, filename=f"see-through-registered-upper-cell-{i}")
    combined = "\n".join(codes)
    assert "SIZE=(1536,2304)" in combined
    assert "'complete_character__ARTWORK.zip'" in combined
    assert "'full_character_input.png'" in combined
    assert "'face_registered_upper.png'" in combined
    assert "'registration_contract.json'" in combined
    assert "registered_face_sha256" in combined
    assert "bbox" in combined
    assert "VISUAL_APPROVED=False" in combined
    assert "face__ARTWORK.zip" not in combined  # old oversized FACE upload is forbidden

def test_generation_guide_distinguishes_ai_zip_and_model_input():
    text = GUIDE.read_text(encoding="utf-8")
    assert "1536×1920" in text
    assert "1536×2304" in text
    assert "0.55" in text
    assert "(380,140)" in text
    assert "GENERATOR_OUTFIT_UPPER_REFERENCE.zip" in text
    assert "GENERATOR_HAIR_UPPER_REFERENCE.zip" in text
    assert "complete_character__ARTWORK.zip" in text
    assert "See-through" in text
