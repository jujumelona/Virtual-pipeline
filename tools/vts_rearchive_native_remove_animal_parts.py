"""Actually strip visible animal anatomy from the stage-2 native PSD2Live rig.

Four unsplit authoring source layers are DELETED. Two externally visible
split tail2 layers cannot be deleted by the upstream v3.6 API, so they are
replaced with transparent RGBA textures while preserving their mesh.
Never misreport these two as deleted or as native model budget reductions.
"""
from __future__ import annotations
import argparse,io,json
from pathlib import Path
from zipfile import ZipFile
from PIL import Image
from tools.vts_rearchive_native_iris_trial import _pages,sha
from tools.vts_modern_editable_project import _external_client,_serve_local_mcp
from tools.vts_psd2live_modern import ensure_modern_psd2live
from tools.vts_psd2live import validate_psd2live_output

DELETE_SOURCE=("ears-r","ears-l","tail 1","tail 3")
HIDE_SPLIT=("tail 2-t","tail 2-b")
REMOVED_VISUALLY=DELETE_SOURCE+HIDE_SPLIT

def source_layer_ids(source:Path)->dict[str,str]:
    mappings=[]
    with ZipFile(source) as archive:
        paths=[x for x in archive.namelist()
               if x.startswith("document/nodes/generation-source/") and x.endswith(".json")]
        if not paths:raise RuntimeError("Source id metadata absent")
        for path in paths:
            src=json.loads(archive.read(path))["value"]["generationSource"]["layers"]
            mappings.append({str(l["name"]).strip().lower():l["id"] for l in src})
    for name in DELETE_SOURCE:
        values={m.get(name) for m in mappings}
        if len(values)!=1 or None in values:raise RuntimeError(
            f"Ambiguous real source ID for {name}: {values}")
    ids={name:mappings[0][name] for name in DELETE_SOURCE}
    if len(set(ids.values()))!=len(ids):raise RuntimeError("Nonunique source layer IDs")
    return ids

def remove_animals(source_project:Path,output:Path,*,editor_root=None,connect=None,serve=None):
    src=Path(source_project).resolve(strict=True)
    out=Path(output).resolve()
    if src.suffix!=".psd2live":raise ValueError("Real native .psd2live required")
    if out.exists() and any(out.iterdir()):raise ValueError("Output must start empty")
    orig=sha(src)
    source_ids=source_layer_ids(src)
    root=ensure_modern_psd2live(editor_root)
    out.mkdir(parents=True)
    report={"schema":"rearchive/actual-native-animal-anatomy-hide-v2",
            "status":"NOT_RUN","source_sha256":orig,
            "deleted_real_layer_ids":[],"transparent_replaced_split_layers":[],
            "effective_removed_animal_layer_names":list(REMOVED_VISUALLY),
            "native_export_verified":False,"native_pose_qa_passed":False,
            "source_unchanged":False,
            "all_six_animal_shapes_absent_from_render_verified":False,
            "high_end_original_art_passed":False,
            "new_twin_tail_mesh_or_physics_added":False,
            "split_tail2_source_removed_from_generator":False}
    def store():
        (out/"STATUS.json").write_text(json.dumps(report,ensure_ascii=False,
                                   indent=2,default=str),encoding="utf-8")
    try:
        with (serve or _serve_local_mcp)(root,out/"mcp") as (endpoint,token,log):
            with (connect or _external_client)(root/"mcp_proxy.py",endpoint,token) as editor:
                opened=editor.edit("project_open",path=str(src))
                if not opened.get("project_id"):raise RuntimeError("Native project not opened")
                dest=out/"REARCHIVE_NO_ANIMAL_PARTS_EDITABLE.psd2live"
                editor.edit("project_save_as",path=str(dest))
                if not dest.is_file():raise RuntimeError("Non-destructive clone absent")
                layers=_pages(editor,"layers")
                existing={str(x.get("name","")).strip().lower():x for x in layers}
                if any(name not in existing for name in REMOVED_VISUALLY):
                    raise RuntimeError("Actual CC0 animal-layer inventory changed")
                for name in DELETE_SOURCE:
                    ident=source_ids[name]
                    before=editor.state()
                    editor.edit("layer_delete",layer_id=ident)
                    if editor.state()==before:raise RuntimeError("Real source layer not deleted: "+name)
                    report["deleted_real_layer_ids"].append({"name":name,"real_id":ident})
                for name in HIDE_SPLIT:
                    layer=existing[name]
                    ident=layer.get("id") or layer.get("layer_id")
                    if not isinstance(ident,str):raise RuntimeError("Actual split id missing: "+name)
                    meta=editor.call("layer_get_texture",{"layer_id":ident})[0]
                    rect=meta.get("canvas_rect")
                    if not isinstance(rect,dict):raise RuntimeError("Actual split geometry absent")
                    w,h=(max(8,round(float(rect[x]))) for x in ("width","height"))
                    if w*h>16_000_000:raise RuntimeError("Split part geometry too large")
                    texture=out/(name.replace(" ","_")+"__TRANSPARENT.png")
                    Image.new("RGBA",(w,h),(0,0,0,0)).save(texture)
                    before=editor.state()
                    editor.edit("layer_replace_image",layer_id=ident,path=str(texture),
                                fit="stretch",rebuild_mesh=False)
                    if editor.state()==before:raise RuntimeError("Transparent replacement not applied: "+name)
                    after=editor.call("layer_get_texture",{"layer_id":ident})[0]
                    # A tile with alpha=0 can still occupy atlas space;
                    # image bytes being zero + successful state is ground truth.
                    report["transparent_replaced_split_layers"].append({
                        "name":name,"real_id":ident,"render_alpha_zero_input_verified":True,
                        "raster_dimensions":[w,h],"atlas_tile_after":after.get("tile"),
                        "mesh_rebuild_requested":False})
                editor.edit("project_save")
                native=out/"native"
                editor.edit("project_export_model",output_directory=str(native))
                checked=validate_psd2live_output(native,edition="pro")
                if not checked.get("runtime_references_valid") or not checked.get("model3_json"):
                    raise RuntimeError("Edited animal anatomy MOC3 export failed")
                if sha(src)!=orig:raise RuntimeError("Original native source was overwritten")
                report.update(status="FOUR_REAL_SOURCE_LAYERS_DELETED_TWO_SPLITS_HIDDEN_NATIVE_EXPORTED",
                    source_unchanged=True,native_export_verified=True,
                    editable=str(dest),model3_json=str(checked["model3_json"]))
    finally:store()
    return report

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--editor",type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(remove_animals(a.source,a.out,editor_root=a.editor),
                     ensure_ascii=False,indent=2,default=str))
if __name__=="__main__":main()
