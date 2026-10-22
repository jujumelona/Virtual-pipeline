"""Make ACTUAL recolored source-part PNGs from pinned Hiakari CC0 painting guides.

This is a RE:ARCHIVE palette/texture feasibility prototype; it is NOT the
user's finished high-detail original avatar, a converted PSD2Live rig, or
proof of retained simulation. The original project is never modified.
"""
from __future__ import annotations
from pathlib import Path
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED
import argparse
import json
import numpy as np
from PIL import Image, ImageDraw

def _hue(im: Image.Image, role: str, name: str) -> Image.Image:
    rgba = np.array(im.convert("RGBA"))
    hsv = np.array(im.convert("RGB").convert("HSV")).astype(np.float32)
    h,s,v = hsv[:,:,0],hsv[:,:,1],hsv[:,:,2]
    alpha=rgba[:,:,3]>8
    if role=="eyes" and name.startswith("irides"):
        h[:]=115   # Pillow hue 0..255, mint green
        s[:]=np.clip(s*.70+58,0,255)
        v[:]=np.clip(v*.97+20,0,255)
    elif role in ("hair","ornament"):
        x=np.arange(im.width)[None,:]
        half=x>im.width//2
        half=np.repeat(half,im.height,axis=0)
        dark=alpha & (half | name in ("back hair 2","front hair 2"))
        v[dark]=np.clip(v[dark]*.23+20,0,255)
        s[dark]=np.clip(s[dark]*.48+10,0,255)
        red=((h<20)|(h>230))&(s>65)&alpha&~dark
        h[red]=113;s[red]=np.clip(s[red]*.68,0,255)
    elif role=="cloth":
        red=((h<20)|(h>230))&(s>45)&alpha
        h[red]=177
        s[red]=np.clip(s[red]*.46,0,255)
        v[red]=np.clip(v[red]*.28+18,0,255)
    else:
        return im
    recolored=Image.fromarray(np.uint8(np.clip(hsv,0,255)),"HSV").convert("RGB")
    recolored.putalpha(Image.fromarray(rgba[:,:,3]))
    return recolored

def _bow(size):
    w,h=size;mult=3
    art=Image.new("RGBA",(w*mult,h*mult))
    d=ImageDraw.Draw(art,"RGBA")
    cx=w*mult//2;cy=int(h*mult*.28);r=max(12,int(w*mult*.36))
    for sign,color in [(-1,(243,144,196,255)),(1,(123,226,203,255))]:
        pts=[(cx,cy),(cx+sign*r,cy-int(r*.5)),(cx+sign*r,cy+int(r*.5)),(cx,cy+int(r*.2))]
        d.polygon(pts,fill=color);d.line(pts+[pts[0]],fill=(65,55,77,255),width=5)
        d.polygon([(cx,cy),(cx+sign*r*.2,cy+h*mult*.36),
                   (cx+sign*r*.55,cy+h*mult*.6)],fill=color)
    d.ellipse((cx-20,cy-20,cx+20,cy+20),fill=(45,50,65,255),
              outline=(176,255,229,255),width=6)
    return art.resize((w,h),Image.Resampling.LANCZOS)

def _capsule(size):
    w,h=size;mult=3
    art=Image.new("RGBA",(w*mult,h*mult));d=ImageDraw.Draw(art,"RGBA")
    x=w*mult//2;y=h*mult//3;r=max(19,w*mult//5)
    d.rounded_rectangle((x-r,y,x+r,y+h*mult*.45),radius=r//2,
                        fill=(40,169,166,215),outline=(197,242,234,255),width=7)
    import math
    top=int(y+15);bottom=int(y+h*mult*.4)
    for phase,color in [(0,(173,255,225,255)),(math.pi,(240,148,213,255))]:
        points=[(int(x+math.sin((y-top)/max(1,bottom-top)*math.pi*3+phase)*r*.66),y)
                 for y in range(top,bottom,4)]
        d.line(points,fill=color,width=8,joint="curve")
    return art.resize(size,Image.Resampling.LANCZOS)

