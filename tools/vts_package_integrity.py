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
        with archive.open(psd_name) as psd_stream:
            header = psd_stream.read(26)
        if len(header) != 26 or header[:4] != b"8BPS" or unpack(">H", header[4:6])[0] != 1:
            raise ValueError("Artwork ZIP does not contain a PSD header")
        channels, height, width, depth, color_mode = unpack(">HIIHH", header[12:26])
        if ((width, height) != canvas or channels < 3 or depth != 8 or color_mode != 3):
            raise ValueError("Artwork ZIP PSD canvas/color mode mismatch")
        with Image.open(BytesIO(archive.read("preview/composite.png"))) as preview:
            if preview.size != canvas:
                raise ValueError("Artwork ZIP preview canvas mismatch")
        rgba_paths = [r["rgba_png"] for r in records]
        mask_paths = [r["alpha_mask_png"] for r in records]
        if (len(set(rgba_paths)) != len(records) or len(set(mask_paths)) != len(records)
                or set(rgba_paths) != {n for n in names if n.startswith("layers_png/") and n.endswith(".png")}
                or set(mask_paths) != {n for n in names if n.startswith("alpha_masks/") and n.endswith(".png")}):
            raise ValueError("Artwork ZIP manifest paths differ from packaged layers")
        for record in records:
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
            "psd_header_checked": True, "editor_import_verified": False,
            "visual_quality_verified": False}
