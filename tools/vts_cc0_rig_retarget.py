"""Safely retarget a real editable CC0 PSD2Live project via upstream MCP.

A raster replacement retains mesh/keyforms/bindings when geometry is similar.
No change is ever made to the source .psd2live; actual editing requires the
modern PSD2Live MCP server and real per-layer PNGs (not contact sheets).
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image
from tools.vts_reference_keyform_author import _run_mcp, _require_mcp_cli

SCHEMA = "virtual-pipeline/cc0-rig-retarget-v1"
ALLOWED_CASES = frozenset(("hiakari-inori", "kirishima-mio", "star_lan"))
MAX_REPLACEMENTS = 96
ROLE_WORDS = frozenset(("face", "eyes", "hair", "mouth", "neck", "sleeve",
                        "outfit", "body", "ribbon", "capsule", "accessory",
                        "other"))

def _sha(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""): h.update(b)
    return h.hexdigest()

def _rect(value) -> list[int]:
    if not isinstance(value,list) or len(value)!=4 or any(
        type(n) is not int or n<0 for n in value
    ) or value[2]==0 or value[3]==0:
        raise ValueError("expected_canvas_rect must be [x,y,width,height]")
    return value

def validate_plan(plan: dict, *, project: Path, project_root: Path) -> list[dict]:
    if plan.get("schema")!=SCHEMA or plan.get("source_case") not in ALLOWED_CASES:
        raise ValueError("Expected known CC0 case and current plan schema")
    if plan.get("source_sha256")!=_sha(project):
        raise ValueError("SOURCE_PROJECT_SHA256_CHANGED")
    items=plan.get("replacements")
    if not isinstance(items,list) or not 1<=len(items)<=MAX_REPLACEMENTS:
        raise ValueError("Require 1..96 real texture replacement items")
    names=set()
    result=[]
    for i,item in enumerate(items):
        if not isinstance(item,dict):raise ValueError(f"Invalid item {i}")
        layer=item.get("layer_id")
        if not isinstance(layer,str) or not layer.strip() or layer in names:
            raise ValueError("Each replacement must have unique real layer_id from workspace_inspect")
        names.add(layer)
        role=item.get("role")
        if role not in ROLE_WORDS:raise ValueError("Unknown role "+str(role))
        # Physical anchor is verified against upstream layer_get_texture (not a guessed name).
        rect=_rect(item.get("expected_canvas_rect"))
        raw=item.get("image")
        if not isinstance(raw,str) or not raw.lower().endswith(".png"):
            raise ValueError("Each replacement requires an actual PNG path")
        file=(project_root/raw).resolve()
        if not file.is_relative_to(project_root.resolve()) or not file.is_file():
            raise ValueError("Missing replacement or path escapes work directory: "+str(raw))
        with Image.open(file) as im:
            im.load()
            if im.format!="PNG" or im.mode!="RGBA":
                raise ValueError("Requires genuine per-part RGBA PNG: "+str(raw))
            if im.width*im.height>16_000_000 or min(im.size)<8:
                raise ValueError("Invalid image dimensions: "+str(raw))
            alpha=im.getchannel("A")
            if alpha.getextrema()[0]!=0 or alpha.getextrema()[1]<200:
                raise ValueError("Nontransparent or invisible part: "+str(raw))
            bbox=alpha.getbbox()
        # No image deformation is permitted without explicit artist review.
        if item.get("fit","contain")!="contain" or item.get("rebuild_mesh",False) is not False:
            raise ValueError("Geometry-preserving reuse requires fit=contain and rebuild_mesh=false")
        result.append({"layer_id":layer,"role":role,"file":file,
                       "sha256":_sha(file),"expected_canvas_rect":rect,
                       "image_size":[im.width,im.height],"alpha_bbox":list(bbox)})
    if len({str(item["file"]) for item in result})!=len(result):
        raise ValueError("A source part PNG cannot be reused for different layers")
    return result

def starter_plan(case: str, project: Path) -> dict:
    if case not in ALLOWED_CASES:raise ValueError("Unknown source case")
    project=Path(project).resolve(strict=True)
    return {
        "schema":SCHEMA,"source_case":case,"source_sha256":_sha(project),
        "source_project":str(project),
        "instructions":("Inspect the actual PSD2Live workspace and fill real layer IDs "
                        "and current canvas rectangles from layer_get_texture. Generate "
                        "per-part transparent painted images on those exact layer bounds. "
                        "These are NOT the original art sheet crops."),
        "replacements":[],
        "source_license":"CC0-1.0 (verify the selected case's upstream manifest)",
        "fidelity_requirements":{
           "new_character":"RE:ARCHIVE; previous humanity DNA and memory preservation",
           "eye":"very large mint/lime eyes, dedicated sclera iris lashes eyelids",
           "hair":"black/white long twin-tails, mint highlights and movable ribbons",
           "outfit":"high-end black/white cyber gothic, detailed large sleeves",
           "capsule":"separate DNA capsule with movable pendant rig",
           "original_art_preserved":True,
           "mask":"exclude until face rig verified"},
        "status":"TEMPLATE_NOT_RIGGED"
    }

def _bbox_tuple(raw: dict):
    # Current upstream layer_get_texture returns canvas_rect; fail closed.
    rect=raw.get("canvas_rect")
    if isinstance(rect,dict):
        return [rect.get(k) for k in ("x","y","width","height")]
    if isinstance(rect,list):
        return rect
    return None

def _actual_response(receipt):
    response=receipt["response"]
    if "data" in response and isinstance(response["data"],dict):
        data=response["data"]
        if "result" in data and isinstance(data["result"],dict):
            return data["result"]
        return data
    return response

def apply(plan: dict, *, project: Path, image_root: Path, proxy_root: Path,
          output: Path, executor=None, render=None) -> dict:
    project=Path(project).resolve(strict=True)
    if project.suffix!=".psd2live":
        raise ValueError("Require an editable .psd2live project, not a moc3")
    image_root=Path(image_root).resolve(strict=True)
    items=validate_plan(plan,project=project,project_root=image_root)
    output=Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("Output must be a fresh directory")
    _require_mcp_cli(proxy_root)
    output.mkdir(parents=True,exist_ok=True)
    original_hash=_sha(project)
    receipts=[]
    receipts.append(_run_mcp(proxy_root,"project_open",{"path":str(project)},
                             output/"mcp"/"open",executor))
    saved=output/"REARCHIVE_retarged_EDITABLE.psd2live"
    receipts.append(_run_mcp(proxy_root,"project_save_as",{"path":str(saved)},
                             output/"mcp"/"save_copy",executor))
    if not saved.is_file():
        raise RuntimeError("Source project was not cloned; stopping")
    processed=[]
    for index,item in enumerate(items):
        layer=item["layer_id"]
        query=_run_mcp(proxy_root,"layer_get_texture",{"layer_id":layer},
                       output/"mcp"/f"inspect_{index}",executor)
        current=_bbox_tuple(_actual_response(query))
        if current!=item["expected_canvas_rect"]:
            raise ValueError(f"Layer geometry changed for {layer}: {current} != "
                             f"{item['expected_canvas_rect']}")
        receipts.append(query)
        result=_run_mcp(proxy_root,"layer_replace_image",{
            "layer_id":layer,"path":str(item["file"]),
            "fit":"contain","rebuild_mesh":False
        },output/"mcp"/f"replace_{index}",executor)
        receipts.append(result)
        processed.append({"layer_id":layer,"role":item["role"],
                          "sha256":item["sha256"],"geometry_preserved_requested":True})
    receipts.append(_run_mcp(proxy_root,"project_save",{},
                             output/"mcp"/"final_save",executor))
    model_dir=output/"native"
    receipts.append(_run_mcp(proxy_root,"project_export_model",{
        "output_directory":str(model_dir)
    },output/"mcp"/"export",executor))
    if _sha(project)!=original_hash:
        raise RuntimeError("SOURCE_PROJECT_MODIFIED")
    models=list(model_dir.rglob("*.model3.json"))
    if len(models)!=1:
        raise RuntimeError("No unique native model export")
    from tools.vts_multiview_runtime import render_actual_native_moc3
    checker=render or render_actual_native_moc3
    native=checker(models[0],output/"pose_qa")
    passed=(isinstance(native,dict) and
            native.get("native_pose_geometry_passed") is True and
            native.get("pose_activity_passed") is True and
            native.get("native_mouth_interpolation_passed") is True and
            isinstance(native.get("parameter_isolation"),dict) and
            native["parameter_isolation"].get("passed") is True)
    report={
        "schema":"virtual-pipeline/cc0-native-retarget-result-v1",
        "source_case":plan["source_case"],"source_sha256":original_hash,
        "copied_project":str(saved),"model3":str(models[0]),
        "replacement_count":len(items),"parts":processed,
        "native_pose_qa_passed":bool(passed),"native_pose_report":native,
        "artistic_quality_verified":False,
        "same_character_visual_identity_verified":False,
        "vtube_studio_tracking_verified":False,
        "free_edition_budget_verified":False,
        "status":"NEEDS_ARTIST_AND_TRACKING_REVIEW" if passed else "NATIVE_POSE_QA_FAILED",
        "receipts":receipts,
    }
    (output/"retarget_verdict.json").write_text(json.dumps(
        report,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
    if not passed:
        raise RuntimeError("NATIVE_POSE_QA_FAILED; see retarget_verdict.json")
    return report

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source-project",type=Path,required=True)
    p.add_argument("--source-case",choices=sorted(ALLOWED_CASES),default="hiakari-inori")
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--plan",type=Path)
    p.add_argument("--image-root",type=Path)
    p.add_argument("--psd2live-source",type=Path)
    a=p.parse_args()
    if a.plan is None:
        a.output.mkdir(parents=True,exist_ok=True)
        target=a.output/"retarget_plan_TEMPLATE.json"
        target.write_text(json.dumps(starter_plan(a.source_case,a.source_project),
                         ensure_ascii=False,indent=2),encoding="utf-8")
        print("Template generated; no edits made:",target)
        return
    if a.image_root is None or a.psd2live_source is None:
        p.error("--plan requires --image-root and --psd2live-source")
    plan=json.loads(a.plan.read_text(encoding="utf-8"))
    print(json.dumps(apply(plan,project=a.source_project,image_root=a.image_root,
                           proxy_root=a.psd2live_source,output=a.output),
                     ensure_ascii=False,indent=2,default=str))

if __name__=="__main__":
    main()
