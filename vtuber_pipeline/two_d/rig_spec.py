"""Portable rig spec is NOT an Inochi INP or Cubism CMO3 binary."""
from pathlib import Path
import json

def build_puppet_spec(parts_json: str, meshes_json: str, keyforms_json: str,
                      physics_json: str, atlas_dir: str, output_json: str) -> str:
    parts=json.loads(Path(parts_json).read_text(encoding="utf-8"))
    meshes=json.loads(Path(meshes_json).read_text(encoding="utf-8"))
    keyforms=json.loads(Path(keyforms_json).read_text(encoding="utf-8"))
    physics=json.loads(Path(physics_json).read_text(encoding="utf-8"))
    pnames={p["semantic_id"] for p in parts["parts"]}
    mnames={m["semantic_id"] for m in meshes["meshes"]}
    if not mnames.issubset(pnames):
        raise ValueError("mesh-to-part references are broken")
    result={"schema":"vtuber-puppet-interchange-v1","canvas":[parts["width"],parts["height"]],
            "textures":[p["rgba_png"] for p in parts["parts"]],
            "parts":parts["parts"],"mesh":meshes["meshes"],
            "parameters":keyforms["parameters"],"keyforms":keyforms["keyforms"],
            "physics":physics["springs"],"draw_order":[p["semantic_id"] for p in
                        sorted(parts["parts"],key=lambda x:x["z_order"])]}
    out=Path(output_json);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    return str(out)
