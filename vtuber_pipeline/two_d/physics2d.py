"""Independent spring/damping specifications for secondary motion."""
from pathlib import Path
import json
def build_physics(keyforms_json: str, parts_json: str, output_dir: str) -> dict:
    data=json.loads(Path(parts_json).read_text(encoding="utf-8"))
    entries=[]
    for p in data["parts"]:
        name=p["semantic_id"]
        if not any(t in name for t in ("hair","sleeve","ribbon","earring","accessory","ornament")):
            continue
        left,top,right,bottom=p["bbox_xyxy"]
        entries.append({"semantic_id":name,"pivot_xy":[(left+right)/2,float(top)],
                        "stiffness":15.0 if "hair" in name else 25.0,"damping":0.72,
                        "max_degrees":14 if "hair" in name else 8,
                        "target_parameter":"physics."+name+".sway"})
    out=Path(output_dir)/"physics2d.json";out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps({"springs":entries},indent=2),encoding="utf-8")
    return {"physics_json":str(out)}
