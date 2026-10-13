"""Audit every published AI art instruction document, not just the first MD.

Checks old execution-instruction conflicts, asset ownership, source rehydration,
and distribution paths. ZIP/document QA does not imply rendered artwork quality.
"""
from pathlib import Path
from zipfile import ZipFile
import json
import re

import pytest

ROOT = Path(__file__).resolve().parents[1] / "docs" / "image_ai_kits_v2"
MODES = ("live2d_bust_up", "live2d_upper", "live2d_full",
         "inochi2d_upper", "inochi2d_full", "3d")
ASSETS = ("body", "hair", "outfit", "accessory")
EXPECTED_MD = {
    "00_MASTER_FIRST.md", "00_DELIVERY_AND_RECHECK.md", "00_READ_FIRST.md",
    "01_COMMON_RULES.md", "02_ADVANCED_PARTS.md", "03_MODE_RULES.md",
    "04_OUTPUT_FILES.md", "05_OFFICIAL_REFERENCES.md",
    "06_ADVANCED_OFFICIAL_COMMUNITY.md", "07_REVIEW_BEFORE_FINAL_ZIP.md",
    "08_PRACTICAL_TIPS.md", "09_VISUAL_ART_QUALITY.md",
    "10_ANIME_STYLE.md", "11_OFFICIAL_IMAGE_EXAMPLES.md",
}

# These are outdated *positive production instructions*, not names of
# things that a negative QA checklist may legitimately prohibit.
DEPRECATED = (
    re.compile(r"불투명\s*기본\s*(?:속옷|상의|의복)"),
    re.compile(r"선정적이지 않은 불투명 기본 속옷"),
    re.compile(r"기본 속옷 착용 상태"),
    re.compile(r"목·가슴·배는 매끈한 2~3단 셀"),
    re.compile(r"몸통을 한 번에 그리"),
    re.compile(r"전신 신체를 직접 그리므로"),
    re.compile(r"속옷을 입은 전신 캐릭터"),
)


def test_exactly_24_canonical_zip_files_and_links():
    expected = {f"{mode}__{asset}.zip" for mode in MODES for asset in ASSETS}
    assert {p.name for p in (ROOT / "zips").glob("*.zip")} == expected
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for name in expected:
        assert f"zips/{name}" in readme


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("asset", ASSETS)
def test_all_14_md_documents_have_no_deprecated_generation_contracts(mode, asset):
    archive_path = ROOT / "zips" / f"{mode}__{asset}.zip"
    with ZipFile(archive_path) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) == EXPECTED_MD
        for doc in sorted(EXPECTED_MD):
            text = archive.read(doc).decode("utf-8")
            for rule in DEPRECATED:
                assert rule.search(text) is None, (
                    f"{archive_path.name}:{doc}: obsolete instruction {rule.pattern}"
                )
            if doc == "00_MASTER_FIRST.md":
                assert "REFERENCE_NOT_VIEWED" in text
                if asset == "body":
                    assert "U형" in text and "귀" in text
                    assert "프록시" in text or "마네킹" in text
                else:
                    assert "기준" in text or "참조" in text
            if doc == "00_READ_FIRST.md":
                if mode == "3d":
                    assert "VRM" in text
                elif mode.startswith("inochi2d"):
                    assert "Inochi" in text
                else:
                    assert "Live2D" in text or "Cubism" in text


@pytest.mark.parametrize("family", ("2D", "3D"))
def test_rebuild_snapshots_match_all_original_source_documents(family):
    snapshot = json.loads((ROOT / "builder_inputs" / f"{family}.json")
                          .read_text(encoding="utf-8"))
    assert len(snapshot) == 10
    for filename, included in snapshot.items():
        assert included == (ROOT / "source" / filename).read_text(encoding="utf-8")


def test_source_quality_rules_allow_body_proxy_not_clothed_skin():
    quality = (ROOT / "source" / "QUALITY_STANDARD_2D.md").read_text(encoding="utf-8")
    body2d = (ROOT / "source" / "BODY_2D.md").read_text(encoding="utf-8")
    body3d = (ROOT / "source" / "BODY_3D.md").read_text(encoding="utf-8")
    assert "BODY 몸통" in quality and "도형" in quality
    assert "몸 전체를 이미지 생성 AI에 한 장으로 그리도록 요청하지 않는다" in body2d
    assert "불투명 중립색 마네킹 실루엣" in body3d
    for source in (quality, body2d, body3d):
        assert "불투명·비선정적 기본 속옷" not in source
        assert "선정적이지 않은 불투명 기본 속옷" not in source
