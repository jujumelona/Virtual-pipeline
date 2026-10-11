"""README for phase-1 UI only. Image prompts will be authored in phase 2."""
from pathlib import Path
from tools.colab_mode_ui import TOP_MODE_CHOICES, ASSET_KINDS

README=Path(__file__).resolve().parents[1]/"README.md"


def test_readme_explains_all_five_modes_and_four_shared_assets():
    text=README.read_text(encoding="utf-8")
    for label, _, _ in TOP_MODE_CHOICES.values():
        assert label in text
    for label in ASSET_KINDS.values():
        assert label in text


def test_readme_does_not_claim_new_artwork_prompts_or_exporters_finished():
    text=README.read_text(encoding="utf-8")
    assert "후속 단계" in text
    assert "프롬프트" in text
    assert "아직 연결되지" in text
