"""CPU-only full sheet ZIP/extraction tests; GPU model is mocked explicitly."""
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile, ZIP_STORED

from PIL import Image, ImageDraw
import pytest

from tools import sheet_input_loader as loader
from vtuber_pipeline.sheet_contract import Sheet, Tile, assert_contract, SHEETS_2D


def png(size, *, rgba=True, box=None):
    im = Image.new("RGBA" if rgba else "RGB", size, (0,0,0,0)
                   if rgba else (20,40,60))
    if box:
        ImageDraw.Draw(im).rectangle(box,fill=(50,100,150,255))
    buf = BytesIO()
    im.save(buf,format="PNG")
    return buf.getvalue()


def mini_layout(monkeypatch):
    monkeypatch.setattr(loader,"MASTER",(16,16))
    monkeypatch.setattr(loader,"FACE",(8,8))
    sheets=(
        Sheet("sheet_face.png",(8,4),2,1,(
            Tile("face",0,0,(8,0,12,4)),
            Tile("neck",0,1,(0,8,4,12)),
        )),
        Sheet("sheet_hair.png",(8,8),1,1,(
            Tile("hair_front",0,0,(0,0,8,8)),
        )),
        Sheet("sheet_body_outfit.png",(8,8),1,1,(
            Tile("body",0,0,(8,8,16,16)),
        )),
    )
    monkeypatch.setattr(loader,"SHEETS_2D",sheets)
    return sheets


def test_exact_26_tiles_and_fixed_roi_sizes():
    assert_contract()
    assert sum(len(s.tiles) for s in SHEETS_2D)==26
    for sheet in SHEETS_2D:
        assert sheet.cell_size[0] == sheet.size[0]//sheet.columns
        assert sheet.cell_size[1] == sheet.size[1]//sheet.rows
        for tile in sheet.tiles:
            assert (tile.roi[2]-tile.roi[0],tile.roi[3]-tile.roi[1])==sheet.cell_size


def test_2d_zip_is_strict_and_tiles_restore_absolute_coordinates(tmp_path,monkeypatch):
    mini_layout(monkeypatch)
    pack = tmp_path/"character_2d_sheet_pack.zip"
    # face tile=first 4x4, neck=second 4x4, each sparse alpha.
    face = Image.new("RGBA",(8,4),(0,0,0,0))
    face.putpixel((1,1),(255,0,0,255))
    face.putpixel((6,2),(0,255,0,255))
    f=BytesIO();face.save(f,"PNG")
    srcs={
        "front_master.png":png((16,16),box=(3,3,11,11)),
        "sheet_face.png":f.getvalue(),
        "sheet_hair.png":png((8,8),box=(2,2,3,3)),
        "sheet_body_outfit.png":png((8,8),box=(1,1,2,2)),
    }
    with ZipFile(pack,"w",ZIP_STORED) as z:
        for name,data in srcs.items():
            z.writestr("character_2d_sheet_pack/"+name,data)
    assert loader.inspect_sheet_archive(str(pack),"live2d")["verified"]
    master,parts = loader.convert_2d_sheet_pack(
        str(pack),str(tmp_path/"out"),output_scale=2,neural=False
    )
    assert Image.open(master).size == (32,32)
    with ZipFile(parts) as z:
        assert set(z.namelist())=={"face.png","neck.png",
                                   "hair_front.png","body.png"}
        with Image.open(z.open("face.png")) as layer:
            assert layer.size==(32,32)
            # face maps from tile (1,1) into master ROI origin=(8,0).
            assert layer.getpixel((18,2))[3]>0
            assert layer.getpixel((2,2))[3]==0
        with Image.open(z.open("neck.png")) as layer:
            assert layer.getpixel((4,20))[3]>0
            assert layer.getpixel((18,2))[3]==0


def test_zip_rejects_path_traversal_and_wrong_files(tmp_path):
    evil=tmp_path/"evil.zip"
    with ZipFile(evil,"w") as z:
        z.writestr("../sheet_face.png",png((16,16)))
    with pytest.raises(ValueError,match="Unsafe|unexpected"):
        loader.inspect_sheet_archive(str(evil),"live2d")
    assert not (tmp_path/"sheet_face.png").exists()


def test_zip_upload_requires_one_correct_archive(tmp_path):
    with pytest.raises(ValueError,match="exactly one"):
        loader.store_uploaded_zip({},str(tmp_path),"live2d")
    with pytest.raises(ValueError,match="requires ZIP filename"):
        loader.store_uploaded_zip({"character_3d_sheet_pack.zip":b"x"},
                                  str(tmp_path),"live2d")


def test_model_is_loaded_only_for_requested_neural_upscale(monkeypatch,tmp_path):
    mini_layout(monkeypatch)
    # No weights are touched by preflight or non-neural extraction.
    def crash():
        raise AssertionError("GPU weights should not load in upload cell")
    import tools.sheet_super_resolution as sr
    monkeypatch.setattr(sr,"load_model",crash)
    assert loader.sheet_names("3d")==frozenset({"face.png","sheet_body_views.png"})
    with pytest.raises(ValueError,match="Provide one"):
        loader.inspect_sheet_archive(str(tmp_path/"missing.png"),"3d")


def test_3d_view_sheet_lossless_crop(tmp_path,monkeypatch):
    mini = Sheet("sheet_body_views.png",(16,16),2,2,(
        Tile("front",0,0,(0,0,8,8)), Tile("back",0,1,(0,0,8,8)),
        Tile("left",1,0,(0,0,8,8)),Tile("right",1,1,(0,0,8,8)),
    ))
    monkeypatch.setattr(loader,"VIEWS_3D",mini)
    monkeypatch.setattr(loader,"FACE",(8,8))
    master=Image.new("RGB",(16,16))
    for cell,xy in enumerate(((0,0),(8,0),(0,8),(8,8)),start=1):
        ImageDraw.Draw(master).rectangle((xy[0],xy[1],xy[0]+7,xy[1]+7),
                                         fill=(cell*35,30,40))
    b=BytesIO();master.save(b,"PNG")
    pack=tmp_path/"character_3d_sheet_pack.zip"
    with ZipFile(pack,"w") as z:
        z.writestr("character_3d_sheet_pack/sheet_body_views.png",b.getvalue())
        z.writestr("character_3d_sheet_pack/face.png",png((8,8)))
    result=loader.convert_3d_sheet_pack(str(pack),str(tmp_path/"3d"))
    for n,i in zip(("front","back","left","right"),range(1,5)):
        with Image.open(result[n]) as im:
            assert im.size==(8,8)
            assert im.getpixel((3,3))==(i*35,30,40)
