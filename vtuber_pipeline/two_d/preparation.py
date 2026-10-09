"""2D character illustration preparation path (not a Live2D model exporter).

All images are supplied by the user. Converts genuine RGBA part layers to
an OpenRaster editing project, preserving layer pixels without inventing
occluded artwork. Neither .moc3 nor a VTube Studio model is synthesized.
"""
from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path, PurePosixPath
import re
import zipfile
from xml.etree import ElementTree as ET

MAX_LAYERS = 128
MAX_LAYER_BYTES = 128 * 1024 * 1024
MAX_TOTAL_BYTES = 2 * 1024 * 1024 * 1024
MAX_DIMENSION = 8192
USAGE = {"personalNonProfit", "personalProfit", "corporation"}
SUGGESTED_PARTS = (
    "hair_back", "body", "face", "eye_left_white", "eye_left_iris",
    "eye_left_lid", "eye_right_white", "eye_right_iris",
    "eye_right_lid", "brow_left", "brow_right",
    "mouth_closed", "mouth_open", "hair_front"
)


def _load_image(data: bytes, description: str):
    from PIL import Image
    try:
        with Image.open(BytesIO(data)) as image:
            if getattr(image, "is_animated", False):
                raise ValueError(f"{description}: animation is not a supported source")
            image.load()
            width, height = image.size
            if not (256 <= width <= MAX_DIMENSION and 256 <= height <= MAX_DIMENSION):
                raise ValueError(
                    f"{description}: each dimension must be 256..{MAX_DIMENSION}")
            if width * height > 32_000_000:
                raise ValueError(f"{description}: too many pixels")
            return image.convert("RGBA")
    except (OSError, Image.DecompressionBombError) as exc:
        raise ValueError(f"{description}: invalid image: {exc}") from exc


def _read_layers(archive: str, canvas: tuple[int, int], *, max_layers: int = MAX_LAYERS):
    from PIL import Image
    layers = []
    total = 0
    with zipfile.ZipFile(archive) as bundle:
        entries = [x for x in bundle.infolist() if not x.is_dir()]
        if not entries or len(entries) > max_layers:
            raise ValueError(f"layers ZIP must contain 1..{max_layers} PNG files")
        used_names = set()
        for entry in sorted(entries, key=lambda x: x.filename.casefold()):
            name = entry.filename.replace("\\", "/")
            path = PurePosixPath(name)
            if (
                name.startswith("/") or ".." in path.parts or
                (entry.external_attr >> 16) & 0o170000 == 0o120000 or
                path.suffix.lower() != ".png" or
                any(part.startswith(".") for part in path.parts)
            ):
                raise ValueError(f"invalid layer ZIP member: {name}")
            if entry.file_size > MAX_LAYER_BYTES:
                raise ValueError(f"layer exceeds {MAX_LAYER_BYTES} bytes: {name}")
            total += entry.file_size
            if total > MAX_TOTAL_BYTES:
                raise ValueError("uncompressed layer ZIP exceeds size limit")
            plain = path.stem
            normalized = plain.casefold()
            if normalized in used_names:
                raise ValueError(f"duplicate layer name: {plain}")
            used_names.add(normalized)
            with bundle.open(entry) as file:
                data = file.read(MAX_LAYER_BYTES + 1)
            if len(data) > MAX_LAYER_BYTES:
                raise ValueError(f"layer file too large: {name}")
            # PNGs should retain a real transparent channel.
            with Image.open(BytesIO(data)) as original:
                if original.format != "PNG" or "A" not in original.getbands():
                    raise ValueError(f"layer must be a transparent RGBA PNG: {name}")
            image = _load_image(data, name)
            if image.size != canvas:
                raise ValueError(
                    f"{name}: layer canvas {image.size} != source {canvas}")
            layers.append((plain, image))
    return layers


