"""Canonical image-AI briefs: 24 README targets and mode/asset-specific references.

ZIP structure and instructions only. Does not certify aesthetic image quality.
"""
from pathlib import Path
from zipfile import ZipFile
import pytest

ROOT = Path(__file__).resolve().parents[1] / "docs" / "image_ai_kits_v2"
MODES = ("live2d_bust_up", "live2d_upper", "live2d_full",
         "inochi2d_upper", "inochi2d_full", "3d")
ASSETS = ("body", "hair", "outfit", "accessory")
UPDATED = ("00_MASTER_FIRST.md", "00_READ_FIRST.md", "00_DELIVERY_AND_RECHECK.md",
           "01_COMMON_RULES.md", "02_ADVANCED_PARTS.md", "03_MODE_RULES.md",
           "07_REVIEW_BEFORE_FINAL_ZIP.md", "09_VISUAL_ART_QUALITY.md",
           "10_ANIME_STYLE.md", "11_OFFICIAL_IMAGE_EXAMPLES.md")


def test_only_24_readme_linked_zips_are_published():
    expected = {f"{mode}__{asset}.zip" for mode in MODES for asset in ASSETS}
    actual = {p.name for p in (ROOT / "zips").glob("*.zip")}
    assert actual == expected
    index = (ROOT / "README.md").read_text(encoding="utf-8")
    for filename in expected:
        assert f"zips/{filename}" in index


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("asset", ASSETS)
def test_every_canonical_zip_has_its_own_reference_and_scope_gate(mode, asset):
    path = ROOT / "zips" / f"{mode}__{asset}.zip"
    with ZipFile(path) as archive:
        assert archive.testzip() is None
        assert len(archive.namelist()) == len(set(archive.namelist())) == 14
        docs = {name: archive.read(name).decode("utf-8") for name in UPDATED}
    marker = f"[2026-10-13 v5 {mode}/{asset}"
    for name, contents in docs.items():
        assert marker in contents, (path, name)
        assert "REFERENCE_NOT_VIEWED" in contents, (path, name)
    # The mandatory read-all safety gate now precedes the asset-specific contract.
    assert docs["00_MASTER_FIRST.md"].startswith("# [READ_ALL_BEFORE_IMAGE_GENERATION_V1]")
    assert f"# 최우선 제작 계약: {mode} / {asset}" in docs["00_MASTER_FIRST.md"]
    first = docs["00_MASTER_FIRST.md"]
    assert "실제" in first and any(word in first for word in ("참고", "비교", "샘플", "이미지"))
    if asset == "body":
        assert "U형" in first and "귀" in first and "눈" in first
        if mode == "3d":
            assert ("전면" in first or "정면" in first) and "후면" in first and "좌/우" in first
            assert "2D 파츠" in first
        else:
            assert "도형" in first and "가슴" in first
    else:
        assert ("기준" in first or "참조" in first or "앵커" in first) and ("독립" in first or "한 종류" in first or "한 벌" in first)
    if mode == "3d":
        assert "VRM" in docs["00_READ_FIRST.md"]
    elif mode.startswith("inochi2d"):
        assert "Inochi" in docs["00_READ_FIRST.md"]
