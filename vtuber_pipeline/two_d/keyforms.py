"""Analytic per-vertex local 2.5D deformation data; no global rotate-only cheats."""
from pathlib import Path
import json
import math
import numpy as np
PARAMS={
 "head.angle_x":(-30,0,30), "head.angle_y":(-20,0,20),
 "head.angle_z":(-30,0,30), "eye.left.open":(0,1,1),
 "eye.right.open":(0,1,1), "eye.x":(-1,0,1), "eye.y":(-1,0,1),
 "brow.left.y":(-1,0,1), "brow.right.y":(-1,0,1),
 "mouth.open":(0,0,1), "mouth.form":(-1,0,1),
 "body.angle_x":(-15,0,15),"body.angle_y":(-15,0,15),
 "body.angle_z":(-15,0,15),"breath":(0,0,1),
}
def build_keyforms(meshes_json: str, parts_json: str,
                   face_landmarks_json: str, output_dir: str) -> dict:
    src=json.loads(Path(meshes_json).read_text(encoding="utf-8"))
    entries=[]
    for m in src["meshes"]:
        verts=np.asarray(m["vertices_xy"],dtype=float)
        center=verts.mean(axis=0)
        span=np.maximum(verts.max(axis=0)-verts.min(axis=0),1)
        part=m["semantic_id"]
        deltas={}
        for p,(low,mid,hi) in PARAMS.items():
            if p.startswith("head.") and not any(n in part for n in ("hair","eye","face","mouth","brow","neck")):
                continue
            if p.startswith("body.") and not any(n in part for n in ("body","arm","cloth","leg")):
                continue
            if p.startswith("eye.left") and "eye.left" not in part: continue
            if p.startswith("eye.right") and "eye.right" not in part: continue
            if p.startswith("eye.") and not ("eye" in part): continue
            if p.startswith("mouth.") and "mouth" not in part: continue
            if p.startswith("brow.left") and "brow.left" not in part: continue
            if p.startswith("brow.right") and "brow.right" not in part: continue
            if p=="breath" and not any(x in part for x in ("body","cloth")): continue
            v=verts-center
            if p.endswith("angle_x"):
                # Nonuniform deformation varies with vertical extent and part position.
                dx=0.16*span[0]*(1-(v[:,1]/span[1])**2)+0.25*v[:,0]
                dy=-0.07*v[:,0]
            elif p.endswith("angle_y"):
                dx=0.10*v[:,0]*(v[:,1]/span[1])
                dy=-0.25*v[:,1]+0.09*span[1]*(v[:,0]/span[0])**2
            elif p.endswith("angle_z"):
                dx=-v[:,1]
                dy=v[:,0]
            elif p.endswith(".open"):
                dx=np.zeros(len(v))
                dy=v[:,1]*0.65
            elif p.endswith(".form"):
                dx=-v[:,0]*0.25
                dy=v[:,1]*0.10
            elif p=="eye.x": dx=np.full(len(v),0.12*span[0]);dy=np.zeros(len(v))
            elif p=="eye.y": dx=np.zeros(len(v));dy=np.full(len(v),0.12*span[1])
            elif p.endswith(".y"):dx=np.zeros(len(v));dy=np.full(len(v),0.20*span[1])
            elif p=="breath":dx=v[:,0]*0.018;dy=-np.full(len(v),0.012*span[1])
            else:continue
            amount=math.radians(hi) if "angle" in p else hi-mid
            plus=np.column_stack((dx,dy))*amount
            minus=-plus
            deltas[p]={"min":minus.tolist(),"default":np.zeros_like(plus).tolist(),"max":plus.tolist()}
        entries.append({"semantic_id":part,"deltas":deltas})
    out=Path(output_dir)/"keyforms.json";out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps({"parameters":{k:list(v) for k,v in PARAMS.items()},
                               "keyforms":entries},indent=2),encoding="utf-8")
    return {"keyforms_json":str(out)}
