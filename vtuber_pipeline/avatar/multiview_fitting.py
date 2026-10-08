"""Align independent TripoSR and InstantMesh meshes as uncertain shape constraints."""
from __future__ import annotations
from pathlib import Path
import itertools
import json
import math
import numpy as np

def _mesh(path):
    import trimesh
    model=trimesh.load(path,force="mesh",process=False)
    if not isinstance(model,trimesh.Trimesh) or len(model.faces)<32 or len(model.vertices)<64:
        raise ValueError("no valid 3D triangle mesh: "+str(path))
    if not np.isfinite(model.vertices).all():
        raise ValueError("nonfinite mesh vertices")
    return model

def _basis_rotations():
    # Enumerate proper signed axis permutations (no parity/reflection inversions).
    for axes in itertools.permutations(range(3)):
        matrix=np.zeros((3,3),dtype=float)
        for flips in itertools.product((-1.0,1.0),repeat=3):
            for i,ax in enumerate(axes):matrix[i,ax]=flips[i]
            if np.linalg.det(matrix)>0.99:
                yield matrix.copy()
            matrix.fill(0)

def _fit_candidate(source, target, rotation):
    from scipy.spatial import cKDTree
    rotated=source @ rotation.T
    bbox=np.ptp(rotated,axis=0)
    target_bbox=np.ptp(target,axis=0)
    # Height dominates normalization to preserve proportions and remove unknown model units.
    ratios=target_bbox / np.maximum(bbox,1e-8)
    scale=float(np.median(ratios))
    estimate=(rotated-rotated.mean(axis=0))*scale+target.mean(axis=0)
    tree=cKDTree(target)
    distances=tree.query(estimate,k=1,workers=-1)[0]
    penalty=np.percentile(distances,80)+np.median(distances)
    return scale, estimate, distances, float(penalty)

def align_sources(coarse_obj: str, multiview_obj: str,
                  depth_manifest: str, reference_manifest: str,
                  output_dir: str) -> dict:
    """Strict geometry/coordinate normalization; never call rendered views observed."""
    import trimesh
    for file in (coarse_obj,multiview_obj,depth_manifest,reference_manifest):
        if not Path(file).is_file():raise FileNotFoundError(file)
    coarse=_mesh(coarse_obj)
    alternative=_mesh(multiview_obj)
    depth=json.loads(Path(depth_manifest).read_text(encoding="utf-8"))
    refs=json.loads(Path(reference_manifest).read_text(encoding="utf-8"))
    if depth.get("units")!="relative/no-metric-scale":
        raise ValueError("unrecognized relative depth coordinate contract")
    if "front" not in depth.get("views",{}):
        raise ValueError("measured front-view depth is mandatory")
    coarse_samples=np.asarray(coarse.vertices,dtype=float)
    other_samples=np.asarray(alternative.vertices,dtype=float)
    rng=np.random.default_rng(0)
    if len(other_samples)>8000:
        sample=other_samples[rng.choice(len(other_samples),size=8000,replace=False)]
    else:sample=other_samples
    if len(coarse_samples)>12000:
        targets=coarse_samples[rng.choice(len(coarse_samples),size=12000,replace=False)]
    else:targets=coarse_samples
    best=None
    for rot in _basis_rotations():
        scale, transformed, distances, score=_fit_candidate(sample,targets,rot)
        if not 0.01 < scale < 100:
            continue
        if best is None or score<best[0]:
            best=(score,rot,scale)
    if best is None:raise RuntimeError("could not normalize TripoSR/InstantMesh coordinate systems")
    score,rot,scale=best
    center_src=other_samples.mean(axis=0)
    center_dest=coarse_samples.mean(axis=0)
    alternative.vertices=((other_samples-center_src)@rot.T)*scale+center_dest
    out=Path(output_dir)
    out.mkdir(parents=True,exist_ok=True)
    aligned=out/"aligned_multiview.glb"
    alternative.export(str(aligned),file_type="glb")
    from scipy.spatial import cKDTree
    distances=cKDTree(np.asarray(alternative.vertices)).query(coarse_samples,k=1)[0]
    median=float(np.median(distances))
    p95=float(np.percentile(distances,95))
    if not math.isfinite(p95):raise RuntimeError("invalid model alignment residuals")
    box=np.ptp(coarse_samples,axis=0)
    height=max(float(np.max(box)),1e-6)
    # Region conf is an uncertainty prior; it is not a semantic classifier.
    conf=np.exp(-np.clip(distances/height,0,10)*8)
    metrics={"median_distance":median,"p95_distance":p95,"normalized_p95":p95/height,
             "confidence_mean":float(conf.mean())}
    manifest=out/"constraints.json"
    manifest.write_text(json.dumps({"schema":"aligned-multiview-v1",
         "target_geometry":str(Path(coarse_obj).resolve()),
         "aligned_multiview":str(aligned),"axis_rotation":rot.tolist(),
         "scale_to_coarse":scale,"center_to_coarse":center_dest.tolist(),
         "depth_manifest":str(Path(depth_manifest).resolve()),
         "reference_manifest":str(Path(reference_manifest).resolve()),
         "observed_views":sorted(k for k,v in depth["views"].items() if v.get("observed_view")),
         "generated_views_are_observed":False,"metric_depth_available":False,
         "alignment_metrics":metrics,"per_vertex_confidence":conf.astype("float32").tolist()},
         ensure_ascii=False,indent=2),encoding="utf-8")
    return {"constraints_json":str(manifest),"aligned_multiview_glb":str(aligned),
            "alignment_metrics":metrics}
