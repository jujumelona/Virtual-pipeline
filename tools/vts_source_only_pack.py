"""Accept source-art-only image AI ZIP and prepare See-through inputs.

The image generator supplies only PNG artwork and multiview references.
No segmentation metadata, PSD or layer_order is read from this package.
"""
from __future__ import annotations

import io
from pathlib import Path, PurePosixPath
from zipfile import ZipFile
from PIL import Image


def is_source_only_zip(source: Path) -> bool:
    with ZipFile(source) as z:
        names = [i.filename for i in z.infolist() if not i.is_dir()]
    return (not any(n == "layer_order.txt" or n.endswith("/layer_order.txt")
                    or n == "manifest.json" or n.endswith("/manifest.json") for n in names)
            and any(n.endswith("outputs/master.png") or
                    n in ("master.png", "master_original.png") for n in names))


def prepare_source_only_2d(source: Path, output: Path, *, asset: str) -> dict:
    from tools.vts_multiview_runtime import VIEW_SETS, _check_view_members
    if asset not in VIEW_SETS:
        raise ValueError("SOURCE_ONLY_UNKNOWN_ASSET")
    source = Path(source).resolve(strict=True)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    with ZipFile(source) as archive:
        infos = [i for i in archive.infolist() if not i.is_dir()]
        if not infos or len(infos) > 200 or sum(x.file_size for x in infos) > 850_000_000:
            raise ValueError("SOURCE_ONLY_ARCHIVE_LIMIT")
        names = [i.filename for i in infos]
        if len(names) != len(set(names)) or archive.testzip():
            raise ValueError("SOURCE_ONLY_CORRUPT_OR_DUPLICATE")
        for info in infos:
            name = info.filename
            p = PurePosixPath(name)
            if (p.is_absolute() or ".." in p.parts or "\\" in name
                    or (info.external_attr >> 16) & 0o170000 == 0o120000):
                raise ValueError("SOURCE_ONLY_UNSAFE_ZIP_MEMBER: " + name)
        masters = [n for n in names
                   if n in ("outputs/master.png", "master.png", "master_original.png")
                   or n.count("/") == 2 and n.endswith("/outputs/master.png")]
        if len(masters) != 1:
            raise ValueError("SOURCE_ONLY_EXPECTED_ONE_MASTER_PNG")
        if any(n.startswith("isolated_parts/") or "/isolated_parts/" in n
               or n.endswith(".psd") for n in names):
            raise ValueError("SOURCE_ONLY_MUST_NOT_SUPPLY_SPLIT_PARTS")
        data = archive.read(masters[0])
    if len(data) > 48_000_000:
        raise ValueError("SOURCE_ONLY_MASTER_TOO_LARGE")
    with Image.open(io.BytesIO(data)) as image:
        if image.format != "PNG" or min(image.size) < 256 or max(image.size) > 8192:
            raise ValueError("SOURCE_ONLY_MASTER_INVALID")
        image.verify()
    with Image.open(io.BytesIO(data)) as image:
        canvas = image.size
    target = output / "source_master.png"
    target.write_bytes(data)
    views = _check_view_members(source, asset=asset,
                                output=output / "reference_views", required=True)
    from tools.vts_authored_part_art import has_authored_parts
    authored_parts_present = has_authored_parts(source)
    return {
        "schema": "vtuber/image-ai-source-only-v2",
        "asset": asset, "master": str(target),
        "canvas": canvas, "views": views,
        "parts": {"status": "SOURCE_ONLY_NEEDS_SEETHROUGH", "count": 0,
                  "visual_quality_verified": False},
        "authored_parts_present": authored_parts_present,
        "source_only": True,
        "multiview_reference_applied_to_native_keyforms": False,
        "state": "SOURCE_ART_CHECKED_NOT_RIGGED",
    }
