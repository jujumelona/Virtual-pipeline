"""Attempt a REAL, non-destructive PSD2Live CC0 rig texture swap (2 mint eyes).

This is an intentionally bounded proof of existing mesh/keyform reuse.
It cannot certify the RE:ARCHIVE character's full art, tail, garment or physics.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile
from tools.vts_reference_keyform_author import _run_mcp, _require_mcp_cli

def sha(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for chunk in iter(lambda:f.read(1<<20),b""):h.update(chunk)
    return h.hexdigest()

def value(reply):
    d=reply["response"]
    if not isinstance(d,dict) or d.get("ok") is False:raise ValueError("Invalid MCP result")
    if "data" in d and isinstance(d["data"],dict):
        d=d["data"].get("result",d["data"])
    return d

def candidates(data):
    found=[]
    def scan(obj):
        if isinstance(obj,dict):
            name=obj.get("name")
            ident=obj.get("id") or obj.get("layer_id")
            if isinstance(name,str) and isinstance(ident,str):
                found.append((name.lower().strip(),ident))
            for x in obj.values():scan(x)
        elif isinstance(obj,list):
            for x in obj:scan(x)
    scan(data)
    return found

def apply(source:Path, edited_zip:Path, editor:Path, output:Path):
    source=source.resolve(strict=True)
    edited_zip=edited_zip.resolve(strict=True)
    if source.suffix!=".psd2live":raise ValueError("Must start with real source project")
    output=output.resolve()
    if output.exists() and list(output.iterdir()):raise ValueError("Output must be empty")
    output.mkdir(parents=True,exist_ok=True)
    _require_mcp_cli(editor)
    original_sha=sha(source)
    with ZipFile(edited_zip) as z:
        if z.testzip() is not None:raise ValueError("corrupt edit ZIP")
        manifest=json.loads(z.read("01_LAYER_MAPPING_TEMPLATE.json"))
        if manifest.get("canvas")!=[2048,3072]:
            raise ValueError("wrong source canvas")
        target={}
        for name in ("irides-r","irides-l"):
            item=next(i for i in manifest["template_layers"] if i["source_layer_name"]==name)
            filename=item["guide"]
            file=output/(name+".png")
            file.write_bytes(z.read(filename))
            target[name]={"file":file,"bbox":item["original_bbox_xyxy"]}
    results=[]
    results.append(_run_mcp(editor,"project_open",{"path":str(source)},
                            output/"00_open"))
    clone=output/"REARCHIVE_MINT_IRIS_TRIAL.psd2live"
    results.append(_run_mcp(editor,"project_save_as",{"path":str(clone)},
                            output/"01_clone"))
    if not clone.is_file():raise RuntimeError("Project clone was not saved")
    info=_run_mcp(editor,"workspace_inspect",{"scope":"layers"},
                  output/"02_layers")
    found=candidates(value(info))
    results.append(info)
    edited=[]
    for k,item in target.items():
        matched=set(ident for name,ident in found if name==k)
        if len(matched)!=1:
            raise RuntimeError(f"Expected unique real MCP ID for {k}, got {matched}")
        ident=next(iter(matched))
        geometry=_run_mcp(editor,"layer_get_texture",{"layer_id":ident},
                          output/("03_texture_"+k))
        d=value(geometry)
        rect=d.get("canvas_rect")
        if isinstance(rect,dict):
            rect=[rect.get(n) for n in ("x","y","width","height")]
        xyxy=item["bbox"]
        expected=[xyxy[0],xyxy[1],xyxy[2]-xyxy[0],xyxy[3]-xyxy[1]]
        if not isinstance(rect,list) or len(rect)!=4 or any(
            abs(float(a)-float(b))>3 for a,b in zip(rect,expected)
        ):
            raise RuntimeError(f"Native project rect mismatch {k}: {rect} vs {expected}")
        results.append(geometry)
        x=_run_mcp(editor,"layer_replace_image",
                   {"layer_id":ident,"path":str(item["file"]),
                    "fit":"contain","rebuild_mesh":False},
                   output/("04_replace_"+k))
        results.append(x)
        edited.append({"layer_name":k,"actual_layer_id":ident,
                       "new_png_sha256":sha(item["file"]),
                       "requested_mesh_rebuild":False})
    results.append(_run_mcp(editor,"project_save",{},output/"05_save"))
    native=output/"native_export"
    results.append(_run_mcp(editor,"project_export_model",{
        "output_directory":str(native)},output/"06_native"))
    model3=list(native.rglob("*.model3.json"))
    if not model3:raise RuntimeError("NO_REAL_NATIVE_MODEL_EXPORTED")
    if sha(source)!=original_sha:raise RuntimeError("Original CC0 project changed!")
    out={"status":"REAL_CC0_MINT_EYE_REPLACEMENT_PROJECT_EXPORTED_UNREVIEWED",
         "source_sha256":original_sha,"source_preserved":True,
         "actual_mcp_layer_replacements":edited,
         "new_project":str(clone),"native_models":[str(p) for p in model3],
         "eye_mesh_rebuild_requested":False,
         "native_pose_qa_passed":False,
         "high_end_REARCHIVE_complete":False,
         "twin_tail_and_DNA_physics_verified":False,
         "vtube_studio_tested":False}
    (output/"ACTUAL_MCP_RESULT.json").write_text(
        json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    return out

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source-project",type=Path,required=True)
    p.add_argument("--edited-zip",type=Path,required=True)
    p.add_argument("--editor",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(apply(a.source_project,a.edited_zip,a.editor,a.out),indent=2))
if __name__=="__main__":main()
