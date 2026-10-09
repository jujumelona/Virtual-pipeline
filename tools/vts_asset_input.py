"""Register an isolated PRO asset without hallucinating a character body/head."""
from pathlib import Path
import json

from PIL import Image, ImageChops


def prepare_detached_asset(master: Path, work: Path, *, asset_kind: str,
                           qwen: bool, layer_count: int, pass_budget: int,
                           third_party: Path, python: str | None = None):
    from psd_tools import PSDImage
    from tools.vts_psd_layer import create_import_layer

    with Image.open(master) as source:
        source.load()
        rgba = source.convert("RGBA")
    work.mkdir(parents=True, exist_ok=True)
    alpha = rgba.getchannel("A")
    report = {"method": "registered_source_alpha", "qwen_passes_used": 0,
              "inferred_hidden_pixels": False, "canvas": list(rgba.size),
              "mask_visual_accuracy_verified": False,
              "rgb_regenerated": False}
    if alpha.getextrema() == (255, 255):
        if not qwen or pass_budget < 1:
            raise ValueError("PRO opaque detached asset needs Qwen foreground masks; "
                             "enable Qwen with at least one pass, or supply actual "
                             "transparent artwork/an aligned layered PSD")
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
    psd = PSDImage.new("RGB", rgba.size)
    create_import_layer(rgba, psd, name=asset_kind + ".source")
    target = work / "asset_source.psd"
    psd.save(target)
    (work / "asset_preparation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return target, report
