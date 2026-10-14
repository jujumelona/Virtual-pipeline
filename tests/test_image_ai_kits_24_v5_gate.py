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


def _read_all_gate_is_valid(master: str) -> bool:
    """A real unique read-all heading must precede legacy template slots."""
    lines = master.splitlines()
    gates = [i for i, line in enumerate(lines)
             if line.startswith("# [READ_ALL_BEFORE_IMAGE_GENERATION_V1]")]
    slots = [i for i, line in enumerate(lines)
             if line.startswith("## [EXISTING_VTUBER_TEMPLATE_SLOTS_V1]")]
    return len(gates) == len(slots) == 1 and gates[0] < slots[0]


def test_read_all_gate_allows_priority_preamble_but_rejects_invalid_headings():
    gate = "# [READ_ALL_BEFORE_IMAGE_GENERATION_V1] — 먼저 참고를 읽는다"
    slots = "## [EXISTING_VTUBER_TEMPLATE_SLOTS_V1]"
    assert _read_all_gate_is_valid("# 새로운 최우선 계약\n" + gate + "\n" + slots)
    assert _read_all_gate_is_valid(gate + "\n" + slots)
    assert not _read_all_gate_is_valid(slots + "\n" + gate)
    assert not _read_all_gate_is_valid("# 다른 계약\n" + slots)
    assert not _read_all_gate_is_valid(gate + "\n" + gate + "\n" + slots)
    assert not _read_all_gate_is_valid("인용: " + gate + "\n" + slots)
    assert not _read_all_gate_is_valid(gate + "\n" + slots + "\n" + slots)


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
    # A mode-specific priority heading may precede the mandatory read-all gate.
    # Fail closed on missing, duplicate, or reordered heading markers.
    assert _read_all_gate_is_valid(docs["00_MASTER_FIRST.md"]), path
    assert f"# 최우선 제작 계약: {mode} / {asset}" in docs["00_MASTER_FIRST.md"]
    first = docs["00_MASTER_FIRST.md"]
    assert "실제" in first and any(word in first for word in ("참고", "비교", "샘플", "이미지"))
    if asset == "body":
        assert "U형" in first and "귀" in first and "눈" in first
        if mode == "3d":
            assert ("전면" in first or "정면" in first) and "후면" in first and "좌/우" in first
            assert "2D 파츠" in first
        else:
            assert "애니" in first and "목" in first and ("손" in first or "양손" in first)
    else:
        assert ("기준" in first or "참조" in first or "앵커" in first) and ("독립" in first or "한 종류" in first or "한 벌" in first)
    if mode == "3d":
        assert "VRM" in docs["00_READ_FIRST.md"]
    elif mode.startswith("inochi2d"):
        assert "Inochi" in docs["00_READ_FIRST.md"]
