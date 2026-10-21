"""Preserve AI-authored per-part RGBA when composing FACE / OUTFIT / HAIR.

The independent originals are evidence: never re-decompose a complete PNG if
all input ZIPs already supply registered and reconstructable part_art layers.
No guessed hidden paints or names are invented.
"""
from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path, PurePosixPath
from zipfile import ZIP_DEFLATED, ZipFile

from PIL import Image, ImageChops

from tools.vts_authored_part_art import _ordered_member_names, MAX_PART_BYTES
from tools.vts_see_through_only import _read_master, _read_registration_anchors
from tools.vts_see_through_only import _register_landmark_layers, _register_image


def _matte(im: Image.Image, rgb: tuple[int, int, int]) -> Image.Image:
    backdrop = Image.new("RGBA", im.size, (*rgb, 255))
    backdrop.alpha_composite(im)
    return backdrop.convert("RGB")


def _equivalent(a: Image.Image, b: Image.Image) -> bool:
    if a.size != b.size:
        return False
    return all(
        ImageChops.difference(_matte(a, rgb), _matte(b, rgb)).getbbox() is None
        for rgb in ((0, 0, 0), (255, 255, 255))
    )


def _part_layers(source: Path, master: Image.Image, asset: str) -> list[dict] | None:
    with ZipFile(source) as z:
        ordered = _ordered_member_names(z)
        if ordered is None:
            return None
        layers = []
        for member in ordered:
            info = z.getinfo(member)
            if not 0 < info.file_size <= MAX_PART_BYTES:
                raise ValueError("AUTHORED_PART_INVALID_SIZE: " + member)
            with Image.open(BytesIO(z.read(info))) as im:
                im.load()
                if im.format != "PNG" or im.mode != "RGBA" or im.size != master.size:
                    raise ValueError("AUTHORED_PART_INVALID_RGBA_CANVAS: " + member)
                if not im.getchannel("A").getbbox():
                    raise ValueError("AUTHORED_PART_EMPTY: " + member)
                if im.getchannel("A").getextrema()[0] != 0:
                    raise ValueError("AUTHORED_PART_NOT_TRANSPARENT: " + member)
                layers.append({"name": PurePosixPath(member).stem,
                               "image": im.copy(), "asset": asset})
        # The order file is topmost-first. Never flatten a neutral pose with
        # hidden alternates, e.g. mouth.open or eye.closed, painted on top.
        # Those variants are retained as PSD layers but not in the neutral.
        def alternate(name: str) -> bool:
            tokens = set(name.casefold().replace("_", ".").replace("-", ".").split("."))
            return bool(("mouth" in tokens and tokens.intersection(
                         {"open", "tongue", "tooth", "teeth"})) or
                        ("eye" in tokens and tokens.intersection(
                         {"closed", "close", "shut"})))
        neutral = Image.new("RGBA", master.size)
        for item in reversed(layers):
            item["hidden_neutral"] = alternate(item["name"])
            if not item["hidden_neutral"]:
                neutral.alpha_composite(item["image"])
        if not _equivalent(neutral, master):
            raise ValueError("AUTHORED_ASSET_MASTER_RECONSTRUCTION_MISMATCH: " + asset)
        return layers


def compose_preserved_parts(inputs: dict[str, Path], output: Path,
                            *, scope: str = "upper") -> dict | None:
    """Return a *real* PSD package if every asset supplies genuine part art.

    No input has parts -> caller may use See-through. A partially authored
    set -> fail; silently flattening it would destroy authored semantics.
    """
    if scope not in ("upper", "full"):
        raise ValueError("Invalid 2D scope")
    if not {"face", "outfit", "hair"} <= set(inputs):
        raise ValueError("FACE / OUTFIT / HAIR all required")
    images = {key: _read_master(Path(value), key) for key, value in inputs.items()}
    canvas = images["outfit"].size
    if any(im.size != canvas for im in images.values()):
        raise ValueError("SOURCE_PART_CANVAS_MISMATCH")
    anchors = {key: _read_registration_anchors(Path(value), key, canvas)
               for key, value in inputs.items()}
    registered, registration = _register_landmark_layers(images, anchors)
    authored = {key: _part_layers(Path(value), _read_master(Path(value), key), key)
                for key, value in inputs.items()}
    if all(v is None for v in authored.values()):
        return None
    if any(v is None for v in authored.values()):
        raise ValueError("PARTIAL_AUTHORED_SOURCES: all assets must provide part_art; "
                         "do not discard existing authored layers in See-through")
    if sum(len(v) for v in authored.values()) > 100:
        raise ValueError("AUTHORED_PART_COUNT_EXCEEDS_FREE_LIMIT")
    # Same drawing order as composite_2d: accessory, hair, face, outfit on top.
    ordered_assets = [n for n in ("accessory", "hair", "face", "outfit") if n in inputs]
    parts = []
    seen = set()
    translation = {key: tuple(registration.get(key, {}).get("translation_xy", [0, 0]))
                   for key in inputs}
    for asset in ordered_assets:
        for entry in authored[asset]:
            if entry["name"] in seen:
                raise ValueError("AUTHORED_PART_ID_COLLISION: " + entry["name"])
            seen.add(entry["name"])
            registered_layer = _register_image(entry["image"], translation[asset], asset)
            parts.append({"name": entry["name"], "image": registered_layer,
                          "source_name": entry["name"], "depth": 0,
                          "hidden_neutral": entry["hidden_neutral"]})
    reconstructed = Image.new("RGBA", canvas)
    for part in reversed(parts):
        if not part["hidden_neutral"]:
            reconstructed.alpha_composite(part["image"])
    expected = Image.new("RGBA", canvas)
    for asset in ("outfit", "face", "hair", "accessory"):
        if asset in registered:
            expected.alpha_composite(registered[asset])
    if not _equivalent(reconstructed, expected):
        raise ValueError("AUTHORED_COMPOSITE_MISMATCH: source part pixels drifted")
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    from tools.vts_artwork_export import _write_psd
    psd = output / "avatar.psd"
    _write_psd(parts, psd, free=True, compact_for_atlas=True)
    preview = output / "neutral_preserved.png"
    reconstructed.save(preview)
    package = output / "preserved_original_parts.zip"
    evidence = {
        "schema": "vtuber/preserved-multiasset-psd-v1",
        "state": "artwork_ready_editor_rig_required",
        "package": str(package),
        "art_psd": str(psd), "canvas": list(canvas),
        "layer_count": len(parts), "preserved_authored_parts": True,
        "segmentation_provider": "none-original-authored-rgba",
        "see_through_inference_executed": False,
        "neutral_exact_same_as_composite": True,
        "source_assets": list(inputs), "registered_assets": registration,
        "hidden_alternates": [p["name"] for p in parts if p["hidden_neutral"]],
        "visual_quality_verified": False,
        "native_rig_verified": False,
    }
    with ZipFile(package, "w", ZIP_DEFLATED) as z:
        z.write(psd, "avatar.psd")
        z.write(preview, "preview/neutral.png")
        z.writestr("metadata/preserved_part_art.json",
                   json.dumps(evidence, ensure_ascii=False, indent=2))
    (output / "preserved_part_report.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    return evidence