def prepare_2d_artwork(
    image_path: str, output_dir: str, *,
    layers_zip: str | None = None,
    commercial_usage: str = "corporation",
    target: str = "live2d",
) -> dict:
    """Package user-supplied RGBA art for an explicitly named 2D rig system.

    No rig is generated; neither .inp nor .moc3 is ever synthesized here.
    """
    from PIL import Image
    if target not in {"inochi2d", "live2d"}:
        raise ValueError(f"unsupported 2D target: {target!r}")
    if commercial_usage not in USAGE:
        raise ValueError(f"unsupported commercial usage: {commercial_usage}")
    source = Path(image_path)
    if not source.is_file():
        raise FileNotFoundError(f"2D source image not found: {source}")
    if source.stat().st_size > MAX_LAYER_BYTES:
        raise ValueError("source artwork exceeds size limit")
    base = _load_image(source.read_bytes(), "source image")
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    if layers_zip:
        if not Path(layers_zip).is_file():
            raise FileNotFoundError(f"layer ZIP missing: {layers_zip}")
        layers = _read_layers(layers_zip, base.size)
    else:
        layers = [("flattened_reference_not_rigged", base)]

    merged = Image.new("RGBA", base.size, (0, 0, 0, 0))
    for _, layer in reversed(layers):
        merged = Image.alpha_composite(merged, layer)

    image_root = ET.Element("image", {
        "version": "0.0.3", "w": str(base.width), "h": str(base.height),
        "name": "External VTuber illustration layers",
    })
    stack = ET.SubElement(image_root, "stack")
    for i, (name, _) in enumerate(layers):
        ET.SubElement(stack, "layer", {
            "name": name, "src": f"data/layer_{i:03d}.png",
            "opacity": "1.0", "visibility": "visible",
            "composite-op": "svg:src-over", "x": "0", "y": "0",
        })
    def png_bytes(image):
        payload = BytesIO()
        image.save(payload, "PNG")
        return payload.getvalue()

    package = output / f"{target}_artwork_prep.zip"
    ora_bytes = BytesIO()
    with zipfile.ZipFile(ora_bytes, "w") as ora:
        ora.writestr("mimetype", "image/openraster", compress_type=zipfile.ZIP_STORED)
        ora.writestr("stack.xml", ET.tostring(image_root, encoding="utf-8"),
                     compress_type=zipfile.ZIP_DEFLATED)
        ora.writestr("mergedimage.png", png_bytes(merged), compress_type=zipfile.ZIP_DEFLATED)
        preview = merged.copy()
        preview.thumbnail((256, 256), Image.Resampling.LANCZOS)
        ora.writestr("Thumbnails/thumbnail.png", png_bytes(preview),
                     compress_type=zipfile.ZIP_DEFLATED)
        for i, (_, layer) in enumerate(layers):
            ora.writestr(f"data/layer_{i:03d}.png", png_bytes(layer),
                         compress_type=zipfile.ZIP_DEFLATED)

    present = {re.sub(r"[^a-z0-9]+", "_", name.casefold()).strip("_")
               for name, _ in layers}
    missing = [name for name in SUGGESTED_PARTS if name not in present]
    status = "needs_layering" if not layers_zip else "prepared"
    inochi2d = target == "inochi2d"
    notes = [
        "This package contains user-provided artwork only; automatic part segmentation is not claimed.",
        "Open artwork.ora in Krita and fill/paint the occluded layers, then export layered PSD.",
    ]
    if inochi2d:
        notes += [
            "Import PSD in the open-source Inochi Creator, rig deformations, "
            "eye/mouth parameters and physics, and export a native .inp puppet.",
            "Load the resulting .inp in Inochi Session for broadcast.",
            "An Inochi2D puppet is not compatible with VTube Studio's Live2D .moc3 runtime.",
        ]
        instructions = (
            "Inochi2D source artwork preparation. NOT a rigged .inp puppet.\n"
            "1. Open artwork.ora in open-source Krita and finish part separation.\n"
            "2. Export layered PSD; import it into open-source Inochi Creator.\n"
            "3. Rig meshes, eyes, mouth, head-angle parameters, and physics.\n"
            "4. Export .inp in Inochi Creator and test with Inochi Session.\n"
            "No .inp or rigging has been created by this pipeline.\n"
        )
    else:
        notes += [
            "Import PSD into Live2D Cubism Editor; rig deformation meshes, "
            "angles, blinking, lipsync and physics.",
            "Export MOC3/model3.json/textures/physics from Cubism Editor for VTube Studio.",
            "Cubism Editor is not open-source. There is no verified permissively "
            "licensed .moc3 encoder integrated in this pipeline.",
        ]
        instructions = (
            "Live2D source artwork preparation. NOT a rigged .moc3 model.\n"
            "1. Open artwork.ora in open-source Krita and finish part separation.\n"
            "2. Export layered PSD and import into Live2D Cubism Editor.\n"
            "3. Rig deformation meshes, eye/mouth/head parameters and physics.\n"
            "4. Export .moc3, .model3.json, textures, physics in Cubism Editor.\n"
            "5. Test the model folder in VTube Studio.\n"
            "No .moc3 or rigging has been created by this pipeline.\n"
        )
    manifest = {
        "format": f"{target}-artwork-preparation-v1",
        "mode": target,
        "status": status,
        "target": (
            "Inochi Creator rigging and Inochi Session VTubing"
            if inochi2d else "Live2D Cubism rigging and VTube Studio"
        ),
        "expected_completed_extension": ".inp" if inochi2d else ".moc3",
        "rig_generated": False,
        "is_inochi2d_model": False,
        "is_live2d_model": False,
        "inochi_session_ready": False,
        "vtube_studio_ready": False,
        "can_export_moc3": False,
        "commercial_usage": commercial_usage,
        "width": base.width, "height": base.height,
        "layer_names_top_to_bottom": [name for name, _ in layers],
        "suggested_parts_not_detected": missing,
        "notes": notes,
    }
    with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr("artwork.ora", ora_bytes.getvalue())
        bundle.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        bundle.writestr("README_NEXT_STEPS.txt", instructions)
        bundle.writestr("original_reference.png", png_bytes(base))
        for i, (name, layer) in enumerate(layers):
            bundle.writestr(f"layers/{i:03d}_{re.sub(r'[^a-zA-Z0-9_-]+', '_', name)}.png",
                            png_bytes(layer))
    return {"status": status, "package_path": str(package), "manifest": manifest}


def prepare_live2d_artwork(
    image_path: str, output_dir: str, *,
    layers_zip: str | None = None,
    commercial_usage: str = "corporation",
) -> dict:
    """Live2D-targeted layered artwork only, not a Cubism runtime export."""
    return prepare_2d_artwork(
        image_path, output_dir,
        layers_zip=layers_zip, commercial_usage=commercial_usage,
        target="live2d",
    )


def prepare_inochi2d_artwork(
    image_path: str, output_dir: str, *,
    layers_zip: str | None = None,
    commercial_usage: str = "corporation",
) -> dict:
    """Inochi2D-targeted layered artwork only, not a native .inp puppet."""
    return prepare_2d_artwork(
        image_path, output_dir,
        layers_zip=layers_zip, commercial_usage=commercial_usage,
        target="inochi2d",
    )
