"""Actually replace two mint irises in a preserved CC0 PSD2Live rig via v3.6 MCP.

Requires original project, actual sprite PNG files from a pinned PSD and the
official upstream editor. Outputs actual editable project + native export when
successful; never declares full RE:ARCHIVE character art complete.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile
from tools.vts_modern_editable_project import _external_client, _serve_local_mcp
from tools.vts_psd2live_modern import ensure_modern_psd2live
from tools.vts_psd2live import validate_psd2live_output

def sha(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for chunk in iter(lambda:f.read(1<<20),b""):h.update(chunk)
    return h.hexdigest()

def _pages(editor,scope):
    items=[];offset=0
    while True:
        raw=editor.call("workspace_inspect",{"scope":scope,"offset":offset,"limit":64})[0]
        if not isinstance(raw,dict) or not isinstance(raw.get("items"),list):
            raise RuntimeError("Expected real PSD2Live paginated "+scope+" inventory")
        items.extend(raw["items"])
        nxt=raw.get("next")
        if nxt is None:break
        if not isinstance(nxt,int) or nxt<=offset:raise RuntimeError("MCP paging broken")
        offset=nxt
    return items

def retarget(source_project,edited_zip,output,*,editor_root=None,connect=None,serve=None):
    project=Path(source_project).resolve(strict=True)
    output=Path(output).resolve()
    if project.suffix!=".psd2live":raise ValueError("Real editable project required")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Retarget requires empty output directory")
    root=ensure_modern_psd2live(editor_root)
    original=sha(project)
    output.mkdir(parents=True)
    with ZipFile(edited_zip) as z:
        if z.testzip() is not None:raise ValueError("Edited PNG ZIP corrupt")
        manifest=json.loads(z.read("01_LAYER_MAPPING_TEMPLATE.json"))
        if manifest.get("canvas")!=[2048,3072]:raise ValueError("Wrong original canvas")
        sources={}
        for n in ("irides-r","irides-l"):
            row=next(x for x in manifest["template_layers"] if x["source_layer_name"]==n)
            part=output/(n+".png")
            part.write_bytes(z.read(row["guide"]))
            sources[n]=(part,row["original_bbox_xyxy"])
    verdict={
        "status":"NOT_RUN","original_source_sha256":original,
        "source_project_unchanged":False,"project_opened":False,
        "editable_copy_produced":False,"replacements":[],
        "native_export_verified":False,
        "original_character_design_complete":False,
        "full_rearchive_rig_complete":False,
        "native_pose_qa_passed":False
    }
    def store():
        (output/"NATIVE_TRIAL_STATUS.json").write_text(
            json.dumps(verdict,ensure_ascii=False,indent=2,default=str),
            encoding="utf-8")
    try:
        with (serve or _serve_local_mcp)(root,output/"mcp") as (endpoint,token,log):
            with (connect or _external_client)(root/"mcp_proxy.py",endpoint,token) as editor:
                opened=editor.edit("project_open",path=str(project))
                if not opened.get("state") or not opened.get("project_id"):
                    raise RuntimeError("Native CC0 project did not open")
                verdict["project_opened"]=True
                copied=output/"REARCHIVE_MINT_EYES_ACTUAL_RIG.psd2live"
                created=editor.edit("project_save_as",path=str(copied))
                if not copied.is_file() or not created.get("state"):
                    raise RuntimeError("Clone of original CC0 rig not written")
                verdict["editable_copy_produced"]=True
                actual=_pages(editor,"layers")
                (output/"ACTUAL_NATIVE_SOURCE_LAYERS.json").write_text(
                    json.dumps(actual,ensure_ascii=False,indent=2,default=str),
                    encoding="utf-8")
                def layer_id(row):
                    for key in ("layer_id","id","target"):
                        raw=row.get(key)
                        if isinstance(raw,str) and raw:
                            return raw
                    return None
                for name,(png,xyxy) in sources.items():
                    matches=[x for x in actual if isinstance(x,dict)
                             and str(x.get("name","")).strip().lower()==name]
                    if len(matches)!=1:raise RuntimeError(
                        "Actual MCP project did not provide unique layer "+name)
                    handle=layer_id(matches[0])
                    if handle is None:raise RuntimeError("Missing native layer ID: "+name)
                    info=editor.call("layer_get_texture",{"layer_id":handle})[0]
                    if not isinstance(info,dict):raise RuntimeError("No layer texture info")
                    rect=info.get("canvas_rect")
                    if isinstance(rect,dict):
                        rect=[rect.get(k) for k in ("left","top","width","height")]
                    expected=[xyxy[0],xyxy[1],xyxy[2]-xyxy[0],xyxy[3]-xyxy[1]]
                    if not isinstance(rect,list) or len(rect)!=4 or any(x is None for x in rect) or any(
                        abs(float(a)-float(b))>3 for a,b in zip(rect,expected)
                    ):
                        raise RuntimeError(f"Real mesh registration mismatch {name} {rect} vs {expected}")
                    before=editor.state()
                    editor.edit("layer_replace_image",layer_id=handle,path=str(png),
                                fit="contain",rebuild_mesh=False)
                    after=editor.state()
                    if after==before:raise RuntimeError("No actual native model change")
                    verdict["replacements"].append({
                        "real_layer_id":handle,"source_layer_name":name,
                        "png_sha256":sha(png),"geometry_rebuilt":False})
                editor.edit("project_save")
                export=output/"native"
                editor.edit("project_export_model",output_directory=str(export))
                checked=validate_psd2live_output(export,edition="pro")
                if not checked.get("runtime_references_valid") or not checked.get("model3_json"):
                    raise RuntimeError("Native model export failed integrity")
                if sha(project)!=original:raise RuntimeError("Original CC0 project was modified")
                verdict.update(status="REAL_CC0_MINT_EYE_EDITABLE_RIG_EXPORTED_NEEDS_ART_QA",
                    source_project_unchanged=True,native_export_verified=True,
                    model3_json=checked["model3_json"],editable=str(copied))
    finally:store()
    return verdict

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source-project",type=Path,required=True)
    p.add_argument("--edited-zip",type=Path,required=True)
    p.add_argument("--editor",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(retarget(a.source_project,a.edited_zip,a.out,
                  editor_root=a.editor),indent=2,default=str))
if __name__=="__main__":main()
