"""Import image-AI authored *individual* artwork PNGs into a real layered PSD.

The image AI creates original full-canvas transparent part drawings one at a
time. Colab only assembles these original pixels; no AI source PSD or masks
are required. A source-only ZIP without part_art falls back to See-through.
"""
from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path, PurePosixPath
import re
from zipfile import ZipFile

from PIL import Image

MAX_LAYERS = 100
MAX_PART_BYTES = 48_000_000


def _ordered_member_names(z: ZipFile) -> list[str] | None:
    names = z.namelist()
    marker = "part_art/_order.txt"
    if marker not in names:
        if any(n.startswith("part_art/") for n in names):
            raise ValueError("AUTHORED_PARTS_ORDER_MISSING")
        return None
    if names.count(marker) != 1:
        raise ValueError("AUTHORED_PARTS_ORDER_DUPLICATE")
    if z.getinfo(marker).file_size > 32_000:
        raise ValueError("AUTHORED_PARTS_ORDER_TOO_LARGE")
    entries = []
    for row in z.read(marker).decode("utf-8-sig").splitlines():
        name = row.strip()
        if not name or name.startswith("#"):
            continue
        p = PurePosixPath(name)
        if (p.is_absolute() or ".." in p.parts or
                len(p.parts) != 2 or p.parts[0] != "part_art" or
                p.suffix.lower() != ".png" or "\\" in name or
                not re.fullmatch(r"[A-Za-z0-9_.-]+", p.stem)):
            raise ValueError("AUTHORED_PART_INVALID_NAME: " + name)
        entries.append(name)
    if not 2 <= len(entries) <= MAX_LAYERS or len(entries) != len(set(entries)):
        raise ValueError("AUTHORED_PART_COUNT_OR_DUPLICATE")
    actual = set(n for n in names if n.startswith("part_art/") and n.endswith(".png"))
    if actual != set(entries):
        raise ValueError("AUTHORED_PART_ORDER_MISMATCH")
    return entries


def has_authored_parts(source: Path) -> bool:
    with ZipFile(source) as z:
        return _ordered_member_names(z) is not None


