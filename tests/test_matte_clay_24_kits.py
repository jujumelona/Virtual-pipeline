"""Static regression contract for all 24 published matte-clay drawing ZIPs."""
from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import pytest

from tools.normalize_matte_clay_kits import (
    ROOT, MODES, ASSETS, START, END, normalize,
)

DOCUMENTS = {
    "00_MASTER_FIRST.md", "00_DELIVERY_AND_RECHECK.md", "00_READ_FIRST.md",
    "01_COMMON_RULES.md", "02_ADVANCED_PARTS.md", "03_MODE_RULES.md",
    "04_OUTPUT_FILES.md", "05_OFFICIAL_REFERENCES.md",
    "06_ADVANCED_OFFICIAL_COMMUNITY.md", "07_REVIEW_BEFORE_FINAL_ZIP.md",
    "08_PRACTICAL_TIPS.md", "09_VISUAL_ART_QUALITY.md",
    "10_ANIME_STYLE.md", "11_OFFICIAL_IMAGE_EXAMPLES.md",
}
OLD_CONFLICTS = (
    "회색 단색 몸통, 프록시 도형",
    "단색 몸통 프록시를 금지",
    "단색 몸통 프록시 금지",
    "회색 찰흙/기하 프록시가 아닌",
    "비키니형 스포츠",
    "반도형 수영복",
    "끈 없는 반도(bandeau)/일자형 튜브 수영복",
)

@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("asset", ASSETS)
def test_published_kit_is_complete_scoped_and_idempotent(mode, asset):
    path = ROOT / f"{mode}__{asset}.zip"
    with ZipFile(path) as z:
        assert set(z.namelist()) == DOCUMENTS
        assert len(z.namelist()) == len(DOCUMENTS) == 14
        assert z.testzip() is None
        docs = {name: z.read(name).decode("utf-8") for name in z.namelist()}

    for name, data in docs.items():
        assert data.count(START) == data.count(END) == 1, (path, name)
        assert normalize(data, asset, mode, name) == data, (path, name)
        if asset == "body":
            assert "불투명 단색 무광 찰흙형" in data, (path, name)
            assert all(old not in data for old in OLD_CONFLICTS), (path, name)
        else:
            assert "BODY_DEFAULT_OPAQUE_SWIMWEAR_V1" not in data
            assert "찰흙형" in data, (path, name)
    master = docs["00_MASTER_FIRST.md"]
    assert master.startswith("# [READ_ALL_BEFORE_IMAGE_GENERATION_V1]")
    if asset == "body":
        assert "removable_neutral_modesty_band_upper" in master
        assert "목과 양쪽 어깨" in master
        assert "얼굴" in master and "눈" in master
        assert "MATTE_CLAY_BODY_V1" in master
    if mode == "3d":
        assert "8방향" in master
        assert "views/" in docs["04_OUTPUT_FILES.md"]
    else:
        assert "reference_views/" in docs["04_OUTPUT_FILES.md"]
        assert "isolated_parts/" in docs["04_OUTPUT_FILES.md"]

def test_exactly_six_body_and_eighteen_independent_assets():
    paths = sorted(ROOT.glob("*.zip"))
    assert len(paths) == 24
    assert sum(p.name.endswith("__body.zip") for p in paths) == 6
    assert sum(not p.name.endswith("__body.zip") for p in paths) == 18
