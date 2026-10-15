"""Accept standalone image-AI PNG artworks and multiview references.

If independently painted part_art/ inputs exist, validate authored expression
reference drawings too; otherwise preserve the legacy See-through-only path.
PSD assembly and rigging are downstream responsibilities.
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


def validate_authored_mouth_reference_states(source: Path, canvas: tuple[int, int]) -> dict:
    """Validate actual close/open illustrations, not just two filenames.

    The check proves distinct pixel content and consistent registration only;
    it cannot prove the generator visually consulted the Live2D PSD template.
    """
    from PIL import ImageChops
    paths = ("expression_refs/mouth_closed.png",
             "expression_refs/mouth_open.png")
    states = []
    with ZipFile(source) as z:
        for name in paths:
            if name not in z.namelist() or z.namelist().count(name) != 1:
                raise ValueError("AUTHORED_BODY_MOUTH_EXPRESSION_REFERENCE_MISSING: " + name)
            info = z.getinfo(name)
            if not 0 < info.file_size <= 48_000_000:
                raise ValueError("AUTHORED_BODY_MOUTH_EXPRESSION_REFERENCE_SIZE: " + name)
            raw = z.read(name)
            with Image.open(io.BytesIO(raw)) as im:
                im.load()
                if im.format != "PNG" or im.size != canvas or im.mode not in ("RGB", "RGBA"):
                    raise ValueError("AUTHORED_BODY_MOUTH_EXPRESSION_REFERENCE_INVALID: " + name)
                states.append(im.convert("RGBA"))
    def flattened(im):
        bg = Image.new("RGBA", canvas, (255, 255, 255, 255))
        bg.alpha_composite(im)
        return bg.convert("RGB")
    difference = ImageChops.difference(flattened(states[0]), flattened(states[1]))
    region = difference.getbbox()
    if region is None:
        raise ValueError("AUTHORED_BODY_MOUTH_EXPRESSION_REFERENCES_IDENTICAL")
    return {"status": "CLOSED_OPEN_PNG_CONTENT_DISTINCT",
            "files": list(paths),
            "difference_bbox_xyxy": list(region),
            "actual_anime_style_verified": False,
            "actual_template_consultation_verified": False}


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
    expressions = (validate_authored_mouth_reference_states(source, canvas)
                   if authored_parts_present and asset == "body" else None)
    return {
        "schema": "vtuber/image-ai-source-only-v2",
        "asset": asset, "master": str(target),
        "canvas": canvas, "views": views,
        "parts": {"status": "SOURCE_ONLY_NEEDS_SEETHROUGH", "count": 0,
                  "visual_quality_verified": False},
        "authored_parts_present": authored_parts_present,
        "mouth_expression_reference_qa": expressions,
        "source_only": True,
        "multiview_reference_applied_to_native_keyforms": False,
        "state": "SOURCE_ART_CHECKED_NOT_RIGGED",
    }
