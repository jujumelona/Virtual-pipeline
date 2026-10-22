"""Create a second 2048x2048 atlas runtime from a genuine native MOC3 export.

This lowers texture memory/quality only, never edits the original .moc3 mesh,
parameter, or physics and NEVER claims Cubism FREE edition compatibility.
"""
from __future__ import annotations
import argparse,hashlib,json,shutil
from pathlib import Path
from PIL import Image

def convert(model3:Path,output:Path):
    model3=Path(model3).resolve(strict=True);src=model3.parent
    output=Path(output).resolve()
    if output.exists() and any(output.iterdir()):raise ValueError("Output directory must be fresh")
    model=json.loads(model3.read_text(encoding="utf-8"))
    f=model.get("FileReferences",{})
    atlas=f.get("Textures")
    if not isinstance(atlas,list) or len(atlas)!=1:raise ValueError("Require exactly one texture atlas")
    texture=(src/atlas[0]).resolve(strict=True)
    if not texture.is_relative_to(src):raise ValueError("Atlas path escapes runtime")
    with Image.open(texture) as img:
        img.load()
        if img.size!=(4096,4096):raise ValueError("Expected real 4096 native texture")
    output.mkdir(parents=True)
    for path in src.rglob("*"):
        if path.is_file():
            rel=path.relative_to(src)
            if rel==Path(atlas[0]) or rel==Path(model3.name):continue
            if not (output/rel).parent.exists():(output/rel).parent.mkdir(parents=True)
            shutil.copy2(path,output/rel)
    newtex=Path(model3.stem+".2048")/"texture_00.png"
    (output/newtex).parent.mkdir(parents=True,exist_ok=True)
    with Image.open(texture) as img:
        img.convert("RGBA").resize((2048,2048),Image.Resampling.LANCZOS).save(
            output/newtex,format="PNG",optimize=True)
    f["Textures"]=[newtex.as_posix()]
    dst=output/model3.name
    dst.write_text(json.dumps(model,ensure_ascii=False,indent=2),encoding="utf-8")
    refs=[f["Moc"],*f["Textures"]]
    for x in ("Physics","DisplayInfo"):refs += [f[x]] if x in f else []
    for motions in f.get("Motions",{}).values():
        refs += [entry["File"] for entry in motions if "File" in entry]
    missing=[r for r in refs if not (output/r).is_file()]
    if missing:raise RuntimeError("Broken native runtime references: "+str(missing))
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    checks={
      "schema":"virtual-pipeline/vts-texture-atlas-lite-v1",
      "native_model_verified":True,"texture_atlas":[2048,2048],
      "texture_atlas_pages":1,
      "original_moc3_sha256":sha(src/f["Moc"]),
      "lite_moc3_sha256":sha(output/f["Moc"]),
      "same_moc3_binary":sha(src/f["Moc"])==sha(output/f["Moc"]),
      "original_physics_sha256":sha(src/f.get("Physics","")) if f.get("Physics") else None,
      "lite_physics_sha256":sha(output/f.get("Physics","")) if f.get("Physics") else None,
      "relative_references_valid":True,
      "cubism_free_editor_artmesh_count_verified":False,
      "cubism_free_editor_deformer_count_verified":False,
      "cubism_free_editor_parameter_count_verified":False,
      "live_cubism_render_verified":False,
      "art_quality_equal_to_original":False,
      "note":"A 2048 texture meets only atlas size; reduced detail and unspecified FREE edition limits remain."}
    (output/"LITE_QA.json").write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding="utf-8")
    return checks

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--model3",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args()
    print(json.dumps(convert(a.model3,a.out),ensure_ascii=False,indent=2))
if __name__=="__main__":main()
