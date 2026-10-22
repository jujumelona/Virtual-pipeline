"""Stage 5: import two *new* black/white long twin-tail ArtMesh parts and rig sway.

Uses real CC0 high-resolution hair strand artwork as temporary texture source,
NOT a replacement for the user's detailed original RE:ARCHIVE illustrations.
Keeps eye, face, costume and DNA edits from stage 4. Every edit occurs inside
the real PSD2Live 3.6 project, not a screenshot compositor.
"""
from __future__ import annotations
import argparse, hashlib, io, json
from pathlib import Path
from zipfile import ZipFile
import numpy as np
from PIL import Image
from tools.vts_rearchive_native_iris_trial import _pages, sha
from tools.vts_modern_editable_project import _external_client, _serve_local_mcp
from tools.vts_psd2live_modern import ensure_modern_psd2live
from tools.vts_psd2live import validate_psd2live_output

SPECS=(("REARCHIVE_WHITE_TWINTAIL_L",[708,1050],True),
       ("REARCHIVE_BLACK_TWINTAIL_R",[1354,1050],False))
ORIGINAL_HAIR_TO_HIDE=("back hair 2","back hair 3")

def authored_tail(source:Image.Image, light:bool)->Image.Image:
    """Reuse actual rendered hair strands with a neutral B/W and mint palette."""
    original=source.convert("RGBA")
    if original.size[0]<150 or original.size[1]<300:
        raise ValueError("A genuine long raster hair strand is required")
    # Avoid low-quality full-canvas stretch: boost tail length only 1.5x.
    width=round(original.width*1.12)
    height=round(original.height*1.58)
    layer=original.resize((width,height),Image.Resampling.LANCZOS)
    raw=np.array(layer,dtype=np.uint8)
    rgba=raw.astype(np.float32)
    a=rgba[:,:,3]
    lum=(0.24*rgba[:,:,0]+0.68*rgba[:,:,1]+0.08*rgba[:,:,2])
    # Keep illustrated fine streaks and preserve alpha.
    if light:
        v=np.clip(166+lum*.35,172,254)
        r=v+4;g=v+9;b=v+10
        # Rare mint highlights along one edge, not a green costume.
        x=np.arange(width)[None,:]
        highlight=(x>round(width*.65))
        g=np.where(highlight,np.clip(g+12,0,255),g)
        r=np.where(highlight,np.clip(r-7,0,255),r)
        b=np.where(highlight,np.clip(b+4,0,255),b)
    else:
        v=np.clip(15+lum*.44,19,128)
        r=v;g=np.clip(v+13,0,255);b=np.clip(v+16,0,255)
        x=np.arange(width)[None,:]
        shine=(x<round(width*.30))
        g=np.where(shine,np.clip(g+19,0,255),g)
        b=np.where(shine,np.clip(b+11,0,255),b)
    image=np.zeros_like(raw)
    image[:,:,0]=np.uint8(np.clip(r,0,255))
    image[:,:,1]=np.uint8(np.clip(g,0,255))
    image[:,:,2]=np.uint8(np.clip(b,0,255))
    image[:,:,3]=raw[:,:,3]
    # LEFT/RIGHT heads get mirrored seam-aware appearance.
    out=Image.fromarray(image,"RGBA")
    return out.transpose(Image.Transpose.FLIP_LEFT_RIGHT) if light else out

def _get_id(rows,name):
    found=[r for r in rows if isinstance(r,dict) and
           str(r.get("name","")).strip().lower()==name.lower()]
    if len(found)!=1:raise RuntimeError(f"Native layer name not unique: {name}, found {len(found)}")
    ident=found[0].get("id") or found[0].get("layer_id")
    if not isinstance(ident,str) or not ident:raise RuntimeError("Native layer ID missing "+name)
    return ident

