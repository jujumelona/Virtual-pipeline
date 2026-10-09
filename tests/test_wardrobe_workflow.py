"""CPU-only clothing workflows: never substitute rigid prop attachment."""
from __future__ import annotations
import json
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
import pytest
from PIL import Image, ImageDraw

from tools import wardrobe_handoff, outfit_variant_pack, sheet_input_loader
from vtuber_pipeline.sheet_contract import Sheet, Tile


def _png(image):
    buf=BytesIO()
    image.save(buf,"PNG")
    return buf.getvalue()


def test_2d_clothing_variant_preserves_original_skin(tmp_path,monkeypatch):
    spec=Sheet("sheet_body_outfit.png",(400,300),2,2,(
        Tile("body",0,0,(0,0,200,150)),
        Tile("outfit_front",0,1,(0,0,200,150)),
        Tile("outfit_back",1,0,(0,0,200,150)),
    ))
    monkeypatch.setattr(sheet_input_loader,"SHEETS_2D",(spec,))
    monkeypatch.setattr(sheet_input_loader,"MASTER",(400,600))
    monkeypatch.setattr(outfit_variant_pack,"SHEETS_2D",(spec,))
    monkeypatch.setattr(sheet_input_loader,"sheet_names",
                        lambda mode:frozenset({"front_master.png","sheet_body_outfit.png"}))
    master=Image.new("RGBA",(400,600),(0,0,0,0))
    ImageDraw.Draw(master).rectangle((120,45,240,370),
                                     fill=(70,65,55,255))
    existing=Image.new("RGBA",(400,300),(0,0,0,0))
    ImageDraw.Draw(existing).rectangle((40,25,150,130),fill=(90,90,90,255))
    ImageDraw.Draw(existing).rectangle((245,30,355,125),fill=(180,60,20,255))
    ImageDraw.Draw(existing).rectangle((40,180,170,250),fill=(180,60,20,255))
    new=Image.new("RGBA",(400,300),(0,0,0,0))
    ImageDraw.Draw(new).rectangle((245,30,355,125),fill=(40,185,30,255))
    ImageDraw.Draw(new).rectangle((40,180,170,250),fill=(40,80,230,255))
    base=tmp_path/"character_2d_sheet_pack.zip"
    with ZipFile(base,"w") as z:
        z.writestr("front_master.png",_png(master))
        z.writestr("sheet_body_outfit.png",_png(existing))
    changed=tmp_path/"outfit_variant.png"
    changed.write_bytes(_png(new))
    target=tmp_path/"variant/character_2d_sheet_pack.zip"
    result=outfit_variant_pack.change_outfit(str(base),str(changed),str(target))
    assert result==str(target)
    with ZipFile(target) as zip:
        assert set(Path(n).name for n in zip.namelist())=={
            "front_master.png","sheet_body_outfit.png"}
        original=zip.read("character_2d_sheet_pack/front_master.png")
        assert original==_png(master)
        with Image.open(BytesIO(zip.read("character_2d_sheet_pack/sheet_body_outfit.png"))) as merged:
            assert merged.getpixel((100,70))==(90,90,90,255), "base skin kept"
            assert merged.getpixel((270,70))==(40,185,30,255), "front outfit changed"
            assert merged.getpixel((100,200))==(40,80,230,255), "back outfit changed"
    receipt=json.loads(target.with_suffix(".wardrobe.json").read_text())
    assert receipt["mode"]=="rerig_required"
    assert receipt["unchanged_semantic_part"]=="body"


def test_2d_outfit_refuses_body_change(tmp_path,monkeypatch):
    spec=Sheet("sheet_body_outfit.png",(400,300),2,2,())
    monkeypatch.setattr(outfit_variant_pack,"SHEETS_2D",(spec,))
    item=Image.new("RGBA",(400,300),(10,10,10,255))
    path=tmp_path/"outfit_variant.png"
    path.write_bytes(_png(item))
    with pytest.raises(ValueError,match="body comes unchanged"):
        outfit_variant_pack.change_outfit(str(tmp_path/"dummy.zip"),
                                           str(path),str(tmp_path/"new.zip"))


def test_3d_xwear_handoff_is_explicitly_not_a_finished_vrm(tmp_path,monkeypatch):
    from tools import colab_native
    monkeypatch.setattr(colab_native,"_has_vrm_container",lambda p:True)
    vrm=tmp_path/"avatar.vrm"
    vrm.write_bytes(b"placeholder dummy rig for CPU contract test")
    clothing=tmp_path/"costume.xwear"
    clothing.write_bytes(b"opaque-xwear-file-content" * 16)
    output=tmp_path/"vroid_dressup_handoff.zip"
    result=wardrobe_handoff.prepare_vroid_dressup(
        str(vrm),str(clothing),str(output))
    assert result==str(output)
    with ZipFile(output) as z:
        assert set(z.namelist())=={
            "base_avatar.vrm","costume.xwear",
            "manifest.json","VRoid_wardrobe_steps.txt"}
        manifest=json.loads(z.read("manifest.json"))
        assert manifest["status"]=="editor_import_required"
        assert not manifest["vrm_exported"]
        assert not manifest["automated_fitting_or_skinning"]
        assert not manifest["compatibility_verified_in_editor"]


def test_3d_wardrobe_refuses_png_masquerading_as_fitted_outfit(tmp_path,monkeypatch):
    from tools import colab_native
    monkeypatch.setattr(colab_native,"_has_vrm_container",lambda p:True)
    v=tmp_path/"avatar.vrm"
    v.write_bytes(b"test vrm")
    png=tmp_path/"costume.png"
    png.write_bytes(b"0"*256)
    with pytest.raises(ValueError,match="REAL .xwear"):
        wardrobe_handoff.prepare_vroid_dressup(
            str(v),str(png),str(tmp_path/"handoff.zip"))
