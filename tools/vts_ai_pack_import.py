"""Validated explicit AI-authored Live2D sprite ZIP -> import PSD.

No See-through/SAM detection, silhouette guessing, or AI judgement here.
Every part must carry a real PNG, draw order, and registration coordinates.
Visual correctness is deliberately NOT certified by this importer.
"""
from __future__ import annotations

from io import BytesIO
import hashlib
import json
from pathlib import Path
import re
from zipfile import ZipFile, BadZipFile

from PIL import Image

from tools.vts_psd_layer import validate_srgb_profile

_PART_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*(?:\.[A-Za-z][A-Za-z0-9_-]*)*$")


def _valid_part_id(value: str) -> bool:
    return len(value) <= 80 and _PART_ID.fullmatch(value) is not None
_MAX_FILES = 500
_MAX_UNCOMPRESSED_BYTES = 650 * 1024 * 1024
_MAX_MANIFEST_BYTES = 2 * 1024 * 1024
_MAX_IMAGE_PIXELS = 32_000_000


def _decode_png(archive: ZipFile, name: str, *, is_part: bool = False,
                expected_sha256: str | None = None) -> Image.Image:
    try:
        raw = archive.read(name)
        if expected_sha256 is not None:
            if (not isinstance(expected_sha256, str) or
                    re.fullmatch(r"[a-fA-F0-9]{64}", expected_sha256) is None):
                raise ValueError(f"AI_PACK_SHA256_INVALID: {name}")
            if hashlib.sha256(raw).hexdigest() != expected_sha256.lower():
                raise ValueError(f"AI_PACK_SHA256_MISMATCH: {name}")
        with Image.open(BytesIO(raw)) as image:
            if image.format != "PNG":
                raise ValueError(f"AI_PACK_NOT_PNG: {name}")
            if image.mode not in (("RGBA",) if is_part else ("RGB", "RGBA")):
                raise ValueError(f"AI_PACK_RGB8_REQUIRED: {name}: got {image.mode}")
            if image.width < 1 or image.height < 1 or image.width * image.height > _MAX_IMAGE_PIXELS:
                raise ValueError(f"AI_PACK_IMAGE_SIZE_INVALID: {name}")
            validate_srgb_profile(image.info.get("icc_profile"))
            image.load()
            return image.copy()
    except (OSError, BadZipFile) as exc:
        raise ValueError(f"AI_PACK_IMAGE_DECODE_FAILED: {name}") from exc


