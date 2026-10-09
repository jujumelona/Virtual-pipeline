"""Strict uploaded ZIP -> verified sheet tiles -> native 2D or 3D inputs.

Accepted archive layout: a single optional folder containing exactly the
canonical seven 2D high-resolution sheets + front_master, or 3D two paired
view sheets + face. The verified manifest is defined by sheet_contract.py.
Single root folder OR bare files. No arbitrary extraction / paths / scripts.
AI SR is applied to each 2D tile AFTER clipping to its true-alpha bbox.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path, PurePosixPath
from zipfile import ZipFile, ZIP_STORED
import json
import os

from PIL import Image

from vtuber_pipeline.sheet_contract import (
    FACE, MASTER, SHEETS_2D, VIEWS_3D, sheet_names,
)

MAX_ARCHIVE_BYTES = 600 * 1024 * 1024
MAX_MEMBER_BYTES = 160 * 1024 * 1024
MAX_TOTAL_BYTES = 500 * 1024 * 1024


def _members(archive: ZipFile, mode: str):
    entries = [item for item in archive.infolist() if not item.is_dir()]
    if not entries or len(entries) != len(sheet_names(mode)):
        raise ValueError("Invalid sheet pack: unexpected image count")
    normalized = {}
    totals = 0
    for entry in entries:
        name = entry.filename.replace("\\", "/")
        segments = PurePosixPath(name).parts
        if (name.startswith("/") or len(segments) not in (1,2)
                or any(p in ("", ".", "..") or p.startswith(".") for p in segments)
                or any(part.endswith(":") for part in segments)
                or (entry.external_attr >> 16) & 0o170000 == 0o120000
                or not segments[-1].endswith(".png")):
            raise ValueError("Unsafe / unexpected ZIP entry: " + name)
        if entry.file_size > MAX_MEMBER_BYTES or entry.file_size <= 0:
            raise ValueError("PNG entry size outside limits: " + name)
        totals += entry.file_size
        if totals > MAX_TOTAL_BYTES:
            raise ValueError("Sheet pack exceeds 500 MiB PNG byte budget")
        key = segments[-1]
        if key in normalized:
            raise ValueError("Duplicate PNG filename inside ZIP: " + key)
        normalized[key] = entry
    parents = {str(PurePosixPath(e.filename).parent) for e in entries}
    if len(parents) != 1:
        raise ValueError("All sheet images must share one common folder")
    expected = sheet_names(mode)
    if set(normalized) != expected:
        raise ValueError(
            f"{mode} sheet filenames: missing={sorted(expected-set(normalized))}; "
            f"unexpected={sorted(set(normalized)-expected)}"
        )
    return normalized


def _expected_size(mode: str, filename: str):
    if mode in ("live2d", "inochi2d", "2d"):
        if filename == "front_master.png":
            return MASTER
        return next(s.size for s in SHEETS_2D if s.filename == filename)
    if filename == "face.png":
        return FACE
    return next(s.size for s in VIEWS_3D if s.filename == filename)


def _valid_aspect(actual: tuple[int, int], expected: tuple[int, int]) -> bool:
    """Image AI may choose resolution, but never change semantic grid ratio."""
    w, h = actual
    ew, eh = expected
    return (
        min(w, h) >= 256
        and max(w, h) <= 8192
        and abs(w * eh - h * ew) / (h * ew) <= 0.015
    )


def _tile_box(image_size: tuple[int,int], sheet, row: int, col: int):
    """Use observed pixels, never assume the AI emitted target resolution."""
    width, height = image_size
    # AI generators often produce odd dimensions; deterministic nearest
    # grid boundaries still partition all pixels without gaps or overlaps.
    x0 = round(col * width / sheet.columns)
    x1 = round((col+1) * width / sheet.columns)
    y0 = round(row * height / sheet.rows)
    y1 = round((row+1) * height / sheet.rows)
    return x0,y0,x1,y1


def _upscale_to(image: Image.Image, target: tuple[int,int], upscaler,
                *, neural: bool) -> Image.Image:
    """AI enlarge before any final geometric resampling; never call interpolation AI."""
    if image.size == target:
        return image.copy()
    factor = max(target[0]/image.width, target[1]/image.height)
    if neural and factor > 1:
        # The checkpoint performs a genuine neural 4x prediction. Large source
        # deficits are reported instead of pretending Lanczos invented detail.
        use = 4 if factor > 2 else 2
        output = upscaler(image, use)
    else:
        output = image
    if output.size != target:
        output = output.resize(target, Image.Resampling.LANCZOS)
    return output


def inspect_sheet_archive(archive_path: str, mode: str) -> dict:
    """CPU-only admission gate used in Colab cell ④, before GPU jobs."""
    src = Path(archive_path)
    if not src.is_file() or src.suffix.lower() != ".zip":
        raise ValueError("Provide one .zip sheet pack")
    if src.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("Sheet ZIP exceeds 600 MiB")
    sizes = {}
    with ZipFile(src, "r") as z:
        members = _members(z, mode)
        for name, entry in sorted(members.items()):
            data = z.read(entry)
            try:
                with Image.open(BytesIO(data)) as im:
                    if im.format != "PNG":
                        raise ValueError(f"{name}: only PNG is supported")
                    target = _expected_size(mode, name)
                    if not _valid_aspect(im.size, target):
                        raise ValueError(
                            f"{name}: wrong aspect ratio {im.size}. "
                            f"Expected width:height={target[0]}:{target[1]} "
                            f"(any sufficient pixel dimensions with this ratio). "
                            "Upscaling cannot repair a sideways or distorted grid."
                        )
                    if (mode in ("2d", "live2d", "inochi2d")
                            and name != "front_master.png" and im.mode != "RGBA"):
                        raise ValueError(
                            f"{name}: actual RGBA transparent layers required; "
                            "RGB/color-background images cannot become rig layers by upscaling"
                        )
                    im.load()
                    if name.startswith("sheet_") and mode != "3d":
                        for sheet in SHEETS_2D:
                            if sheet.filename != name:
                                continue
                            used = {(t.row,t.col) for t in sheet.tiles}
                            for row in range(sheet.rows):
                                for col in range(sheet.columns):
                                    box = _tile_box(im.size,sheet,row,col)
                                    alpha = im.crop(box).getchannel("A")
                                    if ((row,col) in used
                                            and alpha.histogram()[255] >=
                                            int(alpha.width*alpha.height*0.97)):
                                        raise ValueError(
                                            f"{name}: grid ({row+1},{col+1}) is "
                                            "nearly opaque wall-to-wall. "
                                            "Remove the fake/background layer; "
                                            "upscaling does not create transparency."
                                        )
                                    if (row,col) in used and not alpha.getbbox():
                                        raise ValueError(
                                            f"{name}: part at grid ({row+1},{col+1}) is empty"
                                        )
                                    if (row,col) not in used and alpha.getbbox():
                                        raise ValueError(
                                            f"{name}: reserved grid ({row+1},{col+1}) must be alpha=0"
                                        )
                    sizes[name] = list(im.size)
            except (OSError, Image.DecompressionBombError) as exc:
                raise ValueError(f"{name}: damaged PNG file") from exc
    return {"mode":mode, "filenames": sorted(sizes), "sizes": sizes,
            "verified": True}


def store_uploaded_zip(uploaded: dict[str, bytes], folder: str, mode: str) -> str:
    """Only one user ZIP is accepted. Preserve exact basename for audit."""
    if not isinstance(uploaded,dict) or len(uploaded) != 1:
        raise ValueError("Upload exactly one sheet ZIP file")
    name, data = next(iter(uploaded.items()))
    if name not in ("character_2d_sheet_pack.zip",
                    "character_3d_sheet_pack.zip"):
        raise ValueError(
            "ZIP filename must be character_2d_sheet_pack.zip or "
            "character_3d_sheet_pack.zip"
        )
    required = ("character_3d_sheet_pack.zip" if mode == "3d"
                else "character_2d_sheet_pack.zip")
    if name != required:
        raise ValueError(f"{mode} requires ZIP filename {required}")
    if not isinstance(data, bytes) or not data or len(data) > MAX_ARCHIVE_BYTES:
        raise ValueError("Invalid / oversize ZIP upload")
    out = Path(folder)
    out.mkdir(parents=True,exist_ok=True)
    path = out / name
    path.write_bytes(data)
    try:
        receipt = inspect_sheet_archive(str(path),mode)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    (out / "sheet_input_verified.json").write_text(
        json.dumps(receipt, indent=2), encoding="utf-8"
    )
    return str(path)


def _read(z, members, name):
    with Image.open(BytesIO(z.read(members[name]))) as im:
        im.load()
        return im.copy()


def convert_2d_sheet_pack(pack: str, folder: str, *,
                          output_scale: int = 2,
                          neural: bool = True,
                          upscaler=None) -> tuple[str,str]:
    """Creates production full-canvas layers with stable master coordinates.

    AI is required by default; testing can inject a deterministic fake
    upscaler. An absent model / OOM propagates as failure (no hidden fallback).
    """
    if output_scale not in (1,2):
        raise ValueError("2D sheet scale must be 1 or 2")
    inspect_sheet_archive(pack,"live2d")
    from vtuber_pipeline.two_d.preparation import MAX_LAYERS
    if len([t for sheet in SHEETS_2D for t in sheet.tiles]) > MAX_LAYERS:
        raise ValueError("Supplied sprite part count exceeds writer contract")
    output = Path(folder)
    output.mkdir(parents=True,exist_ok=True)
    if neural and upscaler is None:
        from tools.sheet_super_resolution import load_model, upscale_rgba
        model = load_model()
        upscaler = lambda crop, factor: upscale_rgba(
            crop, model, output_scale=factor
        )
    if upscaler is None:
        upscaler = lambda crop, factor: crop.resize(
            (crop.width*factor,crop.height*factor), Image.Resampling.LANCZOS
        )
    size = (MASTER[0]*output_scale,MASTER[1]*output_scale)
    result_zip = output / "registered_parts.internal.zip"
    master_path = output / "front_master.png"
    with ZipFile(pack) as z:
        members = _members(z,"live2d")
        master = _read(z, members, "front_master.png").convert("RGBA")
        master = _upscale_to(master,size,upscaler,neural=neural)
        if master.size != size:
            raise RuntimeError("Upscaler changed master geometry")
        master.save(master_path)
        del master
        tmp = result_zip.with_suffix(".tmp")
        with ZipFile(tmp,"w",compression=ZIP_STORED) as dest:
            for sheet in SHEETS_2D:
                source = _read(z,members,sheet.filename)
                for tile in sheet.tiles:
                    cell = source.crop(
                        _tile_box(source.size,sheet,tile.row,tile.col)
                    ).convert("RGBA")
                    bbox = cell.getchannel("A").getbbox()
                    if bbox is None:
                        raise ValueError(f"{tile.name}: missing opaque artwork")
                    part = cell.crop(bbox)
                    roi_w = tile.roi[2] - tile.roi[0]
                    roi_h = tile.roi[3] - tile.roi[1]
                    # Preserve source cell offsets and master-space ROI rather
                    # than independently centering each generated component.
                    rx = roi_w * output_scale / cell.width
                    ry = roi_h * output_scale / cell.height
                    if abs(rx/ry - 1) > 0.02:
                        raise ValueError(f"{tile.name}: distorted source cell")
                    x = tile.roi[0]*output_scale + round(bbox[0]*rx)
                    y = tile.roi[1]*output_scale + round(bbox[1]*ry)
                    max_x = (tile.roi[2]*output_scale)
                    max_y = (tile.roi[3]*output_scale)
                    desired = (
                        min(max_x-x, max(1,round(part.width*rx))),
                        min(max_y-y, max(1,round(part.height*ry)))
                    )
                    upscale = _upscale_to(part,desired,upscaler,neural=neural)
                    if (x < 0 or y < 0 or x + upscale.width > size[0]
                            or y + upscale.height > size[1]):
                        raise ValueError(f"{tile.name}: part outside final canvas")
                    layer = Image.new("RGBA",size,(0,0,0,0))
                    layer.paste(upscale,(x,y))
                    payload = BytesIO()
                    layer.save(payload,"PNG")
                    dest.writestr(tile.name+".png",payload.getvalue())
                    print("[sheet-part] "+tile.name+f": bbox={bbox} "
                          f"master_xy=({x},{y}) scale={output_scale}x "
                          f"source_cell={cell.size} target_bbox={desired} "
                          f"neural_model={'yes' if neural else 'no'}",
                          flush=True)
                    del part,cell,upscale,layer,payload
                del source
        tmp.replace(result_zip)
    manifest = output / "sheet_conversion.json"
    manifest.write_text(json.dumps({
        "scale":output_scale,"neural_sr":neural,"source":str(pack),
        "master_size":list(size),
        "part_count":sum(len(sheet.tiles) for sheet in SHEETS_2D),
        "base_character_only":True,
        "outfit_meshes_embedded":False,
        "registration":"normalized ROI",
    },indent=2),encoding="utf-8")
    return str(master_path),str(result_zip)


def convert_3d_sheet_pack(pack: str, folder: str,
                          *, upscaler=None, neural: bool=False) -> dict[str,str]:
    """Crop actual view cells and normalize their size, with optional AI SR."""
    inspect_sheet_archive(pack,"3d")
    output = Path(folder)
    output.mkdir(parents=True,exist_ok=True)
    results = {}
    with ZipFile(pack) as z:
        members = _members(z,"3d")
        for sheet_spec in VIEWS_3D:
            sheet = _read(z,members,sheet_spec.filename)
            for tile in sheet_spec.tiles:
                destination = output / (tile.name+".png")
                view = sheet.crop(_tile_box(sheet.size,sheet_spec,tile.row,tile.col))
                view = _upscale_to(view.convert("RGBA"), MASTER, upscaler,
                                   neural=neural)
                view.save(destination)
                results[tile.name] = str(destination)
            del sheet
        face = _read(z,members,"face.png")
        face.save(output/"face.png")
        results["face"] = str(output/"face.png")
    (output/"sheet_conversion.json").write_text(json.dumps({
        "mode":"3d","source":pack,"views":results,
        "registration":"aspect-checked orthographic 2x1 paired sheets",
        "default_outfit":"integrated_with_avatar_geometry",
        "separate_garment_mesh":False,
        "automatic_outfit_swapping":False,
        "notes":"Source views must depict one consistently dressed character",
    },ensure_ascii=False,indent=2),encoding="utf-8")
    return results
