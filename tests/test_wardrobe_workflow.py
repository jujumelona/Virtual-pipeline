"""CPU-level 2D wardrobe contract and honest 3D XWear handoff."""
from __future__ import annotations
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
import json
import pytest
from PIL import Image,ImageDraw

from tools import wardrobe_handoff,outfit_variant_pack
from vtuber_pipeline.wardrobe_contract import GARMENT_PARTS,GARMENT_SHEET

def _png(image):
    b=BytesIO();image.save(b,"PNG");return b.getvalue()

def test_2d_four_garment_parts_are_separate():
    assert GARMENT_PARTS=={
        "outfit_front","outfit_back",
        "outfit_sleeve_left","outfit_sleeve_right"
    }
    assert GARMENT_SHEET.columns==2 and GARMENT_SHEET.rows==2

def test_outfit_png_rejects_missing_or_rgb_background(tmp_path):
    source=tmp_path/"outfit_variant.png"
    Image.new("RGB",(800,600),"white").save(source)
    with pytest.raises(ValueError,match="RGBA"):
        outfit_variant_pack.inspect_garment_image(str(source))
    image=Image.new("RGBA",(800,600),(0,0,0,0))
    ImageDraw.Draw(image).rectangle((20,20,40,60),fill=(70,80,90,255))
    image.save(source)
    with pytest.raises(ValueError,match="outfit_back"):
        outfit_variant_pack.inspect_garment_image(str(source))

def test_garment_4_cells_normalized_and_base_unmodified(tmp_path,monkeypatch):
    """Verify the actual modular compositor; no fake old facade internals."""
    from tools import modular_avatar_pack as modular
    from vtuber_pipeline.sheet_contract import Sheet, Tile

    fake=Sheet("outfit_variant.png",(512,256),2,2,(
        Tile("outfit_front",0,0,(0,10,64,42)),
        Tile("outfit_back",0,1,(0,10,64,42)),
        Tile("outfit_sleeve_left",1,0,(0,20,64,52)),
        Tile("outfit_sleeve_right",1,1,(0,20,64,52)),
    ))
    monkeypatch.setattr(modular,"MASTER",(64,64))
    monkeypatch.setitem(modular.ASSETS,"outfit",(fake,GARMENT_PARTS))
    monkeypatch.setattr(modular,"_valid_aspect",lambda size,target:True)
    monkeypatch.setattr(modular,"inspect_sheet_archive",lambda *a,**kw:None)

    original=Image.new("RGBA",(128,128),(0,0,0,0))
    ImageDraw.Draw(original).rectangle((18,20,38,66),fill=(30,60,100,255))
    base=tmp_path/"base_layers.zip"
    with ZipFile(base,"w") as z:
        for i in range(20):
            z.writestr(f"part_{i}.png",_png(original))

    def fake_convert(*args,**kwargs):
        return str(tmp_path/"front_master.png"),str(base)
    monkeypatch.setattr(modular,"convert_2d_sheet_pack",fake_convert)
    source=tmp_path/"character_2d_sheet_pack.zip"
    source.write_bytes(b"mock source - preflight is patched for CPU test")
    garment=Image.new("RGBA",(512,256),(0,0,0,0))
    for tile in fake.tiles:
        x0,y0,x1,y1=fake.box(tile)
        ImageDraw.Draw(garment).rectangle(
            (x0+8,y0+4,x0+18,y0+12),
            fill=(130,20+20*tile.col,60,255)
        )
    costume=tmp_path/"outfit_variant.png"
    costume.write_bytes(_png(garment))

    generated=outfit_variant_pack.build_dressed_2d_assets(
        str(source),str(costume),str(tmp_path/"output"),neural=False
    )
    with ZipFile(generated["layers"]) as z:
        assert len(z.namelist())==24
        assert z.read("part_0.png")==_png(original)
        for part in GARMENT_PARTS:
            im=Image.open(BytesIO(z.read(part+".png")))
            assert im.size==(128,128)
            assert im.getchannel("A").getbbox() is not None
    m=json.loads(Path(generated["manifest"]).read_text())
    assert m["permanent_base_parts"]==20
    assert m["detachable_outfit_parts"]==4
    assert m["total_parts"]==24
    assert not m["live_hot_swap_ready"]


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
    v=tmp_path/"avatar.vrm";v.write_bytes(b"test vrm")
    png=tmp_path/"costume.png";png.write_bytes(b"0"*256)
    with pytest.raises(ValueError,match="REAL .xwear"):
        wardrobe_handoff.prepare_vroid_dressup(str(v),str(png),str(tmp_path/"handoff.zip"))