def _inspect_image_only_pack(archive: ZipFile, names: list[str], source: Path,
                             edition: str) -> dict:
    """Read only artwork PNG files and a plain back-to-front filename list.

    No metadata, spatial guesswork, AI self-evaluation, or Cubism operations
    are required from the artwork-generation model.
    """
    order_files = [name for name in names
                   if name == "layer_order.txt"
                   or (name.endswith("/layer_order.txt") and name.count("/") == 1)]
    if len(order_files) != 1:
        raise ValueError("AI_PACK_LAYER_ORDER_MISSING_OR_AMBIGUOUS")
    order_name = order_files[0]
    prefix = order_name[:-len("layer_order.txt")]
    # Both names denote the actual authored master; no need to re-generate.
    master_options = [prefix + item for item in (
        "outputs/master.png", "master_original.png", "master.png")
        if prefix + item in names]
    if not master_options:
        raise ValueError("AI_PACK_MASTER_MISSING: expected outputs/master.png, "
                         "master_original.png, or master.png")
    if len(master_options) > 1:
        fingerprints = {
            hashlib.sha256(archive.read(item)).digest()
            for item in master_options
        }
        if len(fingerprints) != 1:
            raise ValueError("AI_PACK_MASTER_AMBIGUOUS: conflicting master images")
    master_file = master_options[0]
    master = _decode_png(archive, master_file)
    if master.width < 256 or master.height < 256:
        raise ValueError("AI_PACK_MASTER_TOO_SMALL")
    try:
        raw_order = archive.read(order_name).decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("AI_PACK_LAYER_ORDER_NOT_UTF8") from exc
    listed = [line.strip() for line in raw_order.splitlines()
              if line.strip() and not line.lstrip().startswith("#")]
    actual = {name[len(prefix):] for name in names
              if name.startswith(prefix + "isolated_parts/") and name.endswith(".png")}
    # Do not infer draw order from ZIP enumeration or silently drop extra parts:
    # a missing sprite is a content defect, whereas an unlisted sprite could
    # have a different front/back position than any automatically chosen one.
    for filename in listed:
        if not filename.startswith("isolated_parts/") or not filename.endswith(".png"):
            raise ValueError(
                f"AI_PACK_LAYER_ORDER_INVALID_PATH: {filename!r}; "
                "expected isolated_parts/<part_id>.png"
            )
    if edition == "free" and len(listed) > 100:
        raise ValueError("AI_PACK_FREE_ARTMESH_LIMIT")
    seen, duplicates = set(), set()
    for filename in listed:
        if filename in seen:
            duplicates.add(filename)
        seen.add(filename)
    missing = sorted(seen - actual)
    unlisted = sorted(actual - seen)
    min_parts = 1 if edition == "pro" else 2
    if not min_parts <= len(listed) <= _MAX_FILES or duplicates or missing or unlisted:
        def _sample(paths: list[str]) -> str:
            preview = repr(paths[:12])
            return preview + (f" (+{len(paths) - 12} more)" if len(paths) > 12 else "")

        details = [f"listed={len(listed)} actual_pngs={len(actual)}"]
        if not min_parts <= len(listed) <= _MAX_FILES:
            details.append(f"layer_count_out_of_range={min_parts}..{_MAX_FILES}")
        if duplicates:
            details.append("duplicate_entries=" + _sample(sorted(duplicates)))
        if missing:
            details.append("listed_but_missing_png=" + _sample(missing))
        if unlisted:
            details.append("png_not_in_layer_order=" + _sample(unlisted))
        raise ValueError("AI_PACK_LAYER_ORDER_NOT_MATCHING_SPRITES: " + "; ".join(details))
    parts = []
    for z, filename in enumerate(listed):
        if not filename.startswith("isolated_parts/") or not filename.endswith(".png"):
            raise ValueError("AI_PACK_LAYER_ORDER_INVALID_PATH")
        part_id = filename[len("isolated_parts/"):-4]
        if not _valid_part_id(part_id) or filename != f"isolated_parts/{part_id}.png":
            raise ValueError("AI_PACK_PART_ID_INVALID")
        image = _decode_png(archive, prefix + filename, is_part=True)
        if image.size != master.size:
            raise ValueError("AI_PACK_CANVAS_MISMATCH: " + part_id)
        alpha = image.getchannel("A")
        if alpha.getbbox() is None:
            raise ValueError("AI_PACK_EMPTY_ALPHA: " + part_id)
        if alpha.getextrema()[0] == 255:
            raise ValueError("AI_PACK_TRANSPARENCY_MISSING: " + part_id)
        parts.append({"id": part_id, "filename": filename, "z": z,
                      "left": 0, "top": 0, "image": image,
                      "method": "supplied_independent_artwork"})
    return {
        "master": master, "parts": parts, "canvas": master.size,
        "manifest": {"schema": "live2d/simple-image-artwork-zip-v1",
                     "scope": "unspecified", "part_count": len(parts)},
        "source": source, "archive_prefix": prefix,
        "visual_quality_verified": False,
    }


