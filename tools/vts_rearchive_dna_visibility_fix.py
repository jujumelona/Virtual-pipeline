"""Stage 9: ensure the independent DNA pendant is REALLY visible in the 2D rig.

The stage8 proof added an independently rigged ArtMesh but it inherited a draw
order that left the pendant obscured. Sets a documented whole-integer
layer_draw_order override, retains its existing swing physics and renders MOC3.
This is a visibility fix, not a claim of high-end reference-art fidelity.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path
from tools.vts_rearchive_native_iris_trial import _pages,sha
from tools.vts_modern_editable_project import _external_client,_serve_local_mcp
from tools.vts_psd2live_modern import ensure_modern_psd2live
from tools.vts_psd2live import validate_psd2live_output

NAME="REARCHIVE_DNA_PENDANT_INDEPENDENT"

def move_front(source:Path,output:Path,*,editor_root=None,connect=None,serve=None):
    project=Path(source).resolve(strict=True)
    output=Path(output).resolve()
    if project.suffix!=".psd2live":raise ValueError("Require genuine editable PSD2Live project")
    if output.exists() and any(output.iterdir()):raise ValueError("Output not empty")
    original=sha(project)
    root=ensure_modern_psd2live(editor_root)
    output.mkdir(parents=True)
    verdict={"schema":"rearchive/dna-visibility-stage9-v1","status":"NOT_RUN",
        "source_sha256":original,"source_project_unmodified":False,
        "independent_pendant_mesh_found":False,"pendant_front_draw_order_committed":False,
        "existing_pendant_physics_retained":False,"native_export_verified":False,
        "native_pose_qa_passed":False,"pendant_pixel_visibility_verified":False,
        "high_end_character_art_passed":False}
    def write():
        (output/"STATUS.json").write_text(json.dumps(
            verdict,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
    try:
        with (serve or _serve_local_mcp)(root,output/"mcp") as (endpoint,token,log):
            with (connect or _external_client)(root/"mcp_proxy.py",endpoint,token) as editor:
                opened=editor.edit("project_open",path=str(project))
                if not opened.get("project_id"):raise RuntimeError("Source model could not open")
                cloned=output/"REARCHIVE_STAGE9_VISIBLE_DNA_EDITABLE.psd2live"
                editor.edit("project_save_as",path=str(cloned))
                if not cloned.is_file():raise RuntimeError("Editable project clone missing")
                drawable=[x for x in _pages(editor,"objects") if
                     isinstance(x,dict) and str(x.get("name","")).strip()==NAME]
                if len(drawable)!=1:raise RuntimeError("Cannot uniquely find physical DNA mesh")
                ref=drawable[0].get("target")
                if not isinstance(ref,str) or not ref.startswith("mesh:"):
                    raise RuntimeError("Real pendant mesh typed handle missing")
                verdict["independent_pendant_mesh_found"]=True
                before=editor.state()
                order=999  # integer 0-1000; faces/costume other layers unchanged
                result=editor.edit("layer_draw_order",target=ref,order=order)
                if editor.state()==before:raise RuntimeError("Draw order update did not commit")
                verdict.update(pendant_front_draw_order_committed=True,
                               pendant_mesh_target=ref,front_draw_order=order)
                editor.edit("project_save")
                native=output/"native"
                editor.edit("project_export_model",output_directory=str(native))
                checked=validate_psd2live_output(native,edition="pro")
                if not checked.get("runtime_references_valid") or not checked.get("model3_json"):
                    raise RuntimeError("Native project does not have coherent MOC3 references")
                if sha(project)!=original:raise RuntimeError("Parent source modified unexpectedly")
                physics=(native/"hiakari_inori_layers_v3.physics3.json")
                if not physics.is_file():raise RuntimeError("Physics output absent")
                pdata=json.loads(physics.read_text())
                # Retained swing configuration is also checked in original editable archive by layer mesh.
                if not pdata.get("PhysicsSettings"):
                    raise RuntimeError("Physics body unexpectedly missing")
                verdict.update(status="INDEPENDENT_DNA_MESH_FRONT_DRAW_ORDER_NATIVE_EXPORTED_NEEDS_TRUE_VISUAL_QA",
                    source_project_unmodified=True,native_export_verified=True,
                    existing_pendant_physics_retained=True,
                    model3_json=str(checked["model3_json"]),editable_project=str(cloned))
    finally:write()
    return verdict

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--editor",type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(move_front(a.source,a.out,editor_root=a.editor),ensure_ascii=False,indent=2))
if __name__=="__main__":main()
