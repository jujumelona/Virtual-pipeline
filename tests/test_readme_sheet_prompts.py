"""All image AI README prompts are independently pasteable and ratio-only."""
from pathlib import Path
import re
from vtuber_pipeline.sheet_contract import SHEETS_2D,VIEWS_3D

def readme():
    return (Path(__file__).resolve().parents[1]/"README.md").read_text(encoding="utf-8")

def prompts():
    section=readme().split("## 캐릭터 이미지 제작:",1)[1].split("## 작업 모드",1)[0]
    patterns=[
        r"#### 2D-0\. `([^`]+)`[^\n]*\n[\s\S]*?```text\n([\s\S]*?)\n```",
        r"#### `([^`]+)`[^\n]*\n[\s\S]*?```text\n([\s\S]*?)\n```",
    ]
    out={}
    for pat in patterns:
        for m in re.finditer(pat,section):
            if m.group(1).endswith(".png"):
                assert m.group(1) not in out
                out[m.group(1)]=m.group(2)
    return out

def test_prompt_per_image_and_no_unreachable_fixed_resolution():
    got=prompts()
    expected={"front_master.png","face.png"}
    expected|={s.filename for s in (*SHEETS_2D,*VIEWS_3D)}
    assert set(got)==expected
    for name,prompt in got.items():
        assert "{gender}" in prompt and "{outfit}" in prompt,name
        assert "ASPECT RATIO" in prompt,name
        assert name in prompt,name
        assert "4096x" not in prompt,name
        assert "WIDTH=2048" not in prompt,name

def test_sheet_ratio_grid_and_semantic_parts():
    allp=prompts()
    for sheet in SHEETS_2D:
        p=allp[sheet.filename]
        ratio=sheet.size[0]/sheet.size[1]
        expected="1:1" if abs(ratio-1)<.01 else "2:3" if abs(ratio-2/3)<.01 else "4:3"
        assert f"= {expected}" in p,sheet.filename
        assert "2 columns and 2 rows" in p
        for tile in sheet.tiles:
            assert tile.name in p

def test_wardrobe_layers_are_not_baked_into_body():
    p=prompts()
    assert "not body or arms" in p["sheet_body_outfit.png"]
    assert "OUTFIT_FRONT" in p["sheet_body_outfit.png"]
    assert "No outfit-specific sleeves" in p["sheet_arms_hands.png"]
    assert "의상 교체" in readme()

def test_3d_paired_views_and_square_face():
    allp=prompts()
    for sheet in VIEWS_3D:
        p=allp[sheet.filename]
        assert "= 4:3" in p
        assert "2 equal-width columns" in p
        for tile in sheet.tiles:
            assert tile.name.upper() in p
    assert "WIDTH:HEIGHT=1:1" in allp["face.png"]
