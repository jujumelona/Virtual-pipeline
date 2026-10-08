"""Run the real official InstantMesh large CLI, not a mesh placeholder."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from _entry import execute

def infer(req):
    upstream=Path(os.environ.get("INSTANTMESH_DIR","")).expanduser().resolve()
    runner=upstream/"run.py"
    config=upstream/"configs/instant-mesh-large.yaml"
    if not runner.is_file() or not config.is_file():
        raise RuntimeError("INSTANTMESH_DIR must contain pinned TencentARC/InstantMesh run.py and configs/instant-mesh-large.yaml")
    source=Path(req["front_rgba"]).resolve()
    if not source.is_file():raise FileNotFoundError(source)
    out=Path(req["output_dir"]).resolve()
    out.mkdir(parents=True,exist_ok=True)
    # upstream expects one image or directory and puts OBJ under <out>/<config>/meshes/
    command=[sys.executable,str(runner),str(config),str(source),"--output_path",str(out),
             "--no_rembg","--diffusion_steps","75"]
    timeout=int(os.getenv("INSTANTMESH_TIMEOUT_SEC","3300"))
    with (out/"instantmesh_upstream.log").open("w",encoding="utf-8") as log:
        proc=subprocess.run(command,cwd=str(upstream),stdout=log,stderr=subprocess.STDOUT,timeout=timeout)
    if proc.returncode:
        raise RuntimeError("InstantMesh large failed exit="+str(proc.returncode)+"; see "+str(out/"instantmesh_upstream.log"))
    folder=out/"instant-mesh-large"
    candidate=folder/"meshes"/(source.stem+".obj")
    if not candidate.is_file() or candidate.stat().st_size<=128:
        raise RuntimeError("InstantMesh did not output expected OBJ: "+str(candidate))
    import trimesh
    mesh=trimesh.load_mesh(candidate,process=False)
    if len(mesh.vertices)<100 or len(mesh.faces)<100:
        raise RuntimeError("InstantMesh result has no usable geometry")
    dest=out/"multiview_mesh.obj"
    dest.write_bytes(candidate.read_bytes())
    # Predicted multi-view images are inferred and NEVER marked as user observations.
    predicted=folder/"images"
    cam=out/"instantmesh_camera.json"
    cam.write_text(json.dumps({"origin_model":"TencentARC/InstantMesh",
        "mesh_source":str(candidate),"front_input":str(source),"observed_views":["front"],
        "inferred_views":["model_generated"],"observed_view":False,
        "units":"unknown","camera":"inferred not physically calibrated"},indent=2),encoding="utf-8")
    return {"mesh_obj":str(dest),"camera_json":str(cam),"render_dir":str(predicted) if predicted.is_dir() else str(folder)}

if __name__=="__main__":
    execute(infer)
