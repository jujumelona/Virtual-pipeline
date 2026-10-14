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


def verify_artwork_package(package: Path, *, require_final_handoff: bool = False,
                           require_pro_reference: bool = False) -> dict:
    with ZipFile(package, "r") as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Artwork ZIP contains duplicate member paths")
        manifest = json.loads(archive.read("metadata/layer_manifest.json"))
        records = manifest["layers"]
        if not records or len(records) != manifest["drawable_layer_count"]:
            raise ValueError("Artwork ZIP manifest layer count mismatch")
        semantic_names = [record["semantic_name"] for record in records]
        if (any(not isinstance(name, str) or not name.strip()
                for name in semantic_names)
                or len(set(semantic_names)) != len(semantic_names)):
            raise ValueError("Artwork ZIP duplicate or empty semantic layer names")
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
            preview.load()
            if preview.size != canvas:
                raise ValueError("Artwork ZIP preview canvas mismatch")
            delivered_preview = preview.convert("RGBA").tobytes()
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
        # The preview must be an actual alpha composite of the delivered
        # raster layers in their manifest order, not just a same-sized PNG.
        # Re-read one layer at a time to avoid holding all 100 FREE candidates
        # in Colab RAM simultaneously.
        assembled = Image.new("RGBA", canvas, (0, 0, 0, 0))
        for record in reversed(records):
            with Image.open(BytesIO(archive.read(record["rgba_png"]))) as part:
                assembled.alpha_composite(part.convert("RGBA"))
        if assembled.tobytes() != delivered_preview:
            raise ValueError("Artwork ZIP preview composite RGBA mismatch")

        if require_pro_reference and not require_final_handoff:
            raise ValueError("PRO reference check requires final handoff validation")
        if require_final_handoff:
            required = {
                "preview/input_vs_psd_comparison.png",
                "metadata/input_vs_psd_geometry.json",
                "logs/psd_runtime/runtime.json",
                "README_CUBISM.md",
                "LIVE2D_ARTWORK_GUIDE.md",
                "QUALITY_REVIEW.md",
            }
            missing = required.difference(names)
            if missing:
                raise ValueError("Artwork ZIP final handoff missing: " + ", ".join(sorted(missing)))
            # These are observations, not native Cubism objects. Reject a
            # contradictory manifest even if the PSD bytes themselves open.
            metadata_required = {
                "metadata/manual_rig_reference.json",
                "metadata/segmentation_trace.json",
                "metadata/integrity_report.json",
                "metadata/texture_budget.json",
                "TEXTURE_BUDGET.md",
                "OFFICIAL_EDITOR_SETTINGS.md",
            }
            absent_metadata = metadata_required.difference(names)
            if absent_metadata:
                raise ValueError("Artwork ZIP final handoff missing: "
                                 + ", ".join(sorted(absent_metadata)))
            if any(name.lower().endswith((".moc3", ".cmo3")) for name in names):
                raise ValueError("Artwork ZIP cannot claim native Cubism artifacts")
            trace = json.loads(archive.read("metadata/segmentation_trace.json"))
            attempts = trace.get("attempts")
            accepted = trace.get("accepted_source_names")
            if (not isinstance(attempts, list) or not isinstance(accepted, list)
                    or trace.get("qwen_attempt_count") != len(attempts)
                    or trace.get("qwen_accepted_count") != len(accepted)
                    or [a.get("source_layer") for a in attempts
                        if isinstance(a, dict) and a.get("accepted") is True] != accepted
                    or any(not isinstance(a, dict) or not isinstance(a.get("source_layer"), str)
                           or not isinstance(a.get("accepted"), bool) for a in attempts)):
                raise ValueError("Artwork ZIP segmentation trace is inconsistent")
            integrity = json.loads(archive.read("metadata/integrity_report.json"))
            if (integrity.get("layer_count") != len(records)
                    or integrity.get("qwen_model_attempts") != len(attempts)
                    or integrity.get("qwen_model_splits_accepted") != len(accepted)
                    or any(integrity.get(field) is not False for field in (
                        "moc3_exported", "native_cubism_artmesh_deformer_keyforms_checked",
                        "native_cubism_texture_atlas_checked"))):
                raise ValueError("Artwork ZIP integrity report contradicts PSD/Editor status")
            manual = json.loads(archive.read("metadata/manual_rig_reference.json"))
            suggested = manual.get("suggested_layer_entries")
            if (not isinstance(suggested, list) or len(suggested) != len(records)
                    or any(not isinstance(x, dict) or
                           (x.get("semantic_name"), x.get("family"),
                            x.get("observed_bounds_xyxy"), x.get("observed_center_xy")) !=
                           (r["semantic_name"], r["semantic_family"],
                            r["canvas_xyxy_bbox"], r["visible_alpha_centroid_xy"])
                           for x, r in zip(suggested, records))
                    or any(manual.get(field) is not False for field in (
                        "native_cubism_import", "auto_rigged", "has_native_keyforms",
                        "has_physics_binds"))
                    or any(manual.get("editor_setup_plan", {}).get(field) is not False
                           for field in ("native_cmo3_created", "native_moc3_created",
                                         "native_physics3_json_created",
                                         "native_keyforms_created",
                                         "texture_packing_verified"))):
                raise ValueError("Artwork ZIP manual Editor reference contradicts PSD")
            budget = json.loads(archive.read("metadata/texture_budget.json"))
            if (budget.get("free_limit_applied") is not (manifest["edition"] == "free")
                    or budget.get("editor_packing_verified") is not False
                    or budget.get("artwork_resized") is not False):
                raise ValueError("Artwork ZIP texture budget claims native packing")
            original_images = [n for n in names if n.startswith("input_reference/source_")]
            source_psds = [n for n in names if n.startswith("source_psd/") and n.endswith(".psd")]
            if len(original_images) != 1 or len(source_psds) != 1:
                raise ValueError("Artwork ZIP final source input/PSD missing or ambiguous")
            with Image.open(BytesIO(archive.read(original_images[0]))) as original:
                source_image_size = original.size
                original.verify()
            with Image.open(BytesIO(archive.read("preview/input_vs_psd_comparison.png"))) as panel:
                panel.verify()
            source_psd_bytes = archive.read(source_psds[0])
            if len(source_psd_bytes) < 26 or source_psd_bytes[:4] != b"8BPS":
                raise ValueError("Artwork ZIP original source PSD missing or invalid")
            # The source PSD is not required to match the final output canvas,
            # but its image data and real editable layers must be parseable.
            try:
                source_psd = PSDImage.open(BytesIO(source_psd_bytes))
                if not any(not layer.is_group() for layer in source_psd.descendants()):
                    raise ValueError("original source PSD has no raster layers")
            except Exception as exc:
                raise ValueError(
                    "Artwork ZIP original source PSD cannot be parsed into layers"
                ) from exc
            geometry = json.loads(archive.read("metadata/input_vs_psd_geometry.json"))
            if geometry.get("output_psd_canvas") != list(canvas):
                raise ValueError("Artwork ZIP comparison geometry differs from PSD canvas")
            if ("source_canvas" in geometry and
                    geometry["source_canvas"] != list(source_image_size)):
                raise ValueError("Artwork ZIP source image canvas differs from comparison geometry")
            if require_pro_reference:
                reference_images = [n for n in names if n.startswith("input_reference/body_")]
                required_pro = {"preview/pro_body_asset_overlay.png",
                                "metadata/pro_reference_alignment.json"}
                if len(reference_images) != 1 or not required_pro.issubset(names):
                    raise ValueError("Artwork ZIP PRO body reference/overlay missing")
                with Image.open(BytesIO(archive.read(reference_images[0]))) as reference:
                    reference_size = reference.size
                    reference.verify()
                if reference_size != canvas:
                    raise ValueError("Artwork ZIP PRO body reference image canvas mismatch")
                with Image.open(BytesIO(archive.read("preview/pro_body_asset_overlay.png"))) as overlay:
                    overlay_size = overlay.size
                    overlay.verify()
                scale = min(1.0, 1400 / max(reference_size))
                expected_size = tuple(max(1, round(dimension * scale))
                                      for dimension in reference_size)
                if overlay_size != expected_size:
                    raise ValueError("Artwork ZIP PRO body overlay preview size mismatch")
                alignment = json.loads(archive.read("metadata/pro_reference_alignment.json"))
                if alignment.get("output_psd_canvas") != list(canvas):
                    raise ValueError("Artwork ZIP PRO body alignment canvas mismatch")
                if ("input_size" in alignment and
                        alignment["input_size"] != list(reference_size)):
                    raise ValueError("Artwork ZIP PRO body alignment input size mismatch")
    return {"status": "PASS", "verified_rgba_mask_pairs": len(records),
            "psd_header_checked": True, "psd_layers_verified": len(records),
            "composite_pixels_verified": True, "final_handoff_verified": require_final_handoff,
            "pro_reference_files_verified": require_pro_reference,
            "editor_import_verified": False,
            "visual_quality_verified": False}