def _list_real_ids(res:dict)->list[str]:
    if not isinstance(res,dict):return []
    for key in ("affectedObjectIds","affected_object_ids","object_ids"):
        v=res.get(key)
        if isinstance(v,list):
            return [str(x) for x in v if isinstance(x,str)]
    for key in ("mutation","result"):
        v=res.get(key)
        if isinstance(v,dict):
            nested=_list_real_ids(v)
            if nested:return nested
    return []

def build(source_project:Path,edited_parts_zip:Path,output:Path,*,
          editor_root=None,connect=None,serve=None):
    project=Path(source_project).resolve(strict=True)
    output=Path(output).resolve()
    if project.suffix!=".psd2live":raise ValueError("Require existing native PSD2Live")
    if output.exists() and any(output.iterdir()):raise ValueError("Output must be empty")
    old_sha=sha(project)
    root=ensure_modern_psd2live(editor_root)
    output.mkdir(parents=True)
    verdict={"status":"NOT_RUN","old_native_sha256":old_sha,
       "original_source_untouched":False,"native_export_verified":False,
       "native_pose_qa_passed":False,"swing_physics_built":False,
       "new_twin_tail_parts":[],"old_braid_layers_hidden":[],
       "high_end_rearchive_identity_approved":False,
       "same_character_art_style_approved":False,
       "source_illustrations_replaced_by_cc0_temporary":True,
       "independent_dna_physics_done":False}
    def write():
        (output/"STATUS.json").write_text(json.dumps(verdict,ensure_ascii=False,
                                          indent=2,default=str),encoding="utf-8")
    try:
        with ZipFile(edited_parts_zip) as z:
            if z.testzip() is not None:raise RuntimeError("Painted CC0 pack corrupted")
            m=json.loads(z.read("01_LAYER_MAPPING_TEMPLATE.json"))
            if m.get("canvas")!=[2048,3072]:raise ValueError("Stage4 canvas mismatch")
            hair=next((x for x in m["template_layers"] if x["source_layer_name"]=="back hair 3"),None)
            if hair is None:raise RuntimeError("Real source hair3 missing")
            png=Image.open(io.BytesIO(z.read(hair["guide"]))).convert("RGBA")
            art={}
            for name,center,light in SPECS:
                f=output/(name+".png")
                sprite=authored_tail(png,light)
                sprite.save(f)
                art[name]={"path":f,"center":center,"size":sprite.size,"sha256":sha(f)}
        with (serve or _serve_local_mcp)(root,output/"mcp") as (endpoint,token,log):
            with (connect or _external_client)(root/"mcp_proxy.py",endpoint,token) as editor:
                opened=editor.edit("project_open",path=str(project))
                if not opened.get("project_id"):raise RuntimeError("Original native stage4 not opened")
                clone=output/"REARCHIVE_STAGE5_REAL_TWIN_TAILS.psd2live"
                editor.edit("project_save_as",path=str(clone))
                if not clone.is_file():raise RuntimeError("Native copy missing")
                inventory=_pages(editor,"layers")
                (output/"ACTUAL_STAGE4_SOURCE_LAYERS.json").write_text(
                   json.dumps(inventory,ensure_ascii=False,indent=2,default=str),
                   encoding="utf-8")
                def optional_layer(name):
                    matches=[x for x in inventory if isinstance(x,dict) and
                       str(x.get("name","")).strip().lower()==name]
                    if len(matches)>1:raise RuntimeError("Ambiguous native layer "+name)
                    if not matches:return None
                    return matches[0].get("id") or matches[0].get("layer_id")
                old_hide_ids=[(n,optional_layer(n)) for n in ORIGINAL_HAIR_TO_HIDE]
                anchor=optional_layer("back hair") or optional_layer("front hair")
                if not isinstance(anchor,str) or not anchor:
                    raise RuntimeError("No real known head anchor for new twin-tails")
                verdict["skipped_old_hair_names_not_in_live_rig"]=[
                    name for name,ident in old_hide_ids if ident is None]
                for orig_name,ident in old_hide_ids:
                    if ident is None:continue
                    meta=editor.call("layer_get_texture",{"layer_id":ident})[0]
                    raster=meta.get("raster")
                    if not isinstance(raster,dict):raise RuntimeError("Old hair raster missing")
                    w,h=raster.get("width"),raster.get("height")
                    if type(w)!=int or type(h)!=int or w<8 or h<8:raise RuntimeError("Old hair dimensions")
                    blank=output/(orig_name.replace(" ","_")+"_BLANK.png")
                    Image.new("RGBA",(w,h),(0,0,0,0)).save(blank)
                    before=editor.state()
                    editor.edit("layer_replace_image",layer_id=ident,path=str(blank),
                                fit="stretch",rebuild_mesh=False)
                    if editor.state()==before:raise RuntimeError("Existing braid unchanged")
                    verdict["old_braid_layers_hidden"].append({"name":orig_name,"id":ident,
                           "method":"RGBA transparent texture; original mesh preserved"})
                for name,point,light in SPECS:
                    result=editor.edit("layer_import_images",paths=[str(art[name]["path"])],
                                       at=point,anchor_layer_id=anchor,in_front=False)
                    after=_pages(editor,"layers")
                    if not any(str(x.get("name",""))==name for x in after):
                        raise RuntimeError("Actual imported tail absent from editor: "+name)
                    ids=_list_real_ids(result)
                    # The terminal import result's source-layer ID is not necessarily
                    # the drawable object ID. Require a real, distinct mesh object ID.
                    objects=_pages(editor,"objects")
                    recognized=[x for x in objects if isinstance(x,dict) and
                       (str(x.get("name",""))==name or
                        str(x.get("name","")).startswith(name))]
                    if len(recognized)!=1:
                        raise RuntimeError(f"Need unique imported drawable for swing: {name}, got {len(recognized)}")
                    mesh=recognized[0].get("target")
                    if not isinstance(mesh,str) or not mesh.startswith("mesh:"):
                        raise RuntimeError("PSD2Live workspace_inspect did not provide a real mesh:<id> target for "+name)
                    swing_id="RearchiveTailWhite" if light else "RearchiveTailBlack"
                    swing=editor.edit("swing_put",id=swing_id,name=name+" swaying hair",
                         targets=[mesh],kind="lateral",segments=2,
                         magnitude=0.18,softness=0.58,parallel=0.4,
                         fulcrum="top",preset="hair",physics_enabled=True)
                    if swing.get("applied") is False:raise RuntimeError("Swing rig not applied")
                    verdict["new_twin_tail_parts"].append(
                         {"name":name,"mesh_id":mesh,"swing_id":swing_id,
                          "png_sha256":art[name]["sha256"],"art_dimensions":art[name]["size"],
                          "center_on_canvas":point,"real_independent_mesh":True,
                          "physics_generated_by_upstream_editor":True})
                verdict["swing_physics_built"]=len(verdict["new_twin_tail_parts"])==2
                editor.edit("project_save")
                native=output/"native"
                editor.edit("project_export_model",output_directory=str(native))
                checked=validate_psd2live_output(native,edition="pro")
                if not checked.get("runtime_references_valid") or not checked.get("model3_json"):
                    raise RuntimeError("Native twin-tail MOC3 export failed")
                if sha(project)!=old_sha:raise RuntimeError("Source native project accidentally modified")
                verdict.update(status="REAL_INDEPENDENT_TWINTAIL_MESH_AND_SWING_RIG_EXPORTED_AESTHETIC_NOT_FINAL",
                   original_source_untouched=True,native_export_verified=True,
                   editable_project=str(clone),model3_json=str(checked["model3_json"]))
    finally:write()
    return verdict

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--source-project",type=Path,required=True)
    ap.add_argument("--edited-parts-zip",type=Path,required=True)
    ap.add_argument("--editor",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    print(json.dumps(build(a.source_project,a.edited_parts_zip,a.out,
                editor_root=a.editor),ensure_ascii=False,indent=2,default=str))

if __name__=="__main__":main()
