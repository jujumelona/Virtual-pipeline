"""GPU-tiled anime super-resolution for extracted sprite parts.

Model: official Real-ESRGAN release v0.2.5.0 / realesr-animevideov3.pth,
BSD-3-Clause source, SRVGGNetCompact (BSD-3-Clause, Xintao Wang/BasicSR).
Downloads belong to Colab cell ③ only. Inference belongs to cell ⑤.
No interpolated upscale is silently represented as neural super-resolution.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from urllib.request import urlopen

MODEL_URL = (
    "https://github.com/xinntao/Real-ESRGAN/releases/download/"
    "v0.2.5.0/realesr-animevideov3.pth"
)
EXPECTED_BYTES = 2504012  # release asset byte count; not a cryptographic pin
MODEL_NAME = "realesr-animevideov3.pth"
# Explicitly stored provenance binds each inference to the downloaded bytes.
# Upstream does not publish a SHA-256 in the GitHub release API.
CACHE = Path(os.environ.get("VTUBER_SR_CACHE", "/content/vtuber_builder/models/anime_sr"))


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for buf in iter(lambda: f.read(1024 * 1024), b""):
            h.update(buf)
    return h.hexdigest()


def prepare_weights(cache: Path | None = None) -> str:
    """Download only during ③, never when generating or while holding GPU."""
    cache = CACHE if cache is None else Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    weight = cache / MODEL_NAME
    manifest = cache / "asset.json"
    if weight.is_file() and manifest.is_file():
        data = json.loads(manifest.read_text(encoding="utf-8"))
        if (data.get("source") == MODEL_URL
                and data.get("bytes") == EXPECTED_BYTES
                and weight.stat().st_size == EXPECTED_BYTES
                and data.get("sha256") == _sha(weight)):
            print(f"[sheet-sr] verified cached model: {weight}", flush=True)
            return str(weight)
    if os.environ.get("VTUBER_NOTEBOOK_EXPLICIT_DOWNLOAD") == "1":
        # This flag is also set in the ⑤ generation process.
        raise RuntimeError("Anime SR checkpoint not prepared; run Colab cell ③")
    tmp = cache / (MODEL_NAME + ".part")
    tmp.unlink(missing_ok=True)
    try:
        with urlopen(MODEL_URL, timeout=120) as response, tmp.open("wb") as target:
            total = 0
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > EXPECTED_BYTES:
                    raise RuntimeError("Anime SR model exceeds official release size")
                target.write(chunk)
        if tmp.stat().st_size != EXPECTED_BYTES:
            raise RuntimeError(
                f"Anime SR model truncated: got {tmp.stat().st_size} bytes, "
                f"expected {EXPECTED_BYTES}"
            )
        digest = _sha(tmp)
        # Before trusting tensor deserialization, use safe weights_only=True
        # and check the expected architecture keys and tensor dimensions.
        import torch
        obj = torch.load(tmp, map_location="cpu", weights_only=True)
        state = obj.get("params_ema", obj.get("params", obj)) if isinstance(obj, dict) else {}
        if not isinstance(state, dict) or "body.0.weight" not in state:
            raise RuntimeError("Unexpected anime SR model architecture")
        tmp.replace(weight)
        marker = manifest.with_suffix(".tmp")
        marker.write_text(json.dumps({
            "source": MODEL_URL, "bytes": EXPECTED_BYTES,
            "sha256": digest, "license": "BSD-3-Clause",
            "architecture": "SRVGGNetCompact(3,3,64,16,4,prelu)",
        }, indent=2), encoding="utf-8")
        marker.replace(manifest)
        print(f"[sheet-sr] verified weights sha256={digest}", flush=True)
        return str(weight)
    finally:
        tmp.unlink(missing_ok=True)


def _model_class():
    # Architecturally identical to upstream BasicSR srvgg_arch.py, avoiding
    # introducing basicsr/realesrgan's incompatible transitive dependencies.
    import torch
    from torch import nn
    from torch.nn import functional as F

    class AnimeSR(nn.Module):
        def __init__(self):
            super().__init__()
            self.body = nn.ModuleList()
            self.body.append(nn.Conv2d(3, 64, 3, 1, 1))
            self.body.append(nn.PReLU(num_parameters=64))
            for _ in range(16):
                self.body.append(nn.Conv2d(64, 64, 3, 1, 1))
                self.body.append(nn.PReLU(num_parameters=64))
            self.body.append(nn.Conv2d(64, 3 * 16, 3, 1, 1))
            self.upsampler = nn.PixelShuffle(4)

        def forward(self, x):
            out = x
            for layer in self.body:
                out = layer(out)
            return self.upsampler(out) + F.interpolate(
                x, scale_factor=4, mode="nearest"
            )

    return AnimeSR


def load_model(cache: Path | None = None):
    """Fail closed if unavailable: never substitute ordinary PIL upscaling."""
    import torch
    cache = CACHE if cache is None else Path(cache)
    weight = cache / MODEL_NAME
    receipt = cache / "asset.json"
    if not weight.is_file() or not receipt.is_file():
        raise RuntimeError("Anime SR assets missing: complete download cell ③")
    data = json.loads(receipt.read_text(encoding="utf-8"))
    if (data.get("source") != MODEL_URL
            or data.get("bytes") != weight.stat().st_size
            or data.get("sha256") != _sha(weight)):
        raise RuntimeError("Anime SR weights do not match downloaded provenance")
    state = torch.load(weight, map_location="cpu", weights_only=True)
    state = state.get("params_ema", state.get("params", state))
    model = _model_class()()
    model.load_state_dict(state, strict=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = model.eval().to(device)
    if device.type == "cuda":
        model = model.half()
    print("[sheet-sr] REAL neural x4 tiled model loaded on " + str(device),
          flush=True)
    return model


def upscale_rgba(image, model, *, output_scale: int = 2, tile: int = 128):
    """Run neural x4 per tight part bbox; optionally downsample result.

    The semantic ROI positioning is NOT changed: callers place the result at
    (master ROI offset + local bbox) * output_scale on a full canvas.
    """
    import numpy as np
    import torch
    from PIL import Image
    if output_scale not in (1, 2, 4):
        raise ValueError("Neural output scales must be 1x, 2x or 4x")
    if tile < 32 or tile > 256 or tile % 16:
        raise ValueError("tile must be 32..256, multiple of 16")
    if image.mode != "RGBA":
        image = image.convert("RGBA")
    import cv2

    arr = np.asarray(image, dtype=np.uint8)
    # Invisible RGB may contain arbitrary values. Extend edge colors before
    # convolution so no black/white halo appears along transparent outlines.
    rgb = np.array(arr[..., :3], copy=True)
    alpha = np.asarray(image.getchannel("A"), dtype=np.uint8)
    empty = np.uint8(alpha < 4) * 255
    if np.any(empty):
        rgb = cv2.inpaint(rgb, empty, 3, cv2.INPAINT_TELEA)
    h, w = alpha.shape
    result = Image.new("RGB", (w * output_scale, h * output_scale))
    device = next(model.parameters()).device
    dtype = next(model.parameters()).dtype
    pad = 12
    for y in range(0, h, tile):
        for x in range(0, w, tile):
            x0, y0 = max(0,x-pad), max(0,y-pad)
            x1, y1 = min(w,x+tile+pad), min(h,y+tile+pad)
            block = rgb[y0:y1,x0:x1].astype(np.float32) / 255.0
            inp = torch.from_numpy(block.transpose(2,0,1).copy())[None].to(
                device=device, dtype=dtype
            )
            with torch.inference_mode():
                pred = model(inp).clamp_(0,1)
            rgb4 = np.uint8(np.rint(
                pred[0].float().permute(1,2,0).cpu().numpy() * 255.0
            ))
            inset = Image.fromarray(rgb4, "RGB")
            left = (x-x0)*4
            top = (y-y0)*4
            size_x = min(tile,w-x)
            size_y = min(tile,h-y)
            inset = inset.crop((left, top,
                                left+size_x*4, top+size_y*4))
            if output_scale != 4:
                inset = inset.resize((size_x*output_scale,
                                      size_y*output_scale),
                                     Image.Resampling.LANCZOS)
            result.paste(inset,(x*output_scale,y*output_scale))
            del inp, pred
    alpha_out = image.getchannel("A").resize(result.size, Image.Resampling.LANCZOS)
    result.putalpha(alpha_out)
    return result


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", action="store_true")
    args = parser.parse_args()
    if not args.prepare:
        parser.error("Only --prepare is supported; generation uses load_model()")
    prepare_weights()
