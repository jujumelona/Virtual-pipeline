"""Validate actual files inside a delivered Live2D artwork ZIP.

Byte-level checks do not certify Cubism import, animation, or visual quality.
"""
from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from struct import unpack
from zipfile import ZipFile

from PIL import Image


def verify_artwork_package(package: Path) -> dict:
    with ZipFile(package, "r") as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Artwork ZIP contains duplicate member paths")
        manifest = json.loads(archive.read("metadata/layer_manifest.json"))
        records = manifest["layers"]
        if not records or len(records) != manifest["drawable_layer_count"]:
            raise ValueError("Artwork ZIP manifest layer count mismatch")
        canvas = (manifest["canvas_width"], manifest["canvas_height"])
        psd_name = ("avatar.psd" if manifest["edition"] == "free"
                    else manifest["asset_kind"] + ".psd")
        # A PSD header alone does not prove that its editable layers exist.
        psd_bytes = archive.read(psd_name)
        header = psd_bytes[:26]
        if len(header) != 26 or header[:4] != b"8BPS" or unpack(">H", header[4:6])[0] != 1:
            raise ValueError("Artwork ZIP does not contain a PSD header")
        channels, height, width, depth, color_mode = unpack(">HIIHH", header[12:26])
        if ((width, height) != canvas or channels < 3 or depth != 8 or color_mode != 3):
            raise ValueError("Artwork ZIP PSD canvas/color mode mismatch")
        from psd_tools import PSDImage
        try:
            psd = PSDImage.open(BytesIO(psd_bytes))
            leaves = [node for node in psd.descendants() if not node.is_group()]
        except Exception as exc:
            raise ValueError("Artwork ZIP PSD cannot be parsed") from exc
        if len(leaves) != len(records):
            raise ValueError("Artwork ZIP PSD drawable layer count mismatch")
        with Image.open(BytesIO(archive.read("preview/composite.png"))) as preview:
            if preview.size != canvas:
                raise ValueError("Artwork ZIP preview canvas mismatch")
        rgba_paths = [r["rgba_png"] for r in records]
        mask_paths = [r["alpha_mask_png"] for r in records]
        if (len(set(rgba_paths)) != len(records) or len(set(mask_paths)) != len(records)
                or set(rgba_paths) != {n for n in names if n.startswith("layers_png/") and n.endswith(".png")}
                or set(mask_paths) != {n for n in names if n.startswith("alpha_masks/") and n.endswith(".png")}):
            raise ValueError("Artwork ZIP manifest paths differ from packaged layers")
        for index, record in enumerate(records):
            # The PSD enumerates bottom-to-top; manifest is top-to-bottom.
            actual = leaves[-1 - index]
            if actual.name != record["semantic_name"]:
                raise ValueError("Artwork ZIP PSD layer semantic name mismatch")
            if (not actual.is_visible() or actual.opacity != 255
                    or actual.blend_mode.name != "NORMAL" or actual.mask is not None):
                raise ValueError("Artwork ZIP PSD layer is not a plain visible raster")
            try:
                psd_pixels = actual.topil(apply_icc=False)
            except Exception as exc:
                raise ValueError("Artwork ZIP PSD layer cannot be decoded") from exc
            if psd_pixels is None:
                raise ValueError("Artwork ZIP PSD layer has no RGBA pixels")
            psd_pixels = psd_pixels.convert("RGBA")
            left, top = actual.left, actual.top
            right, bottom = left + psd_pixels.width, top + psd_pixels.height
            if not (0 <= left < right <= canvas[0] and 0 <= top < bottom <= canvas[1]):
                raise ValueError("Artwork ZIP PSD layer is outside reference canvas")
            local_bbox = psd_pixels.getchannel("A").getbbox()
            if local_bbox is None or [
                    local_bbox[0] + left, local_bbox[1] + top,
                    local_bbox[2] + left, local_bbox[3] + top,
            ] != record["canvas_xyxy_bbox"]:
                raise ValueError("Artwork ZIP PSD layer alpha bounds mismatch")
            rgba_bytes = archive.read(record["rgba_png"])
            mask_bytes = archive.read(record["alpha_mask_png"])
            if sha256(rgba_bytes).hexdigest() != record["rgba_png_sha256"]:
                raise ValueError("Artwork ZIP RGBA SHA256 mismatch: " + record["rgba_png"])
            if sha256(mask_bytes).hexdigest() != record["mask_png_sha256"]:
                raise ValueError("Artwork ZIP mask SHA256 mismatch: " + record["alpha_mask_png"])
            with Image.open(BytesIO(rgba_bytes)) as rgba:
                rgba.load()
                if rgba.mode != "RGBA" or rgba.size != canvas:
                    raise ValueError("Artwork ZIP layer RGBA/canvas mismatch")
                # Full-canvas PNG must match the native PSD raster and offset.
                if psd_pixels.tobytes() != rgba.crop(
                        (left, top, right, bottom)).tobytes():
                    raise ValueError("Artwork ZIP PSD layer RGBA mismatch")
                alpha = rgba.getchannel("A")
                bbox = alpha.getbbox()
                if bbox is None or list(bbox) != record["canvas_xyxy_bbox"]:
                    raise ValueError("Artwork ZIP layer alpha bounds mismatch")
                with Image.open(BytesIO(mask_bytes)) as mask:
                    mask.load()
                    if (mask.mode != "L" or mask.size != canvas
                            or mask.tobytes() != alpha.tobytes()):
                        raise ValueError("Artwork ZIP alpha mask differs from layer")
    return {"status": "PASS", "verified_rgba_mask_pairs": len(records),
            "psd_header_checked": True, "psd_layers_verified": len(records),
            "editor_import_verified": False,
            "visual_quality_verified": False}
