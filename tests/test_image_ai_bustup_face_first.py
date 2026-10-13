"""BUST-UP is an anime face-first close portrait, not a photographic upper-body mannequin."""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from zipfile import ZipFile

import pytest

ROOT = Path(__file__).resolve().parents[1] / "docs" / "image_ai_kits_v2"
SPEC = json.loads((ROOT / "source/BUST_UP_FACE_FIRST_CONTRACT.json").read_text(encoding="utf-8"))
ASSETS = ("body", "hair", "outfit", "accessory")
VISUAL_DOCS = ("00_MASTER_FIRST.md", "00_READ_FIRST.md", "03_MODE_RULES.md",
               "07_REVIEW_BEFORE_FINAL_ZIP.md", "09_VISUAL_ART_QUALITY.md",
               "10_ANIME_STYLE.md")


@pytest.mark.parametrize("asset", ASSETS)
def test_each_published_bust_up_zip_is_face_first_and_owned(asset):
    path = ROOT / "zips" / f"live2d_bust_up__{asset}.zip"
    with ZipFile(path) as z:
        assert len(z.namelist()) == 14
        assert len(set(z.namelist())) == 14
        assert z.testzip() is None
        docs = {name: z.read(name).decode("utf-8") for name in z.namelist()}

    marker = f"## [2026-10-13 FACE-FIRST 애니 바스트업 긴급 교정 | {asset}]"
    for name in VISUAL_DOCS:
        assert docs[name].count(marker) == 1, (asset, name)
    if asset == "body":
        assert docs["02_ADVANCED_PARTS.md"].count(marker) == 1
        assert SPEC["body_face"] in docs["02_ADVANCED_PARTS.md"]
        assert SPEC["body_visual_qa"] in docs["07_REVIEW_BEFORE_FINAL_ZIP.md"]
        assert SPEC["image_prompt_body"] in docs["10_ANIME_STYLE.md"]
        assert "양손" in docs["00_MASTER_FIRST.md"]
        assert "23~29%" in docs["02_ADVANCED_PARTS.md"]
        assert "62~80%" in docs["02_ADVANCED_PARTS.md"]
        assert "both" in docs["10_ANIME_STYLE.md"]
        assert "hands" in docs["10_ANIME_STYLE.md"]
    else:
        assert SPEC["short_scope"][asset] in docs["00_MASTER_FIRST.md"]
        assert SPEC["image_prompt_other"][asset] in docs["10_ANIME_STYLE.md"]
        assert "기준" in docs["00_MASTER_FIRST.md"]
        assert "새로 그리지" in docs["00_MASTER_FIRST.md"] or "신체" in docs["00_MASTER_FIRST.md"]

    all_text = "\n".join(docs.values())
    bad = r"2\.2~2\.8H|40~50%|1~2H|1~2높이|목·어깨·상체 약 1~2|18~22%|55~70%"
    assert re.search(bad, all_text) is None, asset
    # Full-body sample links are only optional ink/color references,
    # not prominent image prompts for bust-up proportions or copied characters.
    samples = docs["11_OFFICIAL_IMAGE_EXAMPLES.md"]
    assert "sample-img-tsumiki.png" in samples
    assert "sample-img-izumi.jpg" in samples
    assert "![Live2D official" not in samples
    assert "전신 샘플은 화풍 참고만" in samples


def test_face_first_contract_is_read_by_synchronizer():
    module_path = ROOT.parents[1] / "tools/sync_image_ai_geometry_guidance.py"
    loader = importlib.util.spec_from_file_location("face_first_synchronizer", module_path)
    assert loader and loader.loader
    module = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(module)

    assert module.BUSTUP_SPEC == ROOT / "source/BUST_UP_FACE_FIRST_CONTRACT.json"
    assert len(SPEC["short_scope"]) == 4
    for asset in ASSETS:
        sections = module.bustup_sections_for(SPEC, asset)
        assert "00_MASTER_FIRST.md" in sections
        assert "10_ANIME_STYLE.md" in sections
        assert "03_MODE_RULES.md" in sections
        if asset == "body":
            assert "02_ADVANCED_PARTS.md" in sections
        else:
            assert "02_ADVANCED_PARTS.md" not in sections

    with pytest.raises(ValueError, match="old rules persist"):
        module.check_bustup_legacy(
            "regenerated_old.zip",
            {"03_MODE_RULES.md": "화면 2.2~2.8H, 머리 40~50%"}
        )


def test_original_2d_source_prioritizes_bustup_face_over_full_body():
    master = (ROOT / "source/BODY_2D.md").read_text(encoding="utf-8")
    mode = (ROOT / "source/MODE_2D.md").read_text(encoding="utf-8")
    style = (ROOT / "source/ANIME_VTUBER_STYLE_2D.md").read_text(encoding="utf-8")
    quality = (ROOT / "source/QUALITY_STANDARD_2D.md").read_text(encoding="utf-8")
    assert "바스트업은 전신 스케치 없이" in master
    assert "양손" in mode
    assert SPEC["image_prompt_body"] in style
    assert SPEC["body_visual_qa"] in quality
