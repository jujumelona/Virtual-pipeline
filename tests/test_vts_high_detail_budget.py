"""Regression contract for high-detail Live2D Qwen refinement settings."""
import json
from pathlib import Path

import pytest

from tools.vts_artwork_export import validate_artwork_request
from tools.colab_mode_ui import refresh_qwen

ROOT = Path(__file__).resolve().parents[1]


def test_free_detail_budget_accepts_thirty_two_and_caps_forty_eight():
    validate_artwork_request(edition="free", scope="upper", per_pass_layers=4, max_qwen_passes=32)
    validate_artwork_request(edition="free", scope="full", per_pass_layers=4, max_qwen_passes=48)
    with pytest.raises(ValueError, match="recursion budget"):
        validate_artwork_request(edition="free", scope="upper", per_pass_layers=4, max_qwen_passes=49)


def test_colab_auto_mode_still_enables_refinement():
    options = {"LIVE2D_QWEN": "auto", "LIVE2D_USE_QWEN": False}
    refresh_qwen(options)
    assert options["LIVE2D_USE_QWEN"] is True


def test_latest_colab_notebook_exposes_high_detail_budget():
    notebook = json.loads((ROOT / "notebooks" / "VTuber_Commercial_Pipeline_Colab_v8.ipynb").read_text(encoding="utf-8"))
    source = "\n".join("".join(cell.get("source", [])) for cell in notebook["cells"])
    assert "LIVE2D_QWEN_PASSES_OPTION = 32" in source
    assert "LIVE2D_QWEN_PASSES = 32" in source
    assert "LIVE2D_QWEN_OPTION = \"auto\"" in source
