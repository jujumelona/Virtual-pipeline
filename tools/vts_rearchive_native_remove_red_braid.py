"""Remove visible legacy red four-part braid from a *real* PSD2Live RE:ARCHIVE rig.

The Hiakari source hair 2 becomes back hair 2-1..4 in the native rig.
Clearing these four source-derived meshes with transparent RGBA preserves the
skeleton/keyforms of the rest of the model. Does not claim the final face or
garment matches the user's reference art.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path
from PIL import Image
from tools.vts_rearchive_native_iris_trial import _pages,sha
from tools.vts_modern_editable_project import _external_client,_serve_local_mcp
from tools.vts_psd2live_modern import ensure_modern_psd2live
from tools.vts_psd2live import validate_psd2live_output

OLD_RED_BRAID = tuple("back hair 2-"+str(n) for n in range(1,5))

def clear(source_project:Path,output:Path,*,editor_root=None,connect=None,serve=None):
    src=Path(source_project).resolve(strict=True)
    out=Path(output).resolve()
    if src.suffix!=".psd2live":raise ValueError("Real editable native project required")
    if out.exists() and any(out.iterdir()):raise ValueError("Fresh output directory required")
    root=ensure_modern_psd2live(editor_root);original=sha(src)
    out.mkdir(parents=True)
    state={"schema":"rearchive/native-red-braid-removal-v1","status":"NOT_RUN",
           "original_project_unchanged":False,"native_export_verified":False,
           "native_pose_qa_passed":False,"replaced_native_split_layers":[],
           "new_twin_tail_physics_inherited":True,
           "original_art_style_approved":False,"high_end_avatar_completed":False}
    def store():
        (out/"STATUS.json").write_text(json.dumps(state,ensure_ascii=False,
                                  indent=2,default=str),encoding="utf-8")
    try:
        with (serve or _serve_local_mcp)(root,out/"mcp") as (endpoint,token,log):
            with (connect or _external_client)(root/"mcp_proxy.py",endpoint,token) as editor:
                opened=editor.edit("project_open",path=str(src))
                if not opened.get("project_id"):raise RuntimeError("Rig parent did not open")
                clone=out/"REARCHIVE_NO_RED_BRAID_EDITABLE.psd2live"
                editor.edit("project_save_as",path=str(clone))
                if not clone.is_file():raise RuntimeError("No editable native clone")
                items=_pages(editor,"layers")
                for name in OLD_RED_BRAID:
                    rows=[x for x in items if str(x.get("name","")).strip().lower()==name]
                    if len(rows)!=1:raise RuntimeError("Required old red-braid section missing "+name)
                    handle=rows[0].get("id")
                    if not isinstance(handle,str):raise RuntimeError("Real section handle missing")
                    tex=editor.call("layer_get_texture",{"layer_id":handle})[0]
                    raster=tex.get("raster",{})
                    w,h=raster.get("width"),raster.get("height")
                    if type(w)!=int or type(h)!=int or not 2<=w<=4096 or not 2<=h<=4096:
                        raise RuntimeError("Invalid source split raster size "+str(raster))
                    png=out/(name.replace(" ","_")+"_transparent.png")
                    Image.new("RGBA",(w,h),(0,0,0,0)).save(png)
                    state_before=editor.state()
                    editor.edit("layer_replace_image",layer_id=handle,path=str(png),
                                fit="stretch",rebuild_mesh=False)
                    if editor.state()==state_before:raise RuntimeError("No real image edit for "+name)
                    state["replaced_native_split_layers"].append(
                        {"native_layer":name,"real_handle":handle,"mesh_preserved":True,
                         "new_alpha_max":0,"raster":[w,h]})
                editor.edit("project_save")
                target=out/"native"
                editor.edit("project_export_model",output_directory=str(target))
                checked=validate_psd2live_output(target,edition="pro")
                if not checked.get("runtime_references_valid") or not checked.get("model3_json"):
                    raise RuntimeError("Native export invalid after braid removal")
                if sha(src)!=original:raise RuntimeError("Input native model changed")
                state.update(status="ACTUAL_FOUR_RED_BRAID_SPLIT_TEXTURES_REMOVED_EDITABLE_MOC3_EXPORTED",
                             original_project_unchanged=True,native_export_verified=True,
                             editable_project=str(clone),model3_json=str(checked["model3_json"]))
    finally:store()
    return state

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--editor",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(clear(a.source,a.out,editor_root=a.editor),ensure_ascii=False,indent=2))
if __name__=="__main__": main()