def inspect_large_ai_pack(source: Path, *, edition: str = "free") -> dict:
    """Inspect actual bytes. Never trust creator-provided PASS or visual claims."""
    source = Path(source).expanduser().resolve(strict=True)
    if source.suffix.lower() != ".zip":
        raise ValueError("AI_PACK_ZIP_REQUIRED")
    if edition not in ("free", "pro"):
        raise ValueError("AI_PACK_INVALID_EDITION")
    with ZipFile(source) as archive:
        members = [item for item in archive.infolist() if not item.is_dir()]
        names = [item.filename for item in members]
        if (len(members) > _MAX_FILES or len(names) != len(set(names))
                or sum(x.file_size for x in members) > _MAX_UNCOMPRESSED_BYTES):
            raise ValueError("AI_PACK_ARCHIVE_LIMIT_OR_DUPLICATE")
        # Accept both root contents and one conventional parent folder.
        # Never silently merge multiple nested manifests or ambiguous roots.
        prefix = ""
        # New external image AI ZIP: only independent PNG files and a simple
        # human-readable layer_order.txt. Existing manifest ZIPs remain supported.
        has_manifest = ("manifest.json" in names or any(
            n.endswith("/manifest.json") and n.count("/") == 1 for n in names))
        if not has_manifest:
            return _inspect_image_only_pack(archive, names, source, edition)
        if "manifest.json" not in names:
            candidates = [n[:-len("manifest.json")] for n in names
                          if n.endswith("/manifest.json") and n.count("/") == 1]
            if len(candidates) != 1:
                raise ValueError("AI_PACK_MANIFEST_MISSING_OR_AMBIGUOUS")
            prefix = candidates[0]
        if archive.getinfo(prefix + "manifest.json").file_size > _MAX_MANIFEST_BYTES:
            raise ValueError("AI_PACK_MANIFEST_TOO_LARGE")
        try:
            manifest = json.loads(archive.read(prefix + "manifest.json"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise ValueError("AI_PACK_MANIFEST_INVALID_JSON") from exc
        if not isinstance(manifest, dict) or manifest.get("schema") not in (
            "live2d/large-image-ai-artwork-pack-v1",
            "live2d/large-image-ai-artwork-pack-v2",
        ):
            raise ValueError("AI_PACK_UNKNOWN_SCHEMA")
        if manifest.get("status") in ("TEMPLATE_NOT_GENERATED", "NOT_GENERATED"):
            raise ValueError("AI_PACK_UNGENERATED_TEMPLATE")
        if manifest.get("delivery_tier") in ("TEMPLATE_NOT_GENERATED",):
            raise ValueError("AI_PACK_UNGENERATED_TEMPLATE")
        master_info = manifest.get("master")
        if not isinstance(master_info, dict) or master_info.get("file") != "outputs/master.png":
            raise ValueError("AI_PACK_MASTER_CONTRACT_INVALID")
        if prefix + master_info["file"] not in names:
            raise ValueError("AI_PACK_MASTER_MISSING")
        master = _decode_png(archive, prefix + "outputs/master.png",
                             expected_sha256=master_info.get("sha256"))
        canvas = manifest.get("canvas", {})
        if (not isinstance(canvas, dict) or
                canvas.get("width") != master.width or
                canvas.get("height") != master.height):
            raise ValueError("AI_PACK_CANVAS_MISMATCH")
        if master.width < 256 or master.height < 256:
            raise ValueError("AI_PACK_MASTER_TOO_SMALL")
        rows = manifest.get("parts")
        if not isinstance(rows, list) or len(rows) < (1 if edition == "pro" else 2):
            raise ValueError("AI_PACK_NO_INDEPENDENT_PARTS")
        if edition == "free" and len(rows) > 100:
            raise ValueError("AI_PACK_FREE_ARTMESH_LIMIT")
        seen_ids, seen_orders = set(), set()
        validated = []
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("AI_PACK_PART_ROW_INVALID")
            part_id = row.get("id")
            if not isinstance(part_id, str) or not _valid_part_id(part_id):
                raise ValueError("AI_PACK_PART_ID_INVALID")
            if part_id in seen_ids:
                raise ValueError("AI_PACK_DUPLICATE_PART_ID: " + part_id)
            seen_ids.add(part_id)
            filename = "isolated_parts/" + part_id + ".png"
            if row.get("file") != filename or prefix + filename not in names:
                raise ValueError("AI_PACK_PART_FILE_MISSING: " + part_id)
            method = row.get("creation_method")
            if method not in ("generated", "redrawn", "edited_with_underpaint"):
                # Visual quality still needs inspection; reject known mask-only art.
                raise ValueError("AI_PACK_PART_NOT_AUTHORED: " + part_id)
            z = row.get("draw_order")
            if isinstance(z, bool) or not isinstance(z, int) or z in seen_orders:
                raise ValueError("AI_PACK_DRAW_ORDER_REQUIRED_UNIQUE: " + part_id)
            seen_orders.add(z)
            image = _decode_png(archive, prefix + filename, is_part=True,
                                expected_sha256=row.get("sha256"))
            bounds = image.getchannel("A").getbbox()
            if bounds is None:
                raise ValueError("AI_PACK_EMPTY_ALPHA: " + part_id)
            placement = row.get("placement")
            if placement is None and image.size == master.size:
                left, top = 0, 0
            elif isinstance(placement, dict) and all(isinstance(placement.get(k), int)
                                                      and not isinstance(placement[k], bool)
                                                      for k in ("left", "top", "width", "height")):
                left, top = placement["left"], placement["top"]
                if (placement["width"], placement["height"]) != image.size:
                    raise ValueError("AI_PACK_PART_PLACEMENT_SIZE_MISMATCH: " + part_id)
            else:
                raise ValueError("AI_PACK_PART_PLACEMENT_REQUIRED: " + part_id)
            if (left < 0 or top < 0 or left + image.width > master.width
                    or top + image.height > master.height):
                raise ValueError("AI_PACK_PART_OUT_OF_CANVAS: " + part_id)
            validated.append({"id": part_id, "filename": filename, "z": z,
                              "left": left, "top": top,
                              "image": image, "method": method})
        actual_files = {name[len(prefix):] for name in names if name.startswith(prefix + "isolated_parts/") and name.endswith(".png")}
        if actual_files != {part["filename"] for part in validated}:
            raise ValueError("AI_PACK_UNDECLARED_PART_IMAGES")
        validated.sort(key=lambda x: x["z"])  # back -> front
        return {"master": master, "parts": validated, "canvas": master.size,
                "manifest": manifest, "source": source, "archive_prefix": prefix,
                "visual_quality_verified": False}


def prepare_large_ai_pack(source: Path, destination: Path, *, edition: str = "free") -> dict:
    """Create a real layered RGB8 PSD from explicit, authored part raster PNGs."""
    result = inspect_large_ai_pack(source, edition=edition)
    destination = Path(destination).expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    master = destination / "master.png"
    psd_file = destination / "authored_parts.psd"
    report = destination / "import_report.json"
    result["master"].save(master, format="PNG")
    from psd_tools import PSDImage
    from tools.vts_psd_layer import new_import_psd, create_import_layer, save_import_psd
    psd = new_import_psd(result["canvas"])
    group = psd.create_group(name="AI_AUTHORED_PARTS")
    for item in result["parts"]:  # back to front in native PSD record order
        image = item["image"]
        bbox = image.getchannel("A").getbbox()
        create_import_layer(image.crop(bbox), group, name=item["id"],
                            top=item["top"] + bbox[1], left=item["left"] + bbox[0])
    save_import_psd(psd, psd_file)
    decoded = PSDImage.open(psd_file)
    layers = [x for x in decoded.descendants() if not x.is_group()]
    if len(layers) != len(result["parts"]):
        raise RuntimeError("AI_PACK_PSD_LAYER_COUNT_MISMATCH")
    # Stored native order must agree with manifest back-to-front ordering.
    if [layer.name for layer in layers] != [x["id"] for x in result["parts"]]:
        raise RuntimeError("AI_PACK_PSD_LAYER_ORDER_MISMATCH")
    import_report = {
        "schema": "live2d/large-ai-pack-import-report-v1",
        "source_zip": str(source), "master": str(master),
        "psd": str(psd_file), "part_count": len(layers),
        "canvas": list(result["canvas"]),
        "skipped_see_through": True, "skipped_semantic_sam": True,
        "mask_only_parts_rejected": False,
        "authored_underpaint_visually_verified": False,
        "visual_quality_verified": False,
        "rigging_verified": False,
        "method": "direct_authored_png_to_psd",
        "warning": "File and PSD validity do not prove semantic part quality or rotation.",
    }
    report.write_text(json.dumps(import_report, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"master": master, "psd": psd_file, "report": report, "metadata": import_report}
