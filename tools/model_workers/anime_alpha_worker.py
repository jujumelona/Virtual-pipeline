from pathlib import Path
import os
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _entry import execute

def infer(req):
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
    rgb = Image.fromarray(source[:, :, :3], "RGB")
    side = 1024
    scale = min(side / rgb.width, side / rgb.height)
    size = (max(1, round(rgb.width*scale)), max(1, round(rgb.height*scale)))
    small = rgb.resize(size, Image.Resampling.BILINEAR)
    padded = Image.new("RGB", (side,side))
    offset = ((side-size[0])//2, (side-size[1])//2)
    padded.paste(small, offset)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    net = AnimeSegmentation.from_pretrained("skytnt/anime-seg").to(device).eval()
    tensor = torch.from_numpy(np.asarray(padded).copy()).permute(2,0,1).unsqueeze(0).float().div(255).to(device)
    with torch.inference_mode():
        alpha = net(tensor).float().detach().cpu().numpy().squeeze()
    alpha = Image.fromarray(np.uint8(np.clip(alpha,0,1)*255), "L")
    alpha = alpha.crop((offset[0],offset[1],offset[0]+size[0],offset[1]+size[1]))
    alpha = alpha.resize(rgb.size, Image.Resampling.BILINEAR)
    a = np.minimum(np.asarray(alpha), source[:,:,3])
    out = Path(req["output_dir"])
    out.mkdir(parents=True, exist_ok=True)
    alpha_path, rgba_path = out/"person_alpha.png", out/"person.png"
    Image.fromarray(a, "L").save(alpha_path)
    source[:,:,3] = a
    Image.fromarray(source, "RGBA").save(rgba_path)
    return {"alpha_png": str(alpha_path), "rgba_png": str(rgba_path)}

if __name__ == "__main__":
    execute(infer)
