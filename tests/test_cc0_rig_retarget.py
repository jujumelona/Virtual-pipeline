"""Unit-level guardrails for retargeting; NOT actual PSD2Live/MOC3 GPU proof."""
import hashlib
from pathlib import Path
import pytest
from PIL import Image

from tools import vts_cc0_rig_retarget as mod

def _source(tmp_path):
    src=tmp_path/"inori.psd2live"
    src.write_bytes(b"unmodified CC0 project fixture")
    img=Image.new("RGBA",(128,128),(0,0,0,0))
    img.paste((50,240,190,255),(25,20,105,100))
    img.save(tmp_path/"irides-l.png")
    p=mod.starter_plan("hiakari-inori",src)
    p["replacements"]=[{
        "layer_id":"layer:real-inspected-id",
        "role":"eyes",
        "image":"irides-l.png",
        "expected_canvas_rect":[12,22,128,128],
        "fit":"contain",
        "rebuild_mesh":False
    }]
    return src,p

def test_starter_not_rigged(tmp_path):
    source,p=_source(tmp_path)
    assert p["status"]=="TEMPLATE_NOT_RIGGED"
    assert p["source_sha256"]==hashlib.sha256(source.read_bytes()).hexdigest()
    assert len(mod.validate_plan(p,project=source,project_root=tmp_path))==1

@pytest.mark.parametrize("field,value,error",[
    ("source_sha256","bad","SHA256"),
    ("source_case","unlicensed","CC0"),
    ("replacements",[],"1..96"),
])
def test_bad_plan_rejected(tmp_path,field,value,error):
    source,p=_source(tmp_path)
    p[field]=value
    with pytest.raises(ValueError,match=error):
        mod.validate_plan(p,project=source,project_root=tmp_path)

def test_no_opaque_or_missing_or_unsafe_art(tmp_path):
    source,p=_source(tmp_path)
    p["replacements"][0]["image"]="../../secret.png"
    with pytest.raises(ValueError,match="Missing replacement"):
        mod.validate_plan(p,project=source,project_root=tmp_path)
    p["replacements"][0]["image"]="irides-l.png"
    Image.new("RGBA",(128,128),(255,255,255,255)).save(tmp_path/"irides-l.png")
    with pytest.raises(ValueError,match="Nontransparent"):
        mod.validate_plan(p,project=source,project_root=tmp_path)

def test_no_geometry_rerig_or_reuse_one_image(tmp_path):
    source,p=_source(tmp_path)
    p["replacements"][0]["rebuild_mesh"]=True
    with pytest.raises(ValueError,match="Geometry-preserving"):
        mod.validate_plan(p,project=source,project_root=tmp_path)
    p["replacements"][0]["rebuild_mesh"]=False
    p["replacements"].append({**p["replacements"][0],"layer_id":"layer:second"})
    with pytest.raises(ValueError,match="cannot be reused"):
        mod.validate_plan(p,project=source,project_root=tmp_path)

def test_native_retarget_calls_real_layer_replace_and_keeps_source(tmp_path,monkeypatch):
    source,p=_source(tmp_path)
    before=source.read_bytes()
    calls=[]
    def fake_run(proxy,operation,request,work,executor=None):
        calls.append((operation,dict(request)))
        if operation=="project_save_as":
            Path(request["path"]).write_bytes(b"edited copy")
        if operation=="project_export_model":
            target=Path(request["output_directory"])
            target.mkdir(parents=True,exist_ok=True)
            (target/"avatar.model3.json").write_text("{}",encoding="utf-8")
        payload={"ok":True,"data":{"canvas_rect":[12,22,128,128]}}
        return {"operation":operation,"response":payload}
    monkeypatch.setattr(mod,"_require_mcp_cli",lambda x: Path(x))
    monkeypatch.setattr(mod,"_run_mcp",fake_run)
    result=mod.apply(p,project=source,image_root=tmp_path,
                     proxy_root=tmp_path,output=tmp_path/"new",
                     render=lambda model,out:{"native_pose_geometry_passed":True,
                        "pose_activity_passed":True,
                        "native_mouth_interpolation_passed":True,
                        "parameter_isolation":{"passed":True}})
    assert source.read_bytes()==before
    assert result["status"]=="NEEDS_ARTIST_AND_TRACKING_REVIEW"
    assert result["native_pose_qa_passed"]
    assert result["artistic_quality_verified"] is False
    assert result["vtube_studio_tracking_verified"] is False
    assert ("layer_replace_image",{"layer_id":"layer:real-inspected-id",
        "path":str((tmp_path/"irides-l.png").resolve()),"fit":"contain",
        "rebuild_mesh":False}) in calls
    assert Path(result["copied_project"]).read_bytes()==b"edited copy"

def test_mismatched_real_layer_geometry_rejected(tmp_path,monkeypatch):
    source,p=_source(tmp_path)
    def fake_run(proxy,operation,request,work,executor=None):
        if operation=="project_save_as":Path(request["path"]).write_bytes(b"copy")
        return {"response":{"ok":True,"data":{"canvas_rect":[999,1,128,128]}}}
    monkeypatch.setattr(mod,"_require_mcp_cli",lambda x:Path(x))
    monkeypatch.setattr(mod,"_run_mcp",fake_run)
    with pytest.raises(ValueError,match="Layer geometry changed"):
        mod.apply(p,project=source,image_root=tmp_path,
                  proxy_root=tmp_path,output=tmp_path/"out",
                  render=lambda *a:None)
