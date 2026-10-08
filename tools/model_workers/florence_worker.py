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

def landmark_fallback_boxes(document, image_size, existing):
    """Emit supported eye/brow/mouth ROIs when Florence lacks tiny anime parts.

    Index groups are grounded in the upstream HRNetV2 28-point keypoint
    ordering (the flip pairs 11..16 <-> 17..22 and 5..7 <-> 8..10).
    Character left is visually on the RIGHT in a frontal RGB reference.
    We only use points when their recorded source pixel frame matches.
    """
    import numpy as np

    if document.get("image_size") != list(image_size):
        return []  # Separate facial close-up requires explicit image registration.
    points = np.asarray(document.get("landmarks", []), dtype=float)
    scores = np.asarray(document.get("landmark_scores", []), dtype=float)
    if points.shape != (28, 2) or not np.isfinite(points).all():
        raise ValueError("HRNet must provide 28 finite 2D landmarks")
    if scores.shape != (28,) or not np.isfinite(scores).all():
        raise ValueError("HRNet must provide 28 finite landmark confidences")

    w, h = image_size
    eyes = [np.arange(11, 17), np.arange(17, 23)]
    brows = [np.arange(5, 8), np.arange(8, 11)]
    eyes.sort(key=lambda group: points[group, 0].mean(), reverse=True)
    brows.sort(key=lambda group: points[group, 0].mean(), reverse=True)
    desired = (
        ("eye.left", eyes[0]), ("eye.right", eyes[1]),
        ("brow.left", brows[0]), ("brow.right", brows[1]),
        ("mouth", np.arange(23, 28)),
    )
    result = []
    for semantic, group in desired:
        if semantic in existing or np.mean(scores[group]) < 0.15:
            continue
        segment = points[group]
        extent = np.ptp(segment, axis=0)
        # A small margin covers the full eyelid or mouth stroke, while
        # remaining grounded in genuinely inferred landmarks.
        margin = np.maximum(4.0, extent * np.array([0.25, 0.45]))
        lower = np.floor(segment.min(axis=0) - margin)
        upper = np.ceil(segment.max(axis=0) + margin)
        x0 = int(np.clip(lower[0], 0, w))
        y0 = int(np.clip(lower[1], 0, h))
        x1 = int(np.clip(upper[0], 0, w))
        y1 = int(np.clip(upper[1], 0, h))
        if x1 <= x0 or y1 <= y0:
            continue
        result.append({
            "semantic_id": semantic, "bbox_xyxy": [x0, y0, x1, y1],
            "source": "anime-face-detector/HRNetV2-28", 
            "score": float(np.mean(scores[group])),
        })
    return result


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
    # Florence's generic open-vocabulary prompt does not reliably distinguish
    # anime eye contours, brows, and mouth. Reuse *measured* HRNet points in
    # their original pixel coordinate system, never imaginary detections.
    landmark_path = Path(req["landmarks_json"])
    if not landmark_path.is_file():
        raise FileNotFoundError(landmark_path)
    landmark_data = json.loads(landmark_path.read_text(encoding="utf-8"))
    parts.extend(landmark_fallback_boxes(
        landmark_data, image.size,
        {p["semantic_id"] for p in parts},
    ))
    if not parts:
        raise RuntimeError("Neither Florence-2 nor aligned HRNet landmarks produced semantic boxes")
    path=Path(req["output_dir"])/"boxes.json"
    path.write_text(json.dumps({"width":image.width,"height":image.height,"parts":parts},ensure_ascii=False,indent=2),encoding="utf-8")
    return {"boxes_json":str(path)}

if __name__=="__main__":
    execute(infer)
