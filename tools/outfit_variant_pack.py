"""Independent 2D wardrobe model: neutral 24-part avatar + four costume parts.

This builds an editor-riggable 28-part package (front, back, left/right
sleeves), NEVER a rigid prop and NEVER a live parameter-toggle. To wear a
different outfit, rebuild the 2D model from identical neutral base + garment.
"""
from __future__ import annotations
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import json

from PIL import Image
from tools.sheet_input_loader import (
    inspect_sheet_archive,convert_2d_sheet_pack,_tile_box,_valid_aspect,
    _upscale_to,MASTER,
)
from vtuber_pipeline.wardrobe_contract import GARMENT_SHEET,GARMENT_PARTS


def inspect_garment_image(filename: str) -> dict:
    path=Path(filename)
    if path.name != "outfit_variant.png":
        raise ValueError("Outfit filename must be exactly outfit_variant.png")
    with Image.open(path) as image:
        if image.format != "PNG" or image.mode != "RGBA":
            raise ValueError("Outfit must be a real RGBA PNG, never an RGB background")
        image.load()
        if not _valid_aspect(image.size, GARMENT_SHEET.size):
            raise ValueError(
                f"outfit_variant.png: expected WIDTH:HEIGHT 4:3 (got {image.size})"
            )
        for t in GARMENT_SHEET.tiles:
            alpha=image.crop(_tile_box(image.size,GARMENT_SHEET,t.row,t.col)).getchannel("A")
            if not alpha.getbbox():
                raise ValueError(f"outfit_variant.png: missing part {t.name}")
            if alpha.histogram()[255] >= alpha.width*alpha.height*.97:
                raise ValueError(
                    f"outfit_variant.png: {t.name} is almost fully opaque; "
                    "remove the painted/background grid first"
                )
        return {"file":path.name,"size":list(image.size),
                "parts":sorted(GARMENT_PARTS),"valid":True}


def build_dressed_2d_assets(base_zip: str, outfit_png: str,
                            output_dir: str, *, neural: bool=True,
                            upscaler=None) -> dict:
    """Return master and 28 full-canvas layer ZIP, preserving all base pixels.

    The neural checkpoint is loaded ONCE per disposable worker. Neither
    upscaling nor the atlas grid invents correct sleeve shape/occlusion.
    """
    inspect_sheet_archive(base_zip,"live2d")
    inspect_garment_image(outfit_png)
    folder=Path(output_dir)
    folder.mkdir(parents=True,exist_ok=True)
    if neural and upscaler is None:
        from tools.sheet_super_resolution import load_model,upscale_rgba
        model=load_model()
        upscaler=lambda im,factor:upscale_rgba(im,model,output_scale=factor)
    if upscaler is None:
        upscaler=lambda im,factor:im.resize(
            (im.width*factor,im.height*factor),Image.Resampling.LANCZOS
        )
    master,base_layers=convert_2d_sheet_pack(
        base_zip,str(folder/"base"),output_scale=2,
        neural=neural,upscaler=upscaler
    )
    final_size=(MASTER[0]*2,MASTER[1]*2)
    output=folder/"wearable_layers.internal.zip"
    temporary=output.with_suffix(".part")
    with Image.open(outfit_png) as im:
        sheet=im.copy()
    try:
        with ZipFile(base_layers) as existing,ZipFile(
                temporary,"w",compression=ZIP_DEFLATED,compresslevel=1) as layers:
            names=existing.namelist()
            if len(names)!=24 or len(set(names))!=24:
                raise RuntimeError("Base avatar is not the 24-layer neutral contract")
            if any(p+".png" in names for p in GARMENT_PARTS):
                raise RuntimeError("Permanent base layers contain garment artwork")
            for name in names:
                layers.writestr(name,existing.read(name))
            for tile in GARMENT_SHEET.tiles:
                cell=sheet.crop(_tile_box(sheet.size,GARMENT_SHEET,
                                          tile.row,tile.col))
                bbox=cell.getchannel("A").getbbox()
                assert bbox is not None  # validated already
                part=cell.crop(bbox)
                roi=tile.roi
                dx=(roi[2]-roi[0])*2/cell.width
                dy=(roi[3]-roi[1])*2/cell.height
                if abs(dx/dy-1)>.02:
                    raise ValueError(f"{tile.name}: garment tile distorted")
                x=roi[0]*2+round(bbox[0]*dx)
                y=roi[1]*2+round(bbox[1]*dy)
                target=(min(roi[2]*2-x,max(1,round(part.width*dx))),
                        min(roi[3]*2-y,max(1,round(part.height*dy))))
                refined=_upscale_to(part,target,upscaler,neural=neural)
                layer=Image.new("RGBA",final_size,(0,0,0,0))
                layer.paste(refined,(x,y))
                data=BytesIO()
                layer.save(data,"PNG")
                layers.writestr(tile.name+".png",data.getvalue())
                print("[outfit] rig layer "+tile.name+" -> "+
                      str(target)+" at "+str((x,y)),flush=True)
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    manifest=folder/"wearable_manifest.json"
    manifest.write_text(json.dumps({
        "schema":"vtuber/2d-outfit-v2",
        "master":master,"layers_zip":str(output),
        "permanent_base_parts":24,"independent_garment_parts":list(sorted(GARMENT_PARTS)),
        "total_parts":28,
        "runtime_toggle_supported":False,
        "dynamic_sleeves_require_motion_validation":True,
    },indent=2),encoding="utf-8")
    return {"front":master,"layers":str(output),"manifest":str(manifest)}
