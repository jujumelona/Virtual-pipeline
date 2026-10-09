"""Compose neutral 2D avatar with independently authored hair and costumes.

The base has 20 permanent facial/body layers. A hairstyle and outfit each
contribute four additional RGBA layers. All combinations are supported:
20 base, 24 (base+hair or base+outfit), 28 (base+hair+outfit).
This produces re-riggable editable 2D artwork, NOT a broadcast-time toggle.
"""
from __future__ import annotations
import json
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from PIL import Image

from tools.sheet_input_loader import (
    inspect_sheet_archive, convert_2d_sheet_pack, _tile_box, _valid_aspect,
    _upscale_to, MASTER,
)
from vtuber_pipeline.hair_contract import HAIR_SHEET,HAIR_PARTS
from vtuber_pipeline.wardrobe_contract import GARMENT_SHEET,GARMENT_PARTS

ASSETS={"hair":(HAIR_SHEET,HAIR_PARTS),"outfit":(GARMENT_SHEET,GARMENT_PARTS)}

def inspect_image(source: str,kind: str) -> dict:
    if kind not in ASSETS:
        raise ValueError(f"Unknown removable part type: {kind}")
    layout,expected=ASSETS[kind]
    path=Path(source)
    if path.name!=layout.filename:
        raise ValueError(f"{kind}: filename must be exactly {layout.filename}")
    with Image.open(path) as im:
        if im.format!="PNG" or im.mode!="RGBA":
            raise ValueError(f"{layout.filename}: true RGBA transparent PNG is required")
        im.load()
        if not _valid_aspect(im.size,layout.size):
            raise ValueError(
                f"{layout.filename}: invalid WIDTH:HEIGHT {im.size}; "
                f"expected {layout.size[0]}:{layout.size[1]}"
            )
        if im.width<256 or im.height<256:
            raise ValueError("Source too small for rigging")
        for t in layout.tiles:
            alpha=im.crop(_tile_box(im.size,layout,t.row,t.col)).getchannel("A")
            if alpha.getbbox() is None:
                raise ValueError(f"{layout.filename}: missing separate {t.name}")
            if alpha.histogram()[255] >= alpha.width*alpha.height*.97:
                raise ValueError(
                    f"{layout.filename}: {t.name} contains a nearly opaque "
                    "background or full-cell fill, not isolated transparent art"
                )
        return {"file":path.name,"kind":kind,
                "size":list(im.size),"parts":sorted(expected),"valid":True}


def build_modular_2d_assets(base_zip: str, output_dir: str, *,
                            hair_png: str|None=None,
                            outfit_png: str|None=None,
                            neural: bool=True, upscaler=None) -> dict:
    if not hair_png and not outfit_png:
        raise ValueError("Provide hair_variant.png or outfit_variant.png")
    inspect_sheet_archive(base_zip,"live2d")
    selected=[]
    if hair_png:
        selected.append(("hair",hair_png))
    if outfit_png:
        selected.append(("outfit",outfit_png))
    for kind,path in selected:
        inspect_image(path,kind)
    folder=Path(output_dir)
    folder.mkdir(parents=True,exist_ok=True)
    if neural and upscaler is None:
        from tools.sheet_super_resolution import load_model,upscale_rgba
        model=load_model()
        upscaler=lambda image,mult: upscale_rgba(image,model,output_scale=mult)
    if upscaler is None:
        upscaler=lambda image,mult: image.resize(
            (image.width*mult,image.height*mult),
            Image.Resampling.LANCZOS
        )
    master,base_layers=convert_2d_sheet_pack(
        base_zip,str(folder/"neutral"),output_scale=2,
        neural=neural,upscaler=upscaler
    )
    canvas=(MASTER[0]*2,MASTER[1]*2)
    output=folder/"modular_layers.internal.zip"
    temp=output.with_suffix(".part")
    added=[]
    try:
        with ZipFile(base_layers) as old,ZipFile(
                temp,"w",compression=ZIP_DEFLATED,compresslevel=1) as dest:
            existing=old.namelist()
            if len(existing)!=20 or len(set(existing))!=20:
                raise RuntimeError("Expected 20 garment-free, hairstyle-free base layers")
            detachable=GARMENT_PARTS | HAIR_PARTS
            if any(n[:-4] in detachable for n in existing):
                raise ValueError("Base character improperly includes detachable hair or costume")
            for name in existing:
                dest.writestr(name,old.read(name))
            for kind,path in selected:
                layout,expected=ASSETS[kind]
                with Image.open(path) as source:
                    artwork=source.copy()
                for tile in layout.tiles:
                    cell=artwork.crop(_tile_box(artwork.size,layout,tile.row,tile.col))
                    bbox=cell.getchannel("A").getbbox()
                    if bbox is None:
                        raise ValueError(f"{kind}: empty {tile.name}")
                    part=cell.crop(bbox)
                    roi=tile.roi
                    dx=(roi[2]-roi[0])*2/cell.width
                    dy=(roi[3]-roi[1])*2/cell.height
                    if abs(dx/dy-1)>.02:
                        raise ValueError(f"{tile.name}: asymmetric resize / distortion")
                    x=roi[0]*2+round(bbox[0]*dx)
                    y=roi[1]*2+round(bbox[1]*dy)
                    target=(min(roi[2]*2-x,max(1,round(part.width*dx))),
                            min(roi[3]*2-y,max(1,round(part.height*dy))))
                    enhanced=_upscale_to(part,target,upscaler,neural=neural)
                    img=Image.new("RGBA",canvas,(0,0,0,0))
                    img.paste(enhanced,(x,y))
                    buf=BytesIO()
                    img.save(buf,"PNG")
                    dest.writestr(tile.name+".png",buf.getvalue())
                    added.append(tile.name)
                    print(f"[modular-2d] {tile.name} -> {target} @ ({x},{y})",
                          flush=True)
        temp.replace(output)
    finally:
        temp.unlink(missing_ok=True)
    manifest=folder/"modular_parts.json"
    manifest.write_text(json.dumps({
        "schema":"vtuber/modular-2d-v1",
        "master":master,"layers_zip":str(output),
        "permanent_base_parts":20,
        "detachable_hair_parts":4 if hair_png else 0,
        "detachable_outfit_parts":4 if outfit_png else 0,
        "total_parts":20+len(added),
        "parts":added,
        "needs_editor_motion_review":True,
        "live_hot_swap_ready":False,
    },ensure_ascii=False,indent=2),encoding="utf-8")
    return {"front":master,"layers":str(output),"manifest":str(manifest)}
