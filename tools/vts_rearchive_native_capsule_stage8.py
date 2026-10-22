"""Install a true independent DNA archive pendant mesh and physical swing.

Input: proven stage7 native .psd2live plus real Stage4 source capsule PNG.
Keeps model editable, preserves existing dual-tail rigs/physics, and exports
genuine native Cubism MOC3. This does NOT make the reused CC0 artwork match
the original high-detail RE:ARCHIVE setting sheets.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path
from PIL import Image
from tools.vts_rearchive_native_iris_trial import _pages,sha
from tools.vts_modern_editable_project import _external_client,_serve_local_mcp
from tools.vts_psd2live_modern import ensure_modern_psd2live
from tools.vts_psd2live import validate_psd2live_output

NAME="REARCHIVE_DNA_PENDANT_INDEPENDENT"
SWING="RearchiveDNAPendantPhysics"

def implant(source:Path,art_file:Path,out:Path,*,editor_root=None,connect=None,serve=None):
    source=Path(source).resolve(strict=True)
    art_file=Path(art_file).resolve(strict=True)
    out=Path(out).resolve()
    if source.suffix.lower()!=".psd2live":raise ValueError("Require a native editable PSD2Live project")
    if out.exists() and any(out.iterdir()):raise ValueError("Fresh output directory required")
    with Image.open(art_file) as img:
        img.load()
        if img.mode!="RGBA" or img.size!=(150,255) or img.getchannel("A").getextrema()!=(0,255):
            raise ValueError("A separate alpha-enabled Stage4 REARCHIVE DNA capsule art is required")
    root=ensure_modern_psd2live(editor_root)
    original=sha(source)
    out.mkdir(parents=True)
    dest_png=out/(NAME+".png")
    dest_png.write_bytes(art_file.read_bytes())
    qa={"schema":"rearchive/independent-dna-pendant-stage8-v1","status":"NOT_RUN",
        "source_sha256":original,"source_unchanged":False,
        "independent_dna_mesh_inserted":False,
        "independent_dna_physics_generated":False,
        "native_export_verified":False,"native_pose_qa_passed":False,
        "vtube_studio_camera_tested":False,"premium_original_art_passed":False,
        "free_2048_one_atlas_verified":False}
    def write():
        (out/"STATUS.json").write_text(json.dumps(qa,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
    try:
        with (serve or _serve_local_mcp)(root,out/"mcp") as (endpoint,token,log):
            with (connect or _external_client)(root/"mcp_proxy.py",endpoint,token) as editor:
                p=editor.edit("project_open",path=str(source))
                if not p.get("project_id"):raise RuntimeError("Stage7 native source could not open")
                cloned=out/"REARCHIVE_STAGE8_DNA_INDEPENDENT_EDITABLE.psd2live"
                editor.edit("project_save_as",path=str(cloned))
                if not cloned.is_file():raise RuntimeError("Stage8 editable copy not saved")
                layers=_pages(editor,"layers")
                anchors=[x for x in layers if str(x.get("name","")).strip()=="neckwear · 前"]
                if len(anchors)!=1:raise RuntimeError("Unique existing front neckline layer required")
                anchor=anchors[0].get("id")
                if not isinstance(anchor,str) or not anchor:raise RuntimeError("Neckline layer ID invalid")
                editor.edit("layer_import_images",paths=[str(dest_png)],
                    at=[1024,760],anchor_layer_id=anchor,in_front=True)
                after=_pages(editor,"layers")
                named=[x for x in after if str(x.get("name","")).strip()==NAME]
                if len(named)!=1:raise RuntimeError("New independent DNA layer not imported")
                drawable=[x for x in _pages(editor,"objects") if isinstance(x,dict)
                           and str(x.get("name","")).strip()==NAME]
                if len(drawable)!=1:raise RuntimeError("No unique new real pendant mesh")
                handle=drawable[0].get("target")
                if not isinstance(handle,str) or not handle.startswith("mesh:"):
                    raise RuntimeError("Need real mesh:ID target from upstream PSD2Live")
                raw=handle.split(":",1)[1]
                if not raw:raise RuntimeError("Empty drawable ID")
                qa["independent_dna_mesh_inserted"]=True
                qa["actual_mesh_id"]=raw
                swing=editor.edit("swing_put",id=SWING,name="DNA capsule soft pendant motion",
                    targets=[raw],kind="lateral",segments=2,magnitude=0.09,
                    softness=0.36,parallel=0.15,fulcrum="top",preset="hair",
                    physics_enabled=True)
                if swing.get("applied") is False:raise RuntimeError("Pendant swing not applied")
                qa["independent_dna_physics_generated"]=True
                editor.edit("project_save")
                exported=out/"native"
                editor.edit("project_export_model",output_directory=str(exported))
                integrity=validate_psd2live_output(exported,edition="pro")
                if not integrity.get("runtime_references_valid") or not integrity.get("model3_json"):
                    raise RuntimeError("DNA pendant native MOC3 invalid")
                if sha(source)!=original:raise RuntimeError("Parent native project was modified")
                qa.update(source_unchanged=True,native_export_verified=True,
                    editable_project=str(cloned),model3_json=str(integrity["model3_json"]),
                    status="ACTUAL_SEPARATE_DNA_CAPSULE_MESH_AND_PHYSICS_NATIVE_EXPORTED_REQUIRES_POSE_AND_ART_QA")
    finally:write()
    return qa

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--capsule",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--editor",type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(implant(a.source,a.capsule,a.out,editor_root=a.editor),ensure_ascii=False,indent=2))
if __name__=="__main__":main()
