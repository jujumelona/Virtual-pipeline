from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from _entry import execute

def infer(req):
    import torch
    import numpy as np
    from PIL import Image
    from sam2.sam2_image_predictor import SAM2ImagePredictor
    from sam2.build_sam import build_sam2
    from vtuber_pipeline.common.model_assets import resolve_snapshot
    checkpoint = Path(resolve_snapshot("sam2_1_hiera_large"))/"sam2.1_hiera_large.pt"
    image = np.asarray(Image.open(req["image_path"]).convert("RGB"))
    alpha=np.asarray(Image.open(req["person_alpha_png"]).convert("L"))
    data=json.loads(Path(req["boxes_json"]).read_text(encoding="utf-8"))
    predictor=SAM2ImagePredictor(build_sam2("configs/sam2.1/sam2.1_hiera_l.yaml",
        str(checkpoint), device="cuda" if torch.cuda.is_available() else "cpu"))
    predictor.set_image(image)
    folder=Path(req["output_dir"])/"part_masks"
    folder.mkdir(parents=True, exist_ok=True)
    results=[]
    for i,item in enumerate(data["parts"]):
        with torch.inference_mode():
            masks,scores,_=predictor.predict(box=np.array(item["bbox_xyxy"],dtype=np.float32),multimask_output=False)
        # Official predictor outputs CxHxW in the original image frame and
        # one quality score per mask. Never broadcast a malformed prediction
        # or silently threshold nonfinite logits into missing artwork pixels.
        masks, scores = np.asarray(masks), np.asarray(scores)
        if (masks.shape != (1, *image.shape[:2]) or scores.shape != (1,)
                or not np.isfinite(masks).all() or not np.isfinite(scores).all()):
            raise RuntimeError("SAM2 returned invalid single-mask prediction")
        mask=np.where((masks[0]>0) & (alpha>10),255,0).astype("uint8")
        x0,y0,x1,y1=item["bbox_xyxy"]
        rect=np.zeros_like(mask)
        rect[y0:y1,x0:x1]=255
        mask &= rect
        if not np.any(mask):
            continue
        path=folder/("part_%03d.png"%i)
        Image.fromarray(mask,"L").save(path)
        results.append({**item,"mask_png":str(path),"score":float(scores[0])})
    if not results:
        raise RuntimeError("SAM2 did not resolve any nonempty masks")
    index=Path(req["output_dir"])/"masks.json"
    index.write_text(json.dumps({"parts":results},ensure_ascii=False,indent=2),encoding="utf-8")
    return {"mask_dir":str(folder),"index_json":str(index)}

if __name__=="__main__":
    execute(infer)
