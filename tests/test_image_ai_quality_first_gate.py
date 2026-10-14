"""End-to-end published instruction QA: image-generator art must precede PSD/ZIP.

These are requirements in prompts; tests cannot certify external image-model quality.
"""
from pathlib import Path
from zipfile import ZipFile

import pytest

from tools.apply_image_ai_multiview_briefs import ROOT, MODES, ASSETS, EXPECTED, COVER_MARKER
from tools.image_ai_quality_first_gate import START, END, DOCS, patched_text


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("asset", ASSETS)
def test_canonical_zip_uses_real_image_generation_before_layer_assembly(mode, asset):
    source = ROOT / f"{mode}__{asset}.zip"
    with ZipFile(source) as z:
        assert z.testzip() is None
        names = z.namelist()
        assert set(names) == set(EXPECTED)
        assert len(names) == 14
        docs = {name: z.read(name).decode("utf-8") for name in names}
    for name in DOCS:
        text = docs[name]
        assert text.count(START) == 1, f"{mode}/{asset} missing quality rule in {name}"
        assert text.count(END) == 1
        assert patched_text(text, mode=mode, asset=asset, name=name) == text
        assert "이미지 생성 AI" in text
        assert "Python/Pillow/cairoSVG/SVG" in text
        assert "마스터" in text
        assert "24개" in text
        assert "리깅" in text or "PSD" in text
    first = docs["00_MASTER_FIRST.md"]
    assert first.startswith("# [READ_ALL_BEFORE_IMAGE_GENERATION_V1]")
    if asset == "body":
        assert first.index(COVER_MARKER) < first.index(START)
        assert "불투명한 스포츠형 수영복 상의" in first and "하체가 화면에 포함되는" in first
        assert "눈 뜸/반감김/감김" in first
        assert "T/A 포즈" in first if mode == "live2d_bust_up" else True
    else:
        assert START in first and "눈 뜸/반감김/감김" not in first
        assert COVER_MARKER not in first
        assert "BODY 납품" not in first
    if mode == "3d":
        assert "PSD/2D 리깅 파일" not in first or "요구하지 않는다" in first
    else:
        assert "isolated_parts/*.png" in docs["04_OUTPUT_FILES.md"]


def test_crude_svg_pipeline_is_explicitly_rejected_in_live2d_bustup_brief():
    with ZipFile(ROOT / "live2d_bust_up__body.zip") as z:
        s = z.read("00_MASTER_FIRST.md").decode("utf-8")
    for cue in ("SVG path/ellipse/rectangle/polygon", "그림 자체를 생성형 이미지 모델",
                "가로로 활짝", "ART_QUALITY_UNVERIFIED"):
        if cue == "가로로 활짝":
            assert "양팔을 수평으로 활짝 펼친" in s
        else:
            assert cue in s


def test_all_quality_rules_are_scoped_to_the_selected_asset():
    for mode in MODES:
        for asset in ASSETS:
            with ZipFile(ROOT / f"{mode}__{asset}.zip") as z:
                brief = z.read("10_ANIME_STYLE.md").decode("utf-8")
            if asset == "hair":
                assert "HAIR 전용" in brief
            if asset == "outfit":
                assert "OUTFIT 전용" in brief
            if asset == "accessory":
                assert "ACCESSORY 전용" in brief
