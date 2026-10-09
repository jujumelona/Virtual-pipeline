"""Create a replaceable 2D outfit ZIP without modifying the original body.

Input: verified full character_2d_sheet_pack.zip plus NEW isolated garment
sheet (front/back clothing cells only). Base body, face, arms and hair are
copied unchanged. The result goes through the normal Colab sheet pipeline,
which re-builds/re-rigs the editable character; this is not a live outfit
toggle nor a per-sleeve skinning system.
"""
from __future__ import annotations
import argparse
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from PIL import Image
from tools.sheet_input_loader import (
    inspect_sheet_archive,_members,_read,_tile_box,_valid_aspect,
)
from vtuber_pipeline.sheet_contract import SHEETS_2D

OUTFIT="sheet_body_outfit.png"

def change_outfit(source_zip: str, new_outfit_png: str, result_zip: str) -> str:
    inspect_sheet_archive(source_zip,"live2d")
    sheet=next(s for s in SHEETS_2D if s.filename==OUTFIT)
    src=Path(source_zip).resolve()
    dest=Path(result_zip).resolve()
    if src==dest:
        raise ValueError("Output must not overwrite original sheet ZIP")
    with Image.open(new_outfit_png) as candidate:
        if candidate.format!="PNG" or candidate.mode!="RGBA":
            raise ValueError("New clothing sheet must be a truly transparent RGBA PNG")
        candidate.load()
        variant=candidate.copy()
    if not _valid_aspect(variant.size,sheet.size):
        raise ValueError("New clothing sheet needs a 4:3 canvas ratio")
    # Body cell must stay totally blank in the *new* sheet; it is supplied
    # solely by original ZIP. No change to skin/bodysuit is ever accepted.
    for row,col in ((0,0),(1,1)):
        box=_tile_box(variant.size,sheet,row,col)
        if variant.crop(box).getchannel("A").getbbox():
            raise ValueError(
                f"New outfit sheet row{row+1} col{col+1} must be FULLY "
                "transparent; body comes unchanged from original sheet"
            )
    for row,col in ((0,1),(1,0)):
        box=_tile_box(variant.size,sheet,row,col)
        alpha=variant.crop(box).getchannel("A")
        if not alpha.getbbox():
            raise ValueError("Both new outfit_front and outfit_back must be nonempty")
        if alpha.histogram()[255] >= alpha.width*alpha.height*.97:
            raise ValueError("Garment cell is a filled background, not transparent art")

    with ZipFile(src) as z:
        members=_members(z,"live2d")
        previous=_read(z,members,OUTFIT).convert("RGBA")
        # Retain higher native sampling where possible. The overall sheet
        # will receive AI SR only AFTER per-cell extraction in cell ⑤.
        target=(max(previous.width,variant.width),max(previous.height,variant.height))
        merged=Image.new("RGBA",target,(0,0,0,0))
        for row,col,sample in ((0,0,previous),(0,1,variant),(1,0,variant)):
            region=sample.crop(_tile_box(sample.size,sheet,row,col))
            x0,y0,x1,y1=_tile_box(target,sheet,row,col)
            if region.size!=(x1-x0,y1-y0):
                region=region.resize((x1-x0,y1-y0),Image.Resampling.LANCZOS)
            merged.paste(region,(x0,y0))
        payload=BytesIO()
        merged.save(payload,"PNG")
        dest.parent.mkdir(parents=True,exist_ok=True)
        temporary=dest.with_suffix(".pending")
        try:
            with ZipFile(temporary,"w",compression=ZIP_DEFLATED) as out:
                for name,item in members.items():
                    blob=payload.getvalue() if name==OUTFIT else z.read(item)
                    out.writestr("character_2d_sheet_pack/"+name,blob)
            inspect_sheet_archive(str(temporary),"live2d")
            temporary.replace(dest)
        finally:
            temporary.unlink(missing_ok=True)
    receipt=dest.with_suffix(".wardrobe.json")
    receipt.write_text(json.dumps({
        "mode":"rerig_required",
        "new_zip":str(dest),
        "unchanged_semantic_part":"body",
        "replaced_semantic_parts":["outfit_front","outfit_back"],
        "note":"Sleeves have no separate deformation meshes in v1; manual editor rigging may be needed",
    },ensure_ascii=False,indent=2),encoding="utf-8")
    return str(dest)


def main():
    parser=argparse.ArgumentParser(description="Replace outfit only in a full 2D sheet ZIP")
    parser.add_argument("--source",required=True,help="Original full character_2d_sheet_pack.zip")
    parser.add_argument("--outfit",required=True,help="New RGBA 2x2 garment-only PNG")
    parser.add_argument("--output",required=True,help="Destination full variant sheet ZIP")
    args=parser.parse_args()
    print(change_outfit(args.source,args.outfit,args.output),flush=True)

if __name__=="__main__":
    main()
