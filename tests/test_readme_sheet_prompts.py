"""README image input contract: modular 2D and skin-colored neutral 3D.

Every exported image prompt must be self-contained: filename, ratio, number
of views/parts, reference attachment, and costume treatment. Do not make
prompts pretend the model generates a fixed 4K file automatically.
"""
from pathlib import Path
import re
from vtuber_pipeline.sheet_contract import SHEETS_2D,VIEWS_3D
from vtuber_pipeline.hair_contract import HAIR_PARTS,HAIR_SHEET
from vtuber_pipeline.wardrobe_contract import GARMENT_PARTS,GARMENT_SHEET

README=Path(__file__).resolve().parents[1]/"README.md"

def section():
    return README.read_text(encoding="utf-8").split(
        "## 모드별 이미지 생성",1
    )[1].split("## 작업 모드",1)[0]

def prompts():
    result={}
    for match in re.finditer(
        r"#{4,5} `([^`]+)`[^\n]*\n[\s\S]*?```text\n([\s\S]*?)\n```",
        section(),
    ):
        if match.group(1).endswith(".png"):
            result[match.group(1)]=match.group(2)
    return result

def test_exact_input_artifacts_and_filename_in_each_prompt():
    expected={"front_master.png","face.png","hair_variant.png",
              "outfit_variant.png"}|{
        s.filename for s in (*SHEETS_2D,*VIEWS_3D)
    }
    assert expected <= set(prompts())
    for name in expected:
        p=prompts()[name]
        assert name in p,name
        assert "{gender}" in p,name
        assert "4096x" not in p,name
        assert "WIDTH:HEIGHT" in p or "width:height" in p,name

def test_character_base_is_20_parts_no_hair_no_outfit():
    assert sum(len(s.tiles) for s in SHEETS_2D)==20
    data=prompts()
    core={"front_master.png"}|{s.filename for s in SHEETS_2D}
    for name in core:
        p=data[name]
        assert "{skin_color}" in p, name
        assert "{base_layer}" not in p, name
        assert "Neutral fitted UNDERLAYER" not in p, name
        assert "NO gray/flesh-colored bodysuit" in p or "Do NOT draw a bodysuit" in p, name
        assert ("NO costume" in p or "NO detachable costume" in p
                or "NO detachable clothing" in p or "NO jacket" in p
                or "OUTFIT-FREE" in p),name
    a=section().split("### ① 캐릭터 생성 — 2D",1)[1].split(
        "### ① 캐릭터 생성 — 3D",1
    )[0]
    assert "character_2d_sheet_pack.zip" in a
    assert "sheet_hair.png" not in a
    assert "hair_variant.png" not in a
    assert "sheet_body_base.png" in a

def test_hairstyle_and_costume_are_optional_distinct_artwork():
    p=prompts()
    hair=p["hair_variant.png"]
    outfit=p["outfit_variant.png"]
    assert "2 columns x 2 rows" in hair or "2 columns x 2 rows" in section()
    for name in HAIR_PARTS:
        assert name in hair
    assert "WIDTH:HEIGHT=2:3" in hair
    assert "WIDTH:HEIGHT = 4:3" in outfit
    for name in GARMENT_PARTS:
        assert name in outfit
    assert "hair_variant.png" in section()
    assert "outfit_variant.png" in section()
    assert "20파츠+의상 4파츠=24파츠" in section()
    assert HAIR_SHEET.filename!="sheet_hair.png"
    assert GARMENT_SHEET.filename=="outfit_variant.png"

def test_3d_base_prompts_keep_skin_tone_without_integrated_outfit():
    p=prompts()
    for view in VIEWS_3D:
        prompt=p[view.filename]
        assert "{skin_color}" in prompt
        assert "PRODUCTION PURPOSE — 3D VTUBER BASE" in prompt
        assert "NO garment of any kind" in prompt
        assert "DEFAULT INTEGRATED OUTFIT" not in prompt
        assert "SAME COMPLETE DEFAULT OUTFIT" not in prompt
        assert "4:3" in prompt
        assert "2:3" in prompt
        for tile in view.tiles:
            assert tile.name.upper() in prompt
    face=p["face.png"]
    assert "{skin_color}" in face
    assert "PRODUCTION PURPOSE — MATCH THE 3D VTUBER BASE IDENTITY" in face
    assert "width:height=1:1" in face
    assert "NO costume collar" in face
    assert "character_3d_sheet_pack.zip" in section()
    assert "3D 의상 자동 교체는 제공하지 않습니다" in section()
    assert "정적 소품" in section()


def test_every_master_and_body_prompt_is_a_modular_vtuber_base():
    p=prompts()
    assert "MODULAR ADULT VTUBER AVATAR BASE" in p["front_master.png"]
    assert "NO gray/flesh-colored bodysuit" in p["sheet_body_base.png"]
    assert "NO gray/flesh-colored bodysuit" in p["sheet_arms_hands.png"]
    assert "TRUE transparent RGBA" in p["outfit_variant.png"]
    assert "alpha=0" in p["hair_variant.png"]
