"""Actual second-stage CC0 rig texture replacement with existing keyforms preserved.

This is a source-geometry/motion technical trial, NOT the final RE:ARCHIVE art.
Only original native layers with exact name and bounded coordinate drift qualify.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from zipfile import ZipFile
from PIL import Image
from tools.vts_modern_editable_project import _external_client,_serve_local_mcp
from tools.vts_psd2live_modern import ensure_modern_psd2live
from tools.vts_psd2live import validate_psd2live_output
from tools.vts_rearchive_native_iris_trial import _pages,sha

# Do not attempt animal tails, ears, composite neckwear, split hair layers.
COSTUME_HAIR = ("front hair","front hair 2","back hair 3",
                "topwear","bottomwear 2","handwear 1-r","handwear 1-l",
                "headwear 1","headwear 2")

def stage2(source_project: Path, edited_zip: Path, dest: Path, *, editor_root=None,
           connect=None,serve=None) -> dict:
    project=Path(source_project).resolve(strict=True)
    dest=Path(dest).resolve()
    if project.suffix!=".psd2live":raise ValueError("Existing editable native project required")
    if dest.exists() and any(dest.iterdir()):raise ValueError("Destination must be empty")
    original=sha(project)
    root=ensure_modern_psd2live(editor_root)
    dest.mkdir(parents=True)
    result={"schema":"rearchive/real-native-costume-source-geometry-v1",
            "status":"NOT_RUN","original_sha256":original,"replaced_layers":[],
            "source_project_unchanged":False,"native_export_verified":False,
            "artistic_quality_passed":False,"rearchive_character_completed":False,
            "new_twin_tail_mesh_and_physics_added":False,
            "animal_ears_and_tails_removed":False}
    def save():
        (dest/"STATUS.json").write_text(json.dumps(
           result,ensure_ascii=False,indent=2),encoding="utf-8")
    with ZipFile(edited_zip) as z:
        if z.testzip() is not None:raise RuntimeError("Edited parts ZIP corrupted")
        manifest=json.loads(z.read("01_LAYER_MAPPING_TEMPLATE.json"))
        if manifest.get("canvas")!=[2048,3072]:raise ValueError("Wrong source canvas")
        parts={item["source_layer_name"]:item for item in manifest["template_layers"]}
        for name in COSTUME_HAIR:
            if name not in parts:raise ValueError("Missing original source layer "+name)
            image=dest/(name.replace(" ","_")+".png")
            image.write_bytes(z.read(parts[name]["guide"]))
            with Image.open(image) as p:
                p.load()
                bounds=parts[name]["original_bbox_xyxy"]
                if p.mode!="RGBA" or p.size!=(bounds[2]-bounds[0],bounds[3]-bounds[1]):
                    raise ValueError("Edited part raster invalid "+name)
    try:
        with (serve or _serve_local_mcp)(root,dest/"mcp") as (endpoint,token,log):
            with (connect or _external_client)(root/"mcp_proxy.py",endpoint,token) as client:
                opened=client.edit("project_open",path=str(project))
                if not opened.get("state"):raise RuntimeError("Native project did not open")
                clone=dest/"REARCHIVE_MINT_AND_COSTUME_TRIAL.psd2live"
                client.edit("project_save_as",path=str(clone))
                if not clone.is_file():raise RuntimeError("No cloned native project")
                actual=_pages(client,"layers")
                for name in COSTUME_HAIR:
                    matches=[x for x in actual if x.get("name","").strip().lower()==name.lower()]
                    if len(matches)!=1:raise RuntimeError("No unique real layer "+name)
                    row=matches[0]
                    ident=row.get("id")
                    if not isinstance(ident,str) or not ident:raise RuntimeError("Native ID absent "+name)
                    tex=client.call("layer_get_texture",{"layer_id":ident})[0]
                    rect=tex.get("canvas_rect")
                    if not isinstance(rect,dict):raise RuntimeError("No native rect "+name)
                    view=[rect[k] for k in ("left","top","width","height")]
                    b=parts[name]["original_bbox_xyxy"]
                    guide=[b[0],b[1],b[2]-b[0],b[3]-b[1]]
                    deltas=[float(a)-float(c) for a,c in zip(view,guide)]
                    if max(abs(x) for x in deltas)>12:
                        raise RuntimeError(f"Source/native mesh mismatch {name}: {view} vs {guide}")
                    prev=client.state()
                    client.edit("layer_replace_image",layer_id=ident,
                                path=str(dest/(name.replace(" ","_")+".png")),
                                fit="contain",rebuild_mesh=False)
                    current=client.state()
                    if current==prev:raise RuntimeError("Actual change not committed for "+name)
                    result["replaced_layers"].append({"name":name,"real_id":ident,
                        "native_rect":view,"source_rect":guide,"pixel_offset":deltas,
                        "mesh_rebuild_requested":False})
                client.edit("project_save")
                ex=dest/"native"
                client.edit("project_export_model",output_directory=str(ex))
                verified=validate_psd2live_output(ex,edition="pro")
                if not verified.get("runtime_references_valid") or not verified.get("model3_json"):
                    raise RuntimeError("Real native export invalid")
                if sha(project)!=original:raise RuntimeError("Original eye-rig project changed")
                result.update(status="REAL_COSTUME_AND_HAIR_TEXTURES_INSERTED_NEEDS_ART_AND_NATIVE_POSE_QA",
                    source_project_unchanged=True,native_export_verified=True,
                    exported_model3=str(verified["model3_json"]),editable=str(clone))
    finally:save()
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source-project",type=Path,required=True)
    p.add_argument("--edited-zip",type=Path,required=True)
    p.add_argument("--editor",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(stage2(a.source_project,a.edited_zip,a.out,editor_root=a.editor),
                    ensure_ascii=False,indent=2))
if __name__=="__main__":main()
