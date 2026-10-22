"""Install a real rendered DNA pendant over existing native neckwear FRONT layer.

Never claims a new independent physics rig; this is a non-destructive geometry-
preserving image replacement on the cloned, already-existing CC0 neckline rig.
"""
from __future__ import annotations
import argparse,io,json,math
from pathlib import Path
from zipfile import ZipFile
from PIL import Image,ImageDraw,ImageFilter
from tools.vts_rearchive_native_iris_trial import _pages,sha
from tools.vts_modern_editable_project import _external_client,_serve_local_mcp
from tools.vts_psd2live_modern import ensure_modern_psd2live
from tools.vts_psd2live import validate_psd2live_output

def paint_dna_pendant(original:Image.Image)->Image.Image:
    if original.size!=(150,255):raise ValueError("Expected pinned 150x255 neckwear source")
    S=4; W,H=original.size; canvas=original.resize((W*S,H*S),Image.Resampling.LANCZOS)
    def P(*box):return tuple(round(x*S) for x in box)
    body=Image.new("RGBA",canvas.size)
    p=ImageDraw.Draw(body)
    p.rounded_rectangle(P(32,70,116,210),radius=17*S,fill=(6,38,48,251),
        outline=(173,222,222,255),width=4*S)
    p.rounded_rectangle(P(39,78,110,200),radius=14*S,fill=(8,49,60,253),
        outline=(36,192,178,240),width=2*S)
    for x in range(43,106):
        t=(x-43)/62
        p.line(P(x,84,x,191),fill=(round(8+13*t),round(91-35*t),
               round(110-25*t),round(218+21*t)),width=S)
    ptsA=[];ptsB=[]
    for y in range(104,184,3):
        x=74+23*math.sin((y-104)/79*math.pi*3.2)
        ptsA.append((round(x*S),y*S))
        ptsB.append((round((148-x)*S),y*S))
    glowing=Image.new("RGBA",canvas.size)
    g=ImageDraw.Draw(glowing)
    g.line(ptsA,fill=(90,248,211,210),width=5*S,joint="curve")
    g.line(ptsB,fill=(245,128,203,210),width=5*S,joint="curve")
    canvas=Image.alpha_composite(canvas,glowing.filter(ImageFilter.GaussianBlur(4*S)))
    canvas=Image.alpha_composite(canvas,body)
    ornate=Image.new("RGBA",canvas.size)
    d=ImageDraw.Draw(ornate)
    d.line(ptsA,fill=(151,255,222,254),width=3*S,joint="curve")
    d.line(ptsB,fill=(251,163,225,254),width=3*S,joint="curve")
    for y in range(107,184,8):
        x1=74+23*math.sin((y-104)/79*math.pi*3.2)
        d.line(P(round(x1),y,round(148-x1),y),fill=(200,254,244,190),width=2*S)
    d.arc(P(42,88,90,196),100,260,fill=(220,252,254,150),width=3*S)
    d.line(P(49,92,50,161),fill=(255,255,255,115),width=2*S)
    d.rounded_rectangle(P(43,67,106,86),radius=5*S,fill=(34,50,62,255),
        outline=(192,229,222,255),width=3*S)
    d.rounded_rectangle(P(38,194,111,207),radius=5*S,fill=(32,56,61,255),
        outline=(185,228,226,255),width=2*S)
    for x in (48,99):d.ellipse(P(x,77,x+4,81),fill=(183,248,228,250))
    d.ellipse(P(70,57,80,67),fill=(35,57,68,255),outline=(213,239,235,255),width=2*S)
    canvas=Image.alpha_composite(canvas,ornate)
    return canvas.resize((W,H),Image.Resampling.LANCZOS)

