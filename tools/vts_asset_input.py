"""Register an isolated PRO asset without hallucinating a character body/head."""
from pathlib import Path
import json

from PIL import Image, ImageChops, ImageDraw



def _flat_border_foreground_mask(rgba):
    """Extract only a fully enclosed foreground on a near-uniform border.

    This changes alpha only, not source RGB, and never reconstructs hidden
    artwork. Ambiguous backgrounds and border-contacting objects fail closed.
    """
    width, height = rgba.size
    if min(width, height) < 16:
        return None
    rgb = rgba.convert("RGB")
    background_color = rgb.getpixel((0, 0))
    edges = (
        rgb.crop((0, 0, width, 1)),
        rgb.crop((0, height - 1, width, height)),
        rgb.crop((0, 0, 1, height)),
        rgb.crop((width - 1, 0, width, height)),
    )
    for edge in edges:
        difference = ImageChops.difference(
            edge, Image.new("RGB", edge.size, background_color))
        if any(high > 8 for low, high in difference.getextrema()):
            return None
    marker = tuple(0 if channel >= 128 else 255 for channel in background_color)
    flooded = rgb.copy()
    ImageDraw.floodfill(flooded, (0, 0), marker, thresh=8)
    background = ImageChops.difference(rgb, flooded).convert("L").point(
        lambda value: 255 if value else 0)
    covered = background.histogram()[255]
    if not (0.05 * width * height <= covered <= 0.95 * width * height):
        return None
    return ImageChops.invert(background)

def prepare_detached_asset(master: Path, work: Path, *, asset_kind: str,
                           qwen: bool, layer_count: int, pass_budget: int,
                           third_party: Path, python: str | None = None):
    if qwen:
        raise ValueError("SEE_THROUGH_ONLY: Qwen foreground inference disabled")
    from tools.vts_psd_layer import create_import_layer, new_import_psd, save_import_psd

    with Image.open(master) as source:
        source.load()
        rgba = source.convert("RGBA")
    work.mkdir(parents=True, exist_ok=True)
    alpha = rgba.getchannel("A")
    report = {"method": "registered_source_alpha", "qwen_passes_used": 0,
              "inferred_hidden_pixels": False, "canvas": list(rgba.size),
              "mask_visual_accuracy_verified": False,
              "rgb_regenerated": False}
    if alpha.getextrema() == (255, 255) and not qwen:
        mask = _flat_border_foreground_mask(rgba)
        if mask is None:
            raise ValueError(
                "PRO opaque detached asset needs a uniform, unobstructed border, "
                "transparent artwork or an aligned PSD; Qwen is optional "
                "only for PRO hair/accessory")
        rgba.putalpha(mask)
        report.update(
            method="flat_border_floodfill_original_rgb",
            note="Connected near-uniform background removed; inspect edges and "
                 "background leakage. Hidden pixels were not reconstructed.")
    elif alpha.getextrema() == (255, 255):
        if pass_budget < 1:
            raise ValueError("PRO opaque detached asset needs a positive Qwen "
                             "pass budget or transparent artwork")
        # The official Stable-Layers output is background first and then
        # back-to-front objects. Use only object alpha, never generated RGB.
        from tools.vts_qwen_refine import infer
        result = infer(master, work / "foreground", third_party=third_party,
                       python=python, layer_count=layer_count)
        paths = result["layers"]
        if len(paths) < 2:
            raise ValueError("Qwen returned no foreground object mask")
        mask = Image.new("L", rgba.size, 0)
        scale = 640 / max(rgba.size)
        rounded = tuple(max(int(round(dim * scale / 16)) * 16, 16) for dim in rgba.size)
        for path in paths[1:]:
            with Image.open(path) as proposal:
                proposal.load()
                if proposal.mode != "RGBA":
                    raise ValueError("Qwen foreground proposal must be RGBA")
                error = abs(proposal.width / proposal.height - rgba.width / rgba.height) / (rgba.width / rgba.height)
                if error > .08 and proposal.size != rounded:
                    raise ValueError("Qwen foreground mask changed source geometry")
                region = proposal.getchannel("A").resize(rgba.size, Image.Resampling.BILINEAR)
                # Union opacity follows the official Porter-Duff over rule.
                mask = ImageChops.invert(ImageChops.multiply(
                    ImageChops.invert(mask), ImageChops.invert(region)))
        if not mask.getbbox() or mask.getextrema()[0] > 24:
            raise ValueError("Qwen did not distinguish foreground from the opaque background")
        rgba.putalpha(ImageChops.multiply(alpha, mask))
        report.update(method="qwen_foreground_mask_original_rgb", qwen_passes_used=1,
                      note="Mask shape is inferred at 640px; review edges, backdrop "
                           "leakage and completeness. Hidden surfaces are not restored.")
    if not rgba.getchannel("A").getbbox():
        raise ValueError("Detached asset has no drawable pixels")
    psd = new_import_psd(rgba.size)
    create_import_layer(rgba, psd, name=asset_kind + ".source")
    target = work / "asset_source.psd"
    save_import_psd(psd, target)
    (work / "asset_preparation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return target, report
