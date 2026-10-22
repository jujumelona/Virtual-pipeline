"""Remove six genuinely imported animal-ear/tail layers from the cloned RE:ARCHIVE trial.

This invokes upstream PSD2Live 3.6 "layer_delete" against ACTUAL named
layers in a source CC0 rig, not an alpha-paint mock. Preserves original
project; outputs an editable .psd2live and native MOC3 if valid.
This is STILL NOT a finished original RE:ARCHIVE character.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
from tools.vts_rearchive_native_iris_trial import _pages,sha
from tools.vts_modern_editable_project import _external_client,_serve_local_mcp
from tools.vts_psd2live_modern import ensure_modern_psd2live
from tools.vts_psd2live import validate_psd2live_output

DELETE = ("ears-r","ears-l","tail 1","tail 2-t","tail 2-b","tail 3")

def remove_animals(source_project:Path,output:Path,*,editor_root=None,connect=None,serve=None):
    src=Path(source_project).resolve(strict=True)
    out=Path(output).resolve()
    if src.suffix!=".psd2live":raise ValueError("Real .psd2live required")
    if out.exists() and any(out.iterdir()):raise ValueError("Output must start empty")
    original=sha(src)
    root=ensure_modern_psd2live(editor_root)
    out.mkdir(parents=True)
    report={"schema":"rearchive/actual-animal-deletion-v1","source_sha256":original,
            "deleted_real_layer_ids":[],"native_export_verified":False,
            "native_pose_qa_passed":False,"source_unchanged":False,
            "original_high_end_art_passed":False,
            "dna_capsule_independent_rigged":False,
            "twin_tails_reauthored":False,
            "status":"NOT_RUN"}
    def store():
        (out/"STATUS.json").write_text(json.dumps(report,ensure_ascii=False,
                                      indent=2,default=str),encoding="utf-8")
    try:
        with (serve or _serve_local_mcp)(root,out/"mcp") as (endpoint,token,log):
            with (connect or _external_client)(root/"mcp_proxy.py",endpoint,token) as editor:
                opened=editor.edit("project_open",path=str(src))
                if not opened.get("project_id"):raise RuntimeError("Real CC0 project did not open")
                copied=out/"REARCHIVE_NO_ANIMAL_PARTS_EDITABLE.psd2live"
                editor.edit("project_save_as",path=str(copied))
                if not copied.is_file():raise RuntimeError("Failed to clone native project")
                layers=_pages(editor,"layers")
                for name in DELETE:
                    matches=[x for x in layers if str(x.get("name","")).strip().lower()==name]
                    if len(matches)!=1:raise RuntimeError(f"Expected one real layer {name}: {matches}")
                    ident=matches[0].get("id") or matches[0].get("layer_id")
                    if not isinstance(ident,str) or not ident:raise RuntimeError("Real ID missing")
                    old=editor.state()
                    editor.edit("layer_delete",layer_id=ident)
                    if editor.state()==old:raise RuntimeError("Layer removal was not committed")
                    report["deleted_real_layer_ids"].append({"name":name,"id":ident})
                remaining=_pages(editor,"layers")
                deletion_state=[]
                for name in DELETE:
                    listed=[x for x in remaining if str(x.get("name","")).strip().lower()==name]
                    if not listed:
                        deletion_state.append({"name":name,"state":"removed_from_inspection"})
                        continue
                    if len(listed)!=1:raise RuntimeError("Duplicate derived layer after deletion: "+name)
                    ident=listed[0].get("id") or listed[0].get("layer_id")
                    # Derived source-split layers are soft-tombstoned by
                    # upstream, and may remain in the layer inspection list.
                    actual=editor.call("layer_get_texture",{"layer_id":ident})[0]
                    if actual.get("deleted") is not True:
                        raise RuntimeError(
                            f"Deleted layer is still textured/active: {name}; {actual.get('deleted')}")
                    deletion_state.append({"name":name,"state":"upstream_deleted_tombstone"})
                report["actual_native_deletion_states"]=deletion_state
                editor.edit("project_save")
                native=out/"native"
                editor.edit("project_export_model",output_directory=str(native))
                checked=validate_psd2live_output(native,edition="pro")
                if not checked.get("runtime_references_valid") or not checked.get("model3_json"):
                    raise RuntimeError("Deleted-layer model fails native output references")
                if sha(src)!=original:raise RuntimeError("Source project accidentally modified")
                report.update(native_export_verified=True,source_unchanged=True,
                    status="FIVE_ORIGINAL_ANIMAL_LAYERS_REMOVED_NATIVE_MODEL_EXPORTED_NOT_ART_FINAL",
                    editable=str(copied),model3_json=str(checked["model3_json"]))
    finally:store()
    return report

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--editor",type=Path,required=True)
    x=p.parse_args()
    print(json.dumps(remove_animals(x.source,x.out,editor_root=x.editor),
                     ensure_ascii=False,indent=2,default=str))
if __name__=="__main__": main()