def assemble_authored_parts(source: Path, master: Path, output: Path,
                            *, asset: str, edition: str, scope: str = "upper",
                            enforce_required_parts: bool = False) -> dict:
    """Require byte-backed transparent PNG and preserve each original layer.

    This is data validation and PSD assembly, NOT evidence of a working rig
    nor automatically of correct visual alignment.
    """
    if asset not in {"body", "hair", "outfit", "accessory"}:
        raise ValueError("AUTHORED_PART_UNSUPPORTED_ASSET")
    source, master = Path(source), Path(master)
    with Image.open(master) as image:
        image.load()
        canvas = image.size
        neutral_original = image.convert("RGBA")
    layers = []
    with ZipFile(source) as archive:
        members = _ordered_member_names(archive)
        if members is None:
            raise ValueError("AUTHORED_PARTS_NOT_SUPPLIED")
        for name in members:
            info = archive.getinfo(name)
            if info.file_size > MAX_PART_BYTES or info.file_size == 0:
                raise ValueError("AUTHORED_PART_OVERSIZED_OR_EMPTY: " + name)
            with Image.open(BytesIO(archive.read(name))) as image:
                image.load()
                if image.format != "PNG" or image.mode != "RGBA":
                    raise ValueError("AUTHORED_PART_REQUIRES_TRUE_RGBA: " + name)
                if image.size != canvas:
                    raise ValueError("AUTHORED_PART_CANVAS_MISMATCH: " + name)
                extrema = image.getchannel("A").getextrema()
                if extrema[0] > 0 or extrema[1] < 16:
                    raise ValueError("AUTHORED_PART_NOT_TRANSPARENT_OR_EMPTY: " + name)
                # Label/guide/background pollution is not reliably measured
                # from alpha alone. Store review flag rather than faking PASS.
                if not image.getchannel("A").getbbox():
                    raise ValueError("AUTHORED_PART_EMPTY: " + name)
                layers.append({"name": PurePosixPath(name).stem,
                               "image": image.copy(), "depth": 0})
    # A name-only audit is not visual proof, but missing independent roles
    # are a conclusive violation of the template-guided artwork contract.
    from tools.vts_part_separation_contract import audit_part_separation
    semantic_audit = audit_part_separation(
        [part["name"] for part in layers], asset=asset, scope=scope)
    if enforce_required_parts and not semantic_audit["named_role_requirements_met"]:
        raise ValueError("AUTHORED_REQUIRED_PART_ROLES_MISSING: "
                         + ", ".join(semantic_audit["missing_or_unproven_roles"]))
    # A visible neck reference is NOT underpaint. The actual separately
    # authored neck PNG must reach behind the lower face and into the torso.
    # This geometric condition is necessary but not sufficient for yaw/pitch.
    neck_geometry = {
        "status": "NOT_APPLICABLE", "native_profile_90_verified": False,
        "neck_seamless_at_extreme_poses_verified": False,
    }
    if asset == "body" and enforce_required_parts:
        from PIL import ImageChops
        def select_single(family: str):
            hits = [part for part in layers
                    if re.split(r"[._-]+", part["name"].lower())[0] == family]
            if len(hits) != 1:
                raise ValueError("AUTHORED_BODY_NECK_GEOMETRY_AMBIGUOUS: " + family)
            return hits[0]["image"].getchannel("A").point(
                lambda a: 255 if a > 10 else 0)
        face_a = select_single("face")
        neck_a = select_single("neck")
        torso_a = select_single("torso")
        bbox = face_a.getbbox()
        if not bbox:
            raise ValueError("AUTHORED_BODY_FACE_EMPTY")
        jaw = Image.new("L", canvas, 0)
        jaw_start = bbox[1] + int((bbox[3] - bbox[1]) * 0.57)
        jaw.paste(face_a.crop((bbox[0], jaw_start, bbox[2], bbox[3])),
                  (bbox[0], jaw_start))
        jaw_overlap = ImageChops.multiply(jaw, neck_a).histogram()[255]
        torso_overlap = ImageChops.multiply(torso_a, neck_a).histogram()[255]
        neck_geometry = {
            "status": "SOURCE_ALPHA_JOINT_OVERLAP_ONLY",
            "jaw_neck_shared_pixels": jaw_overlap,
            "neck_torso_shared_pixels": torso_overlap,
            "native_profile_90_verified": False,
            "neck_seamless_at_extreme_poses_verified": False,
        }
        if jaw_overlap < 16:
            raise ValueError("AUTHORED_JAW_NECK_HIDDEN_PAINT_MISSING: "
                             + str(jaw_overlap) + " pixels")
        if torso_overlap < 16:
            raise ValueError("AUTHORED_NECK_TORSO_HIDDEN_PAINT_MISSING: "
                             + str(torso_overlap) + " pixels")
    # Explicit uppermost-first order. Hidden expression variants MUST NOT
    # be visible in the neutral composite, but are retained in the PSD for
    # the native PSD2Live expression-opacity rigging engine.
    alternate = []
    for item in layers:
        tokens = set(re.split(r"[._-]+", item["name"].lower()))
        alternate.append(bool(
            ("mouth" in tokens and (tokens & {"open", "tooth", "teeth", "tongue"})) or
            ("eye" in tokens and tokens & {"closed", "close", "shut"})
        ))
    if asset == "body" and not any(
        item["name"].startswith(("mouth.close", "mouth.closed"))
        for item in layers
    ):
        raise ValueError("AUTHORED_BODY_REQUIRES_SINGLE_CLOSED_MOUTH")
    preview = Image.new("RGBA", canvas)
    for item, is_alternate in reversed(list(zip(layers, alternate))):
        if not is_alternate:
            preview.alpha_composite(item["image"])
    from PIL import ImageChops
    # Pixel fidelity is a review metric because independently generated
    # drawings can be inconsistent even with identical canvas dimensions.
    original_rgba = neutral_original
    # Pillow RGBA Image.getbbox() may ignore an RGB-only difference when
    # both alpha-difference channels are zero. Compare opaque composites on
    # BOTH black and white backdrops to catch RGB, alpha and edge errors.
    def on_matte(im, rgb):
        base = Image.new("RGBA", canvas, (*rgb, 255))
        base.alpha_composite(im)
        return base.convert("RGB")
    black = ImageChops.difference(on_matte(preview, (0, 0, 0)),
                                   on_matte(original_rgba, (0, 0, 0))).getbbox()
    white = ImageChops.difference(on_matte(preview, (255, 255, 255)),
                                   on_matte(original_rgba, (255, 255, 255))).getbbox()
    if black and white:
        difference_bbox = (min(black[0], white[0]), min(black[1], white[1]),
                           max(black[2], white[2]), max(black[3], white[3]))
    else:
        difference_bbox = black or white
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    preview.save(output / "neutral_reconstruction.png")
    if difference_bbox is not None:
        # Never pass a visibly changed or wrongly layered character to
        # PSD2Live merely because dimensions, count and names look correct.
        raise ValueError("AUTHORED_NEUTRAL_MASTER_RECONSTRUCTION_MISMATCH: "
                         + str(difference_bbox))
    from tools.vts_artwork_export import _write_psd
    psd = output / (asset + ".psd")
    _write_psd(layers, psd, free=edition == "free", compact_for_atlas=True)
    report = {
        "schema": "vtuber/authored-part-art-assembly-v1",
        "origin": "image_ai_one_part_per_generation",
        "psd": str(psd), "canvas": list(canvas),
        "parts": [x["name"] for x in layers],
        "independent_rgba_png_count": len(layers),
        "semantic_part_roles": semantic_audit,
        "neck_source_overlap": neck_geometry,
        "required_roles_enforced": enforce_required_parts,
        "neutral_hidden_alternate_parts": [
            layers[i]["name"] for i in range(len(layers)) if alternate[i]],
        "neutral_preview": str(output / "neutral_reconstruction.png"),
        "neutral_exact_same_as_master": difference_bbox is None,
        "master_reconstruction_difference_bounds": list(difference_bbox) if difference_bbox else None,
        "visual_alignment_verified": False,
        "native_rig_verified": False,
    }
    (output / "authored_parts.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report

