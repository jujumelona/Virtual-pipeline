"""README is the copy/paste interface for generating external sprite sheets.

Each individual AI prompt must carry exact dimensions, absolute master
coordinates, tile pixel boundaries and character orientation independently;
users must never depend on prose appearing outside the copied code block.
"""
from __future__ import annotations

from pathlib import Path
import re

from vtuber_pipeline.sheet_contract import MASTER, SHEETS_2D, VIEWS_3D

ROOT = Path(__file__).resolve().parents[1]
PROMPTS = ROOT / "README.md"


def prompts():
    text = PROMPTS.read_text(encoding="utf-8")
    section = text.split("## 고화질 시트 제작", 1)[1].split("## 작업 모드", 1)[0]
    result = {}
    for match in re.finditer(
        r"#### (?:2D|3D)-\d+\. `([^`]+)`[^\n]*\n[\s\S]*?```text\n([\s\S]*?)\n```",
        section,
    ):
        assert match.group(1) not in result
        result[match.group(1)] = match.group(2)
    return result


def test_every_generated_image_has_one_complete_copypaste_prompt():
    data = prompts()
    expected = (
        {"front_master.png", "face.png"}
        | {sheet.filename for sheet in SHEETS_2D}
        | {sheet.filename for sheet in VIEWS_3D}
    )
    assert set(data) == expected
    for name, prompt in data.items():
        assert "{gender}" in prompt, name
        assert "{palette}" in prompt, name
        assert name in prompt, name
        assert "TOP-LEFT" in prompt, name
        assert "+X" in prompt and "+Y" in prompt, name
        assert "LEFT" in prompt and "RIGHT" in prompt, name


def test_2d_each_prompt_contains_master_pixel_anchors_and_exact_resolution():
    for sheet in SHEETS_2D:
        prompt = prompts()[sheet.filename]
        assert "2048x3072" in prompt
        for landmark in ("240", "1110", "1280", "1380", "1510",
                         "1590", "1730", "2700"):
            assert landmark in prompt, (sheet.filename, landmark)
        assert str(sheet.size[0]) in prompt
        assert str(sheet.size[1]) in prompt
        assert "REAL transparent alpha" in prompt
        assert "front_master.png" in prompt
        assert "CHARACTER LEFT = VIEWER RIGHT" in prompt
        assert "SHEET" in prompt
        for t in sheet.tiles:
            cw, ch = sheet.cell_size
            x, y = t.col * cw, t.row * ch
            assert t.name in prompt
            assert f"[{x},{y},{x+cw},{y+ch})" in prompt, (
                sheet.filename, t.name
            )


def test_3d_each_view_prompt_has_full_landmarks_and_individual_cell_boxes():
    for sheet in VIEWS_3D:
        prompt = prompts()[sheet.filename]
        for value in ("4096x3072", "2048x3072", "1024",
                      "150", "600", "730", "1550", "2330", "2930"):
            assert value in prompt, (sheet.filename, value)
        for tile in sheet.tiles:
            assert tile.name.upper() in prompt
            a, b, c, d = sheet.box(tile)
            assert f"[{a},{b},{c},{d})" in prompt


def test_standalone_master_and_face_have_their_own_coordinates():
    data = prompts()
    master = data["front_master.png"]
    face = data["face.png"]
    assert "WIDTH=2048 HEIGHT=3072" in master
    assert "center x=1024" in master
    assert "crown y≈240" in master
    assert "2048x2048" in face
    assert "1050" in face
    assert "sheet_front_back.png" in face
    assert "first master image" in master or "first image" in master
