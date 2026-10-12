"""Regression contract for high-detail Live2D Qwen refinement settings."""
import json
from pathlib import Path

import pytest

from tools.vts_artwork_export import validate_artwork_request

ROOT = Path(__file__).resolve().parents[1]


def test_free_detail_budget_accepts_thirty_two_and_caps_forty_eight():
    validate_artwork_request(edition="free", scope="upper", per_pass_layers=4, max_qwen_passes=32)
    validate_artwork_request(edition="free", scope="full", per_pass_layers=4, max_qwen_passes=48)
    with pytest.raises(ValueError, match="recursion budget"):
        validate_artwork_request(edition="free", scope="upper", per_pass_layers=4, max_qwen_passes=49)


def test_replacement_colab_does_not_expose_obsolete_refinement_options():
    notebook = json.loads((ROOT / "notebooks" / "VTuber_Commercial_Pipeline_Colab_v8.ipynb").read_text(encoding="utf-8"))
    cells = ["".join(cell.get("source", [])) for cell in notebook["cells"]
             if cell.get("cell_type") == "code"]
    source = "\n".join(cells[:4])
    for legacy in ("LIVE2D_QWEN_PASSES_OPTION", "LIVE2D_QWEN_OPTION",
                   "refresh_qwen(", "tools.vts_setup", "run_see_through"):
        assert legacy not in source
    # Later production cells may prepare See-through for unlayered inputs.
    # For completed AI artwork ZIPs, model loading is deliberately skipped.
    assert "prepare_large_ai_pack" in "\n".join(cells[4:])
    assert 'if INPUT_KIND == "single_image"' in "\n".join(cells[4:])
