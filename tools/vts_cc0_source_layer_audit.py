"""Extract real (not inferred) layer metadata from a pinned CC0 rig example.

Requires psd-tools only for actual PSD inspection. No texture/rig mutations.
Never treats the layer count as the ArtMesh count.
"""
from __future__ import annotations
import argparse
import json
import hashlib
from pathlib import Path

from tools.vts_open_quality_cases import fetch_case, CATALOG

GROUP_KEYS={
  "eyes":("iris","irides","eye","pupil","white","lash","eyebrow","eyewhite"),
  "mouth":("mouth","lip","teeth","tongue"),
  "hair":("hair","bang","twin","pony","tail","fringe","ahoge","headwear"),
  "cloth":("sleeve","skirt","dress","coat","shirt","bow","topwear",
           "bottomwear","handwear","neckwear","arm","hand","ribbon","collar"),
  "head_neck":("face","neck","ear","nose","jaw","head"),
  "other":()
}

def classify(name: str) -> str:
    text=name.lower().replace(" ","").replace("_","").replace("-","")
    for role,terms in GROUP_KEYS.items():
        if any(term in text for term in terms):return role
    return "other"

def summarize_psd(psd_path: Path, *, limit=500):
    from psd_tools import PSDImage
    psd=PSDImage.open(psd_path)
    leaf=[]
    def walk(group,prefix="",depth=0):
        if depth>16:raise ValueError("PSD layer nesting too deep")
        for layer in group:
            name=str(layer.name)
            path=f"{prefix}/{name}" if prefix else name
            if layer.is_group():
                walk(layer,path,depth+1)
                continue
            b=tuple(layer.bbox)
            if len(b)!=4:
                raise ValueError("Invalid PSD layer bbox")
            x1,y1,x2,y2=(int(v) for v in b)
            leaf.append({"name":name,"path":path,
                         "bbox_xyxy":[x1,y1,x2,y2],
                         "width":x2-x1,"height":y2-y1,
                         "visible":bool(layer.is_visible()),
                         "inferred_role":classify(path)})
            if len(leaf)>limit:raise ValueError("Too many PSD layers to audit")
    walk(psd)
    roles={r:sum(item["inferred_role"]==r for item in leaf) for r in GROUP_KEYS}
    return {"psd":str(psd_path),"canvas":[psd.width,psd.height],
            "independent_raster_layer_count":len(leaf),
            "role_counts_from_names_NOT_semantic_proof":roles,
            "layers":leaf}

def inspect_case(case: str, output: Path, *, case_dir: Path|None=None):
    if case not in CATALOG:raise ValueError("Only pinned CC0 cases may be inspected")
    output=Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("Output directory must be empty")
    output.mkdir(parents=True)
    if case_dir is None:
        source=fetch_case(case,output/"download")
        folder=Path(source["source_artifact_dir"])
    else:
        folder=Path(case_dir).resolve(strict=True)
        if not folder.is_dir():raise ValueError("Not a case folder")
        source={"case":case,"source_artifact_dir":str(folder),
                "archive_sha256_verified_this_run":False,
                "warning":"External extracted folder; hash verification required separately"}
    psds=sorted(folder.rglob("*.psd"))
    projects=sorted(folder.rglob("*.psd2live"))
    models=sorted(folder.rglob("*.model3.json"))
    if not psds or not projects or not models:
        raise ValueError("Requires real PSD, editable project and exported native model")
    # A large example may contain many historical PSDs. Prefer main/final source.
    preferred={
      "hiakari-inori":"hiakari_inori_layers_v3.psd",
      "kirishima-mio":"kirishima_mio_fullbody_layers.psd",
      "star_lan":"star_lan.psd"
    }
    selected=next((p for p in psds if p.name==preferred[case]),None)
    if selected is None:raise ValueError("Pinned final PSD was not found")
    details=summarize_psd(selected)
    if not details["layers"]:raise ValueError("Final PSD contains no raster layers")
    project_hint={
      "hiakari-inori":"hiakari_inori_layers_v3.psd2live",
      "kirishima-mio":"kirishima_mio_fullbody.psd2live",
      "star_lan":"star_lan.psd2live"
    }
    main_project=next((p for p in projects if p.name==project_hint[case]),None)
    if main_project is None:raise ValueError("Pinned final editable project not found")
    hash_value=hashlib.sha256()
    with main_project.open("rb") as f:
        for chunk in iter(lambda:f.read(1<<20),b""):hash_value.update(chunk)
    result={
      "schema":"virtual-pipeline/cc0-model-source-audit-v1",
      "case":case,"case_archive_sha256_reference":CATALOG[case]["sha256"],
      "download_report":source,
      "actual_editable_project":str(main_project),
      "editable_project_sha256":hash_value.hexdigest(),
      "model_export_count":len(models),
      "actual_psd_inventory":details,
      "mapping_status":"SOURCE_LAYER_INVENTORY_ONLY",
      "real_psd2live_layer_ids_verified":False,
      "edit_ready":False,
      "native_rig_retargeted":False,
      "native_pose_test_ran":False,
      "original_art_reuse_as_character":False,
      "notes":[
        "Use source names only to suggest roles; PSD layer name is not a real MCP layer_id.",
        "Open the actual .psd2live and inspect layer_get_texture for each real ID/rect.",
        "Replace only with genuinely redrawn RE:ARCHIVE PNGs aligned to matching geometry.",
        "New twin tails or DNA pendant requiring new geometry need separate rigging.",
        "Native exported model is a source reference, not finished RE:ARCHIVE."]
    }
    (output/"source_layer_audit.json").write_text(
        json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--case",choices=sorted(CATALOG),default="hiakari-inori")
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--case-dir",type=Path)
    a=p.parse_args()
    report=inspect_case(a.case,a.out,case_dir=a.case_dir)
    print(json.dumps({"case":a.case,
       "layers":report["actual_psd_inventory"]["independent_raster_layer_count"],
       "roles":report["actual_psd_inventory"]["role_counts_from_names_NOT_semantic_proof"],
       "json":str(a.out/"source_layer_audit.json"),
       "actual_model_retargeted":False},ensure_ascii=False,indent=2))

if __name__=="__main__":main()
