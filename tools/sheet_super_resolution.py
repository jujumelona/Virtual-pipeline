"""GPU-tiled anime super-resolution for extracted sprite parts.

Model: official Real-ESRGAN release v0.2.2.4 / RealESRGAN_x4plus_anime_6B.pth,
BSD-3-Clause source, RRDBNet 6-block architecture (BSD-3-Clause, Xintao Wang/BasicSR).
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
    "v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth"
)
EXPECTED_BYTES = 17938799  # release asset byte count; not a cryptographic pin
MODEL_NAME = "RealESRGAN_x4plus_anime_6B.pth"
# Independently observed from the official v0.2.2.4 release asset; not a
# publisher-provided checksum. Bind caches and subsequent downloads to it.
EXPECTED_SHA256 = "f872d837d3c90ed2e05227bed711af5671a6fd1c9f7d7e91c911a61f155e99da"
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
                and data.get("sha256") == EXPECTED_SHA256 == _sha(weight)):
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
        if digest != EXPECTED_SHA256:
            raise RuntimeError("Official anime 6B asset digest mismatch")
        # Before trusting tensor deserialization, use safe weights_only=True
        # and check the expected architecture keys and tensor dimensions.
        import torch
        obj = torch.load(tmp, map_location="cpu", weights_only=True)
        state = obj.get("params_ema", obj.get("params", obj)) if isinstance(obj, dict) else {}
        if not isinstance(state, dict) or "body.5.rdb3.conv5.weight" not in state:
            raise RuntimeError("Unexpected anime SR model architecture")
        tmp.replace(weight)
        marker = manifest.with_suffix(".tmp")
        marker.write_text(json.dumps({
            "source": MODEL_URL, "bytes": EXPECTED_BYTES,
            "sha256": digest, "license": "BSD-3-Clause",
            "architecture": "RRDBNet(3,3,64,6,32,4)",
        }, indent=2), encoding="utf-8")
        marker.replace(manifest)
        print(f"[sheet-sr] verified weights sha256={digest}", flush=True)
        return str(weight)
    finally:
        tmp.unlink(missing_ok=True)


def _model_class():
    # Inference-only equivalent of BasicSR RRDBNet(3,3,64,6,32,scale=4).
    # Original architecture: Xintao Wang / BasicSR, BSD-3-Clause.
    # https://github.com/XPixelGroup/BasicSR/blob/master/basicsr/archs/rrdbnet_arch.py
    # Omit random training initialization: strict checkpoint loading replaces it.
    import torch
    from torch import nn
    from torch.nn import functional as F

    class DenseBlock(nn.Module):
        def __init__(self):
            super().__init__()
            for index in range(1, 6):
                setattr(self, f"conv{index}", nn.Conv2d(
                    64 + 32 * (index - 1), 64 if index == 5 else 32, 3, 1, 1))

        def forward(self, x):
            features = [x]
            for index in range(1, 5):
                features.append(F.leaky_relu(
                    getattr(self, f"conv{index}")(torch.cat(features, dim=1)), 0.2))
            return x + 0.2 * self.conv5(torch.cat(features, dim=1))

    class RRDB(nn.Module):
        def __init__(self):
            super().__init__()
            self.rdb1, self.rdb2, self.rdb3 = DenseBlock(), DenseBlock(), DenseBlock()

        def forward(self, x):
            return x + 0.2 * self.rdb3(self.rdb2(self.rdb1(x)))

    class AnimeSR(nn.Module):
        def __init__(self):
            super().__init__()
            self.conv_first = nn.Conv2d(3, 64, 3, 1, 1)
            self.body = nn.Sequential(*(RRDB() for _ in range(6)))
            for name in ("conv_body", "conv_up1", "conv_up2", "conv_hr"):
                setattr(self, name, nn.Conv2d(64, 64, 3, 1, 1))
            self.conv_last = nn.Conv2d(64, 3, 3, 1, 1)

        def forward(self, x):
            features = self.conv_first(x)
            features = features + self.conv_body(self.body(features))
            for layer in (self.conv_up1, self.conv_up2):
                features = F.leaky_relu(layer(F.interpolate(
                    features, scale_factor=2, mode="nearest")), 0.2)
            return self.conv_last(F.leaky_relu(self.conv_hr(features), 0.2))

    return AnimeSR


def load_model(cache: Path | None = None):
    """Fail closed if unavailable: never substitute ordinary PIL upscaling."""
    from tools.model_workers._entry import require_cuda
    require_cuda()
    import torch
    cache = CACHE if cache is None else Path(cache)
    weight = cache / MODEL_NAME
    receipt = cache / "asset.json"
    if not weight.is_file() or not receipt.is_file():
        raise RuntimeError("Anime SR assets missing: complete download cell ③")
    data = json.loads(receipt.read_text(encoding="utf-8"))
    if (data.get("source") != MODEL_URL
            or data.get("bytes") != weight.stat().st_size
            or data.get("bytes") != EXPECTED_BYTES
            or data.get("sha256") != EXPECTED_SHA256
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


def _finish_rgba(rgb4, alpha, *, output_scale):
    """Official non-neural alpha option + one full-canvas outscale.

    Upstream calls this alpha option 'bicubic', but utils.py implements
    INTER_LINEAR at native x4, then INTER_LANCZOS4 on the merged RGBA.
    https://github.com/xinntao/Real-ESRGAN/blob/master/realesrgan/utils.py
    """
    import cv2
    import numpy as np
    from PIL import Image
    h, w = alpha.shape
    if output_scale not in (1, 2, 4):
        raise ValueError("Neural output scales must be 1x, 2x or 4x")
    if rgb4.shape != (h * 4, w * 4, 3):
        raise ValueError("SR output does not match the official native x4 canvas")
    if not np.isfinite(rgb4).all():
        raise ValueError("SR output contains non-finite pixels")
    rgb8 = rgb4 if rgb4.dtype == np.uint8 else np.rint(np.clip(rgb4, 0, 1) * 255).astype(np.uint8)
    alpha4 = cv2.resize(alpha.astype(np.float32) / 255, (w * 4, h * 4),
                        interpolation=cv2.INTER_LINEAR)
    result = np.dstack((rgb8, np.rint(alpha4 * 255).astype(np.uint8)))
    if output_scale != 4:
        result = cv2.resize(result, (w * output_scale, h * output_scale),
                            interpolation=cv2.INTER_LANCZOS4)
    return Image.fromarray(result, "RGBA")


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
    if not isinstance(tile, int) or isinstance(tile, bool) or tile < 0:
        raise ValueError("tile must be a nonnegative integer; 0 disables tiling")
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
    result = Image.new("RGB", (w * 4, h * 4))
    tile = tile or max(h, w)  # official tile=0 means whole-image inference
    device = next(model.parameters()).device
    dtype = next(model.parameters()).dtype
    pad = 10  # official Real-ESRGAN tile_pad default
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
            if tuple(pred.shape) != (1, 3, (y1-y0)*4, (x1-x0)*4) or not torch.isfinite(pred).all():
                raise ValueError("SR model returned invalid native x4 pixels")
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
            result.paste(inset,(x*4,y*4))
            del inp, pred
    return _finish_rgba(np.asarray(result), alpha, output_scale=output_scale)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", action="store_true")
    args = parser.parse_args()
    if not args.prepare:
        parser.error("Only --prepare is supported; generation uses load_model()")
    prepare_weights()