def retarget_pendant(source_project:Path,painted_source_zip:Path,out:Path,*,
                     editor_root=None,serve=None,connect=None):
    source=Path(source_project).resolve(strict=True)
    out=Path(out).resolve()
    if source.suffix!=".psd2live":raise ValueError("Real project required")
    if out.exists() and any(out.iterdir()):raise ValueError("Output must be empty")
    original_sha=sha(source)
    root=ensure_modern_psd2live(editor_root)
    out.mkdir(parents=True)
    verdict={"status":"NOT_RUN","original_source_sha256":original_sha,
             "original_source_unchanged":False,"native_export_verified":False,
             "capsule_texture_inserted_into_actual_front_neckwear_layer":False,
             "independent_capsule_physics_completed":False,
             "high_end_rearchive_art_completed":False,
             "pose_test_passed":False}
    def write(): (out/"STATUS.json").write_text(json.dumps(verdict,ensure_ascii=False,
                                                  indent=2,default=str),encoding="utf-8")
    try:
        with ZipFile(painted_source_zip) as z:
            if z.testzip() is not None:raise ValueError("Source texture archive corrupt")
            mapping=json.loads(z.read("01_LAYER_MAPPING_TEMPLATE.json"))
            src=next(x for x in mapping["template_layers"] if x["source_layer_name"]=="neckwear")
            new_texture=paint_dna_pendant(Image.open(io.BytesIO(z.read(src["guide"]))).convert("RGBA"))
            texture=out/"REARCHIVE_DNA_CAPSULE_FRONT.png"
            new_texture.save(texture)
            xyxy=src["original_bbox_xyxy"]
            expected=(xyxy[0],xyxy[1],xyxy[2]-xyxy[0],xyxy[3]-xyxy[1])
        with (serve or _serve_local_mcp)(root,out/"mcp") as (endpoint,token,log):
            with (connect or _external_client)(root/"mcp_proxy.py",endpoint,token) as editor:
                opened=editor.edit("project_open",path=str(source))
                if not opened.get("state"):raise RuntimeError("PSD2Live project not opened")
                copy=out/"REARCHIVE_DNA_CAPSULE_EDITABLE.psd2live"
                editor.edit("project_save_as",path=str(copy))
                if not copy.is_file():raise RuntimeError("Failed to copy native source")
                rows=_pages(editor,"layers")
                matches=[x for x in rows if str(x.get("name","")).strip()=="neckwear · 前"]
                if len(matches)!=1:raise RuntimeError("Exact native front neckwear split layer not found")
                layer=matches[0].get("id")
                if not isinstance(layer,str):raise RuntimeError("Layer ID missing")
                actual=editor.call("layer_get_texture",{"layer_id":layer})[0]
                rect=actual.get("canvas_rect")
                if not isinstance(rect,dict):raise RuntimeError("No real layer registration")
                current=[float(rect[k]) for k in ("left","top","width","height")]
                if any(abs(v-e)>12 for v,e in zip(current,expected)):
                    raise RuntimeError(f"Native capsule registration diverges: {current} vs {expected}")
                prev=editor.state()
                editor.edit("layer_replace_image",layer_id=layer,path=str(texture),
                            fit="contain",rebuild_mesh=False)
                if editor.state()==prev:raise RuntimeError("Actual capsule texture not committed")
                verdict["capsule_texture_inserted_into_actual_front_neckwear_layer"]=True
                verdict["actual_rig_layer_id"]=layer
                editor.edit("project_save")
                native=out/"native"
                editor.edit("project_export_model",output_directory=str(native))
                checked=validate_psd2live_output(native,edition="pro")
                if not checked.get("runtime_references_valid") or not checked.get("model3_json"):
                    raise RuntimeError("Capsule MOC3 export invalid")
                if sha(source)!=original_sha:raise RuntimeError("Source project mutated")
                verdict.update(original_source_unchanged=True,native_export_verified=True,
                    editable_project=str(copy),model3_json=str(checked["model3_json"]),
                    status="ACTUAL_DNA_PENDANT_TEXTURE_IN_NECKWEAR_MESH_NATIVE_EXPORTED")
    finally:write()
    return verdict

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--painted-zip",type=Path,required=True)
    p.add_argument("--editor",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    x=p.parse_args()
    print(json.dumps(retarget_pendant(x.source,x.painted_zip,x.out,editor_root=x.editor),
                     ensure_ascii=False,indent=2))
if __name__=="__main__":main()
