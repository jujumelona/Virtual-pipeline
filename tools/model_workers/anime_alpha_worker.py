from pathlib import Path
import os
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _entry import execute

def prepare_input(rgb, side=1024):
    """Match pinned SkyTNT inference: normalized float CV2 linear resize."""
    import cv2
    import numpy as np
    h, w = rgb.shape[:2]
    h, w = ((side, max(1, int(side * w / h))) if h > w else
            (max(1, int(side * h / w)), side))
    offset = ((side-w)//2, (side-h)//2)
    padded = np.zeros((side, side, 3), dtype=np.float32)
    padded[offset[1]:offset[1]+h, offset[0]:offset[0]+w] = cv2.resize(
        (rgb / 255).astype(np.float32), (w, h))
    return padded, (w, h), offset


def restore_alpha(prediction, size, offset, original_size, side=1024):
    """Validate mask frame, crop padding, then resize before quantization."""
    import cv2
    import numpy as np
    if (prediction.shape != (1, 1, side, side)
            or not np.isfinite(prediction).all()):
        raise RuntimeError("Anime segmentation returned invalid alpha prediction")
    x, y = offset
    w, h = size
    alpha = cv2.resize(prediction[0, 0, y:y+h, x:x+w], original_size)
    return np.uint8(np.clip(alpha, 0, 1) * 255)


def infer(req):
    from vtuber_pipeline.common.model_assets import resolve_snapshot
    snapshot = resolve_snapshot('skytnt_anime_seg_isnet_is')
    import numpy as np
    from PIL import Image
    import torch
    upstream = os.environ.get("ANIME_SEGMENTATION_REPO")
    if not upstream or not (Path(upstream)/"train.py").is_file():
        raise RuntimeError("ANIME_SEGMENTATION_REPO must point to checked-out official anime-segmentation")
    sys.path.insert(0, upstream)
    from train import AnimeSegmentation
    img = Image.open(req["image_path"]).convert("RGBA")
    source = np.asarray(img).copy()
    padded, size, offset = prepare_input(source[:, :, :3])
    device = "cuda" if torch.cuda.is_available() else "cpu"
    net = AnimeSegmentation.from_pretrained(snapshot).to(device).eval()
    tensor = torch.from_numpy(padded).permute(2,0,1).unsqueeze(0).to(device)
    with torch.inference_mode():
        prediction = net(tensor).float().detach().cpu().numpy()
    alpha = restore_alpha(prediction, size, offset, img.size)
    a = np.minimum(alpha, source[:,:,3])
    out = Path(req["output_dir"])
    out.mkdir(parents=True, exist_ok=True)
    alpha_path, rgba_path = out/"person_alpha.png", out/"person.png"
    Image.fromarray(a, "L").save(alpha_path)
    source[:,:,3] = a
    Image.fromarray(source, "RGBA").save(rgba_path)
    return {"alpha_png": str(alpha_path), "rgba_png": str(rgba_path)}

if __name__ == "__main__":
    execute(infer)
