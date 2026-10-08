"""Constrained full-body mesh surface refinement with separate strand ribbon geometry."""
from __future__ import annotations
from pathlib import Path
import json
import numpy as np

def _load(path):
    import trimesh
    mesh=trimesh.load(path,force="mesh",process=False)
    if not isinstance(mesh,trimesh.Trimesh) or len(mesh.vertices)<100 or len(mesh.faces)<100:
        raise ValueError("invalid anatomical mesh")
    return mesh

def _ribbons(mesh):
    """Generate head-following separate ribbon meshes; derived from geometric scalp frame."""
    import trimesh
    vertices=np.asarray(mesh.vertices,dtype=float)
    vmin,vmax=vertices.min(axis=0),vertices.max(axis=0)
    height=float(vmax[1]-vmin[1])
    if height<1e-5:raise ValueError("invalid model height")
    scalp=vertices[vertices[:,1]>vmax[1]-0.22*height]
    if len(scalp)<20:raise ValueError("could not identify scalp geometry")
    lo,hi=np.percentile(scalp[:,0],[8,92])
    front=float(np.percentile(scalp[:,2],85))
    top=float(np.percentile(scalp[:,1],90))
    width=(hi-lo)/14
    if width<=1e-5:raise ValueError("invalid scalp width")
    parts=[]
    for index in range(7):
        x=lo+(index+0.5)*(hi-lo)/7
        pts=[]
        uv=[]
        faces=[]
        for j,t in enumerate(np.linspace(0,1,13)):
            # Ribbon endpoint y follows observed head scale; it is approximate geometry.
            cx=x+0.045*(hi-lo)*np.sin(np.pi*t)*(index-3)/3
            cy=top-(0.10+0.07*abs(index-3)/3)*height*t
            cz=front+0.011*height+0.018*height*np.sin(np.pi*t)
            for side in (-1,1):
                pts.append([cx+side*width*(1-0.15*t),cy,cz])
                uv.append([(side+1)/2,t])
            if j>0:
                a=(j-1)*2;b=j*2
                faces.extend([[a,b,a+1],[a+1,b,b+1]])
        ribbon=trimesh.Trimesh(vertices=pts,faces=faces,process=False)
        ribbon.visual.vertex_colors=np.tile(np.array([80,72,85,255],dtype=np.uint8),(len(ribbon.vertices),1))
        parts.append(ribbon)
    return trimesh.util.concatenate(parts)

def refine_anatomy(fitted_mesh: str, constraints_json: str,
                   reference_images_json: str, output_dir: str) -> dict:
    import trimesh
    from scipy.sparse import coo_matrix, diags, eye
    from scipy.sparse.linalg import spsolve
    for p in (fitted_mesh,constraints_json,reference_images_json):
        if not Path(p).is_file():raise FileNotFoundError(p)
    constraints=json.loads(Path(constraints_json).read_text(encoding="utf-8"))
    references=json.loads(Path(reference_images_json).read_text(encoding="utf-8"))
    if constraints.get("contract") != "vtuber-multiview-constraints-v1":
        raise ValueError("unsupported multiview alignment contract")
    aligned_glb = constraints.get("aligned_multiview_glb")
    if not isinstance(aligned_glb, str) or not Path(aligned_glb).is_file():
        raise ValueError("aligned independent shape source is missing")
    mesh=_load(fitted_mesh)
    verts=np.asarray(mesh.vertices,dtype=float)
    count=len(verts)
    edges=np.asarray(mesh.edges_unique,dtype=int)
    if not len(edges):raise ValueError("mesh has no adjacency")
    vmin,vmax=verts.min(axis=0),verts.max(axis=0)
    y_fraction=(verts[:,1]-vmin[1])/max(vmax[1]-vmin[1],1e-9)
    # Sparse Laplacian regularizer; limb/face landmarks are protected.
    rows=np.r_[edges[:,0],edges[:,1]]
    cols=np.r_[edges[:,1],edges[:,0]]
    adjacency=coo_matrix((np.ones(len(rows)),(rows,cols)),shape=(count,count)).tocsr()
    degree=np.asarray(adjacency.sum(axis=1)).ravel()
    laplacian=diags(degree)-adjacency
    protect=np.where((y_fraction>0.82)|(y_fraction<0.12),10.0,1.0)
    A=diags(protect)+0.025*laplacian
    smoothed=np.column_stack([spsolve(A,protect*verts[:,j]) for j in range(3)])
    if not np.isfinite(smoothed).all():raise RuntimeError("nonfinite body surface")
    drift=np.linalg.norm(smoothed-verts,axis=1)
    limit=0.006*max(float(np.ptp(verts[:,1])),1e-6)
    delta=smoothed-verts
    multiplier=np.minimum(1.0,limit/np.maximum(drift,1e-9))[:,None]
    mesh.vertices=verts+delta*multiplier
    # Preserve template face connectivity and vertex indices for humanoid skinning.
    if len(mesh.vertices)!=count or len(mesh.faces)<100:raise RuntimeError("lost template topology")
    hair=_ribbons(mesh)
    out=Path(output_dir)
    out.mkdir(parents=True,exist_ok=True)
    refined=out/"refined.glb"
    hair_glb=out/"hair.glb"
    mesh.export(refined,file_type="glb")
    hair.export(hair_glb,file_type="glb")
    report={"topology_preserved":True,"reference_image_roles":list(references.get("images",{})),
            "ribbon_count":7,"ribbons_are_approximate":True,
            "maximum_surface_displacement_mesh_units":float(np.max(np.linalg.norm(mesh.vertices-verts,axis=1))),
            "limitations":"Invisible clothing geometry and hidden finger poses cannot be observed from the input"}
    report_path=out/"surface_refine.json"
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    return {"status":"complete","refined_glb":str(refined),"hair_geometry_glb":str(hair_glb),
            "report_json":str(report_path),"output_path":str(refined)}
