from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from _entry import execute

def parse_boxes(parsed, semantic, image_size):
    """Florence open-vocabulary outputs bboxes_labels, unlike OD's labels."""
    import math
    boxes = parsed.get('bboxes', [])
    labels = parsed.get('bboxes_labels', parsed.get('labels', []))
    if len(boxes) != len(labels):
        raise ValueError('Florence bbox/label count mismatch')
    parts = []
    for box, label in zip(boxes, labels):
        if len(box) != 4 or not all(math.isfinite(v) for v in box):
            raise ValueError('invalid Florence coordinates')
        coords = [max(0, min(round(v), image_size[i % 2])) for i, v in enumerate(box)]
        if coords[2] <= coords[0] or coords[3] <= coords[1]:
            continue
        parts.append({'semantic_id': semantic, 'bbox_xyxy': coords,
                      'source': 'Florence-2-base', 'score': None, 'detected_label': label})
    return parts

def infer(req):
    from vtuber_pipeline.common.model_assets import resolve_snapshot
    snapshot = resolve_snapshot('florence2_base')
    import json
    import torch
    from PIL import Image
    from transformers import AutoProcessor, AutoModelForCausalLM
    from vtuber_pipeline.common.part_taxonomy import SEMANTIC_PROMPTS
    image=Image.open(req["image_path"]).convert("RGB")
    device="cuda" if torch.cuda.is_available() else "cpu"
    name=snapshot
    processor=AutoProcessor.from_pretrained(name, trust_remote_code=True)
    model=AutoModelForCausalLM.from_pretrained(name, trust_remote_code=True).to(device).eval()
    parts=[]
    # Open-vocabulary detection is grounded in model-returned boxes; no phantom parts.
    for semantic,prompt in SEMANTIC_PROMPTS.items():
        task="<OPEN_VOCABULARY_DETECTION>"
        text=task+prompt
        inputs=processor(text=text,images=image,return_tensors="pt").to(device)
        with torch.inference_mode():
            generated=model.generate(**inputs,max_new_tokens=256,num_beams=3,do_sample=False)
        decoded=processor.batch_decode(generated,skip_special_tokens=False)[0]
        parsed=processor.post_process_generation(decoded,task=task,image_size=image.size).get(task,{})
        parts.extend(parse_boxes(parsed, semantic, image.size))
    if not parts:
        raise RuntimeError("Florence-2 found no usable semantic part bounding boxes")
    path=Path(req["output_dir"])/"boxes.json"
    path.write_text(json.dumps({"width":image.width,"height":image.height,"parts":parts},ensure_ascii=False,indent=2),encoding="utf-8")
    return {"boxes_json":str(path)}

if __name__=="__main__":
    execute(infer)
