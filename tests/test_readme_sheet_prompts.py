"""README-facing image prompts must map to actual production filenames."""
from pathlib import Path
import re
from vtuber_pipeline.sheet_contract import SHEETS_2D,VIEWS_3D
from vtuber_pipeline.wardrobe_contract import GARMENT_PARTS

README=(Path(__file__).resolve().parents[1]/"README.md")

def section():
    return README.read_text(encoding="utf-8").split("## 모드별 이미지 생성",1)[1].split("## 작업 모드",1)[0]

def prompts():
    content=section()
    out={}
    for m in re.finditer(
        r"#### `([^`]+)`[^\n]*\n[\s\S]*?```text\n([\s\S]*?)\n```",
        content
    ):
        if m.group(1).endswith(".png"):
            out[m.group(1)]=m.group(2)
    return out

def test_base_avatar_has_only_neutral_image_prompts_and_exact_filenames():
    p=prompts()
    needed={"front_master.png","face.png"}|{
        s.filename for s in (*SHEETS_2D,*VIEWS_3D)
    }
    assert needed.issubset(p)
    for name in needed:
        data=p[name]
        assert name in data and "{gender}" in data
        assert "WIDTH:HEIGHT" in data
        assert "4096x" not in data, name
        assert "NO costume" in data or "NO detachable clothing" in data or "NO jacket" in data or "OUTFIT-FREE" in data

def test_sheet_grids_and_wardrobe_ownership():
    p=prompts()
    for spec in SHEETS_2D:
        data=p[spec.filename]
        for tile in spec.tiles:
            assert tile.name in data
        if len(spec.tiles)>1:
            assert "2 columns x 2 rows" in data
        else:
            assert "1 column x 1 row" in data
    garment=p["outfit_variant.png"]
    assert "WIDTH:HEIGHT = 4:3" in garment
    assert "2 columns x 2 rows" in garment
    for name in GARMENT_PARTS:
        assert name in garment
    assert "character_2d_sheet_pack.zip" in section()
    assert "costume.xwear" in section()
    assert "garment_front_back_ref.png" in section()

def test_every_costume_reference_has_explicit_filename_and_aspect():
    p=prompts()
    for name in ("outfit_variant.png","garment_front_back_ref.png",
                 "garment_side_views_ref.png","garment_details_ref.png"):
        assert name in p
        assert "create and SAVE" in p[name]
        assert "WIDTH:HEIGHT" in p[name]
    assert "24파츠+의상 4파츠=28파츠" in section()
    assert "착용 완료 VRM" in section() or "입힌 VRM 완성품이 아닙니다" in section()