def repaint(guide_zip: Path, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True,exist_ok=True)
    z0=ZipFile(guide_zip)
    # GitHub Actions artifacts wrap the actual ZIP in one entry.
    names=z0.namelist()
    if len(names)==1 and names[0].lower().endswith(".zip"):
        z=ZipFile(BytesIO(z0.read(names[0])))
    else:z=z0
    m=json.loads(z.read("01_LAYER_MAPPING_TEMPLATE.json"))
    source=m["template_layers"]; canvas=tuple(m["canvas"])
    if canvas!=(2048,3072) or len(source)!=33:
        raise ValueError("Pinned 33-layer Hiakari final PSD is required")
    edited={}; after=Image.new("RGBA",canvas);before=Image.new("RGBA",canvas)
    replacements={}
    for item in source:
        name=item["source_layer_name"]
        src=Image.open(BytesIO(z.read(item["guide"]))).convert("RGBA")
        box=item["original_bbox_xyxy"]
        if src.size!=(box[2]-box[0],box[3]-box[1]):
            raise ValueError("PSD source layer rectangle mismatch")
        role=item["inferred_role"]
        if name.startswith("tail ") or name.startswith("ears-"):
            out=Image.new("RGBA",src.size)
            edited[name]="hidden animal appendage; requires independent hair/ornament rig"
        elif name.startswith("headwear"):
            out=_bow(src.size);edited[name]="pink/mint bow replacement (new painted pixels)"
        elif role in ("eyes","hair","cloth","ornament"):
            out=_hue(src,role,name)
            edited[name]="actual texture pixels transformed"
        else:out=src.copy()
        if name=="neckwear":
            out=Image.alpha_composite(out,_capsule(src.size))
            edited[name]="chest DNA capsule painted onto original neckwear rectangle"
        before.alpha_composite(src,tuple(box[:2]))
        after.alpha_composite(out,tuple(box[:2]))
        buffer=BytesIO();out.save(buffer,"PNG")
        replacements[item["guide"]]=buffer.getvalue()
    def preview(im):
        bg=Image.new("RGBA",canvas,(40,44,55,255))
        bg.alpha_composite(im)
        return bg.convert("RGB").resize((512,768),Image.Resampling.LANCZOS)
    compared=Image.new("RGB",(1024,768))
    compared.paste(preview(before),(0,0))
    compared.paste(preview(after),(512,0))
    compared.save(output_dir/"ACTUAL_BEFORE_AFTER.jpg",quality=94)
    after.save(output_dir/"ACTUAL_PART_COMPOSITE.png")
    verdict={"schema":"rearchive/cc0-repaint-preview-v1",
             "source":"actual Hiakari CC0 separated final PSD layers",
             "canvas":list(canvas),"layer_count":len(source),
             "painted_or_hidden_layers":len(edited),
             "source_layer_canvas_rects_preserved":True,
             "native_rig_project_was_edited":False,
             "user_character_design_match_verified":False,
             "high_end_art_quality_passed":False,
             "native_movement_verified":False,
             "status":"ACTUAL_ART_REPAINT_PROTOTYPE_NOT_FINAL_VTUBER",
             "changes":edited}
    with ZipFile(output_dir/"REARCHIVE_ACTUAL_33_LAYER_PAINTINGS.zip","w",
                 ZIP_DEFLATED,compresslevel=4) as outzip:
        for name,data in replacements.items():outzip.writestr(name,data)
        outzip.writestr("01_LAYER_MAPPING_TEMPLATE.json",json.dumps(m,ensure_ascii=False))
        outzip.writestr("02_UNFINISHED_STATUS.json",json.dumps(verdict,ensure_ascii=False))
        assert outzip.testzip() is None
    (output_dir/"STATUS.json").write_text(json.dumps(verdict,ensure_ascii=False,indent=2),
                                         encoding="utf-8")
    return verdict

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source-guides",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    result=repaint(args.source_guides,args.out)
    print(json.dumps({k:v for k,v in result.items() if k!="changes"},ensure_ascii=False))
if __name__=="__main__":main()
