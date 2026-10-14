"""README must accurately distinguish selection, Live2D build, and unverified stages."""
from pathlib import Path
from tools.colab_mode_ui import TOP_MODE_CHOICES, ASSET_KINDS

README=Path(__file__).resolve().parents[1]/"README.md"


def test_readme_explains_all_five_modes_and_four_shared_assets():
    text=README.read_text(encoding="utf-8")
    for label, _, _ in TOP_MODE_CHOICES.values():
        assert label in text
    for label in ASSET_KINDS.values():
        assert label in text


def test_readme_describes_connected_live2d_and_unverified_execution():
    text=README.read_text(encoding="utf-8")
    assert "VTuber_Finished_AI_ZIP_All_Modes.ipynb" in text
    assert "PSD2Live" in text and "RIGGING=auto" in text
    assert "분리 PSD" in text and "artwork_only" in text
    assert "자동 리깅을 기본 실행" not in text
    assert "Live2D" in text and "⑤" in text and "⑨" in text
    assert "ZIP" in text and "PSD" in text
    assert "실제 Colab GPU" in text
    assert "Cubism" in text and "미검증" in text
