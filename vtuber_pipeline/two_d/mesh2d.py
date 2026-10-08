"""Contour-constrained adaptive mesh, source pixel vertices and UVs."""
import json
from pathlib import Path
import numpy as np

def generate_meshes(parts_json: str, output_dir: str) -> dict:
    import cv2
    from scipy.spatial import Delaunay
    from PIL import Image
    obj=json.loads(Path(parts_json).read_text(encoding="utf-8"))
    w,h=obj["width"],obj["height"]
    output=[]
    for part in obj["parts"]:
        mask=np.asarray(Image.open(part["mask_png"]).convert("L"))
        binary=np.uint8(mask>32)
        contours,_=cv2.findContours(binary,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
        contour=max(contours,key=cv2.contourArea)
        if cv2.contourArea(contour)<8:
            continue
        # More vertices for detailed facial parts; sparse for trunk/ornaments.
        fine=any(token in part["semantic_id"] for token in ("eye","mouth","hair","face"))
        step=12 if fine else 32
        approx=cv2.approxPolyDP(contour,1.0 if fine else 3.0,True)[:,0,:]
        x,y,bw,bh=cv2.boundingRect(contour)
        points=[tuple(map(float,p)) for p in approx]
        for gy in range(y+step//2,y+bh,step):
            for gx in range(x+step//2,x+bw,step):
                if binary[min(gy,h-1),min(gx,w-1)]:
                    points.append((float(gx),float(gy)))
        points=list(dict.fromkeys(points))
        if len(points)<3:
            continue
        verts=np.asarray(points,dtype=float)
        triangles=Delaunay(verts).simplices
        accepted=[]
        for tri in triangles:
            center=verts[tri].mean(axis=0)
            cx,cy=np.clip(center.astype(int),[0,0],[w-1,h-1])
            if binary[cy,cx]:
                accepted.append([int(i) for i in tri])
        if not accepted:
            raise ValueError("cannot triangulate " + part["semantic_id"])
        output.append({"semantic_id":part["semantic_id"],"rgba_png":part["rgba_png"],
                       "z_order":part["z_order"],"vertices_xy":verts.tolist(),
                       "uv":[[float(x/w),float(y/h)] for x,y in verts],
                       "triangles":accepted})
    if not output:
        raise ValueError("no triangulated part meshes")
    dest=Path(output_dir)/"meshes2d.json"
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps({"width":w,"height":h,"meshes":output},indent=2),encoding="utf-8")
    return {"meshes_json":str(dest)}
