"""Cubism is the ONLY MOC3 writer. Collect and validate its official files."""
from __future__ import annotations
from pathlib import Path
import json
import shutil
import zipfile
from vtuber_pipeline.common.schemas import BuildResult

def _safe(root, rel):
    if not isinstance(rel, str) or not rel or Path(rel).is_absolute() or ".." in Path(rel).parts:
        raise ValueError("invalid Cubism export reference: "+repr(rel))
    path=(root/rel).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file() or not path.stat().st_size:
        raise FileNotFoundError("missing or unsafe Cubism export reference: "+rel)
    return path

def validate_official_export(folder: str) -> dict:
    root=Path(folder).resolve()
    models=list(root.glob("*.model3.json"))
    if len(models)!=1:
        raise ValueError("need exactly one top-level model3.json")
    refs=json.loads(models[0].read_text(encoding="utf-8")).get("FileReferences")
    if not isinstance(refs, dict):
        raise ValueError("Cubism file references missing")
    moc=refs.get("Moc")
    tex=refs.get("Textures")
    if not isinstance(moc,str) or not moc.endswith(".moc3") or not isinstance(tex,list) or not tex:
        raise ValueError("Cubism MOC3 or textures missing")
    files=[_safe(root,moc)]+[_safe(root,p) for p in tex]
    if any(p.suffix.lower()!=".png" for p in files[1:]):
        raise ValueError("Cubism textures must be PNG")
    for key in ("Physics","Pose","UserData","DisplayInfo"):
        if refs.get(key):
            files.append(_safe(root,refs[key]))
    expressions=refs.get("Expressions",[])
    if not isinstance(expressions,list):
        raise ValueError("invalid expression refs")
    for item in expressions:
        files.append(_safe(root,item["File"]))
    motions=refs.get("Motions",{})
    if not isinstance(motions,dict):
        raise ValueError("invalid motion refs")
    for group in motions.values():
        for item in group:
            files.append(_safe(root,item["File"]))
    return {"moc3":str(files[0]),"model3_json":str(models[0]),
            "files":list(dict.fromkeys([str(models[0])]+[str(p) for p in files]))}

def create_cubism_package(parts_json: str, psd_path: str, meshes_json: str,
                          keyforms_json: str, physics_json: str, output_dir: str) -> dict:
    output=Path(output_dir)
    output.mkdir(parents=True,exist_ok=True)
    sources=[Path(p) for p in (parts_json,psd_path,meshes_json,keyforms_json,physics_json)]
    for path in sources:
        if not path.is_file():raise FileNotFoundError(path)
    parts=json.loads(sources[0].read_text(encoding="utf-8"))
    specification={"format":"cubism-editor-handoff-v1","editor_required":True,
         "parameters":["ParamAngleX","ParamAngleY","ParamAngleZ","ParamEyeLOpen",
            "ParamEyeROpen","ParamMouthOpenY","ParamMouthForm","ParamBodyAngleX",
            "ParamBodyAngleY","ParamBodyAngleZ","ParamBreath"],
         "mesh":json.loads(sources[2].read_text(encoding="utf-8")),
         "keyforms":json.loads(sources[3].read_text(encoding="utf-8")),
         "physics":json.loads(sources[4].read_text(encoding="utf-8"))}
    spec_path=output/"cubism_spec.json"
    spec_path.write_text(json.dumps(specification,ensure_ascii=False,indent=2),encoding="utf-8")
    guide=output/"CUBISM_EDITOR_REQUIRED.txt"
    guide.write_text("Import avatar.psd to Cubism Editor. Apply cubism_spec.json meshes/keyforms/physics manually, save .cmo3 and export .moc3 plus .model3.json and textures. Reimport the exported folder. This archive is NOT a MOC3 model.\n",encoding="utf-8")
    archive=output/"cubism_handoff.zip"
    with zipfile.ZipFile(archive,"w",compression=zipfile.ZIP_DEFLATED) as out:
        for source in [*sources,spec_path,guide]:
            out.write(source,source.name)
        for i,part in enumerate(parts["parts"]):
            p=Path(part["rgba_png"])
            if not p.is_file():raise FileNotFoundError(p)
            out.write(p,"parts/%03d.png"%i)
    return {"art_psd":psd_path,"spec_json":str(spec_path),"handoff_zip":str(archive)}

def collect_official_export(export_folder: str, output_dir: str) -> BuildResult:
    checked=validate_official_export(export_folder)
    src=Path(export_folder).resolve()
    dest=Path(output_dir).resolve()/"official_export"
    if src==dest or dest.is_relative_to(src):
        raise ValueError("cannot import an export inside its own directory")
    dest.mkdir(parents=True,exist_ok=True)
    for item in checked["files"]:
        path=Path(item).resolve()
        target=dest/path.relative_to(src)
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,target)
    copied=validate_official_export(str(dest))
    result=BuildResult("live2d","complete",copied["moc3"],copied["model3_json"],str(dest))
    result.write(output_dir)
    with zipfile.ZipFile(Path(output_dir)/"live2d_official_export.zip","w",compression=zipfile.ZIP_DEFLATED) as out:
        for item in copied["files"]:
            file=Path(item)
            out.write(file,file.relative_to(dest).as_posix())
    return result
