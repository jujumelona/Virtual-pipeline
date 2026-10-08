"""Pinned relative depth image inference with one model load and no fictitious metric scale."""
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from _entry import execute

def infer(req):
    import numpy as np
    from PIL import Image
    import torch
    from transformers import pipeline
    out=Path(req["output_dir"])
    out.mkdir(parents=True,exist_ok=True)
    model="depth-anything/Depth-Anything-V2-Small-hf"
    estimator=pipeline(task="depth-estimation",model=model,device=0 if torch.cuda.is_available() else -1)
    views={}
    for role,path in req["images"].items():
        if not path:
            continue
        img=Image.open(path).convert("RGB")
        prediction=estimator(img)
        depth=prediction.get("predicted_depth")
        if depth is None:
            raise RuntimeError("Depth Anything V2 Small returned no numeric predicted_depth")
        if hasattr(depth,"detach"):
            depth=depth.detach().float().cpu().numpy()
        value=np.asarray(depth,dtype=np.float32).squeeze()
        if value.ndim!=2 or not np.isfinite(value).all():
            raise RuntimeError(role+": invalid depth prediction")
        if value.shape!=(img.height,img.width):
            value=np.asarray(Image.fromarray(value,mode="F").resize(img.size,Image.Resampling.BILINEAR),
                             dtype=np.float32)
        saved=out/("depth_"+role+".npy")
        np.save(saved,value,allow_pickle=False)
        views[role]={"depth_npy":str(saved),"relative_depth":True,"observed_view":True,
                     "source_image":str(Path(path).resolve()),"image_size":[img.width,img.height]}
    manifest=out/"depth_manifest.json"
    manifest.write_text(json.dumps({"model":model,"units":"relative/no-metric-scale","views":views},
                                    ensure_ascii=False,indent=2),encoding="utf-8")
    return {
        "depth_manifest": str(manifest),
        "manifest_json": str(manifest),
        **{"depth_" + key: data["depth_npy"] for key, data in views.items()},
        **{"depth_" + key + "_npy": data["depth_npy"] for key, data in views.items()},
    }

if __name__=="__main__":
    execute(infer)
