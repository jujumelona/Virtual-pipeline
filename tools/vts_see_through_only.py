"""Compose user-authored 2D source ZIP masters; run ONLY See-through on the composite.

No isolated FACE, OUTFIT, HAIR or ACCESSORY source may be falsely treated
as a complete body/head image. Compositing is not geometry verification.
"""
from __future__ import annotations
import argparse
from io import BytesIO
import json
import math
from pathlib import Path
from zipfile import ZipFile
from PIL import Image


def _read_master(path: Path, asset: str) -> Image.Image:
    if not path.is_file():
        raise FileNotFoundError(f"{asset}: missing source ZIP {path}")
    with ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError(f"{asset}: ZIP integrity failure")
        names = [n for n in archive.namelist()
                 if n in ("outputs/master.png", "master.png", "master_original.png")
                 or n.endswith("/outputs/master.png")]
        if len(names) != 1:
            raise ValueError(f"{asset}: exactly one outputs/master.png is required")
        info = archive.getinfo(names[0])
        if not 0 < info.file_size <= 48_000_000:
            raise ValueError(f"{asset}: source PNG too big or empty")
        raw = archive.read(info)
    with Image.open(BytesIO(raw)) as image:
        image.load()
        if image.format != "PNG" or "A" not in image.getbands():
            raise ValueError(f"{asset}: genuine transparent RGBA PNG required")
        if min(image.size) < 256 or max(image.size) > 8192:
            raise ValueError(f"{asset}: invalid source dimensions {image.size}")
        alpha_min, alpha_max = image.getchannel("A").getextrema()
        if alpha_min != 0 or alpha_max == 0:
            raise ValueError(f"{asset}: transparent background and nonempty artwork required")
        return image.convert("RGBA")



def _read_registration_anchors(path: Path, asset: str,
                               canvas: tuple[int, int]) -> dict:
    """Optional image-AI-supplied pixel landmarks; never invent landmarks."""
    with ZipFile(path) as archive:
        name = "metadata/registration_anchors.json"
        if name not in archive.namelist():
            return {}
        if archive.namelist().count(name) != 1:
            raise ValueError(f"{asset}: duplicate registration anchors")
        info = archive.getinfo(name)
        if not 0 < info.file_size <= 32768:
            raise ValueError(f"{asset}: invalid anchor manifest size")
        data = json.loads(archive.read(name).decode("utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("anchors"), dict):
        raise ValueError(f"{asset}: expected {{'anchors': {{name: [x,y]}}}}")
    points = {}
    for label, pair in data["anchors"].items():
        if (not isinstance(label, str) or not label or
                not isinstance(pair, list) or len(pair) != 2 or
                any(isinstance(v, bool) or not isinstance(v, (int, float)) or
                    not math.isfinite(v) for v in pair)):
            raise ValueError(f"{asset}: invalid landmark {label!r}")
        x, y = pair
        if not 0 <= x < canvas[0] or not 0 <= y < canvas[1]:
            raise ValueError(f"{asset}: landmark outside canvas: {label}")
        points[label] = (x, y)
    return points


def _register_image(image: Image.Image, shift: tuple[int, int], asset: str) -> Image.Image:
    dx, dy = shift
    bounds = image.getchannel("A").getbbox()
    if bounds is None:
        raise ValueError(f"{asset}: empty alpha during landmark registration")
    if (bounds[0] + dx < 0 or bounds[1] + dy < 0 or
            bounds[2] + dx > image.width or bounds[3] + dy > image.height):
        raise ValueError(f"{asset}: anchor translation would crop visible artwork")
    if not dx and not dy:
        return image
    registered = Image.new("RGBA", image.size, (0, 0, 0, 0))
    registered.alpha_composite(image, (dx, dy))
    return registered


def _register_landmark_layers(images: dict, anchors: dict) -> tuple[dict, dict]:
    """Translation-only part registration. Reject scale/rotation conflicts.

    The anchor names must refer to the same *physical* point in both assets.
    Example: outfit and face share neck_joint; face and hair share hairline_center.
    """
    translations = {"outfit": (0, 0)}
    report = {}
    for asset, parents, priority in (
        ("face", ("outfit",), ("neck_joint", "neck_center")),
        ("hair", ("face",), ("hairline_center", "temple_left")),
        ("accessory", ("hair", "face", "outfit"),
         ("head_attachment", "ear_left", "ear_right", "chest_attachment")),
    ):
        if asset not in images:
            continue
        registration = None
        for parent in parents:
            matched = set(anchors.get(asset, {})) & set(anchors.get(parent, {}))
            if not matched:
                continue
            preferred = next((name for name in priority if name in matched),
                             sorted(matched)[0])
            parent_shift = translations[parent]
            px, py = anchors[parent][preferred]
            sx, sy = anchors[asset][preferred]
            dx, dy = (round(px + parent_shift[0] - sx),
                      round(py + parent_shift[1] - sy))
            disagreements = {
                name: round(math.hypot(
                    anchors[asset][name][0] + dx -
                    (anchors[parent][name][0] + parent_shift[0]),
                    anchors[asset][name][1] + dy -
                    (anchors[parent][name][1] + parent_shift[1])), 2)
                for name in sorted(matched)
            }
            if any(distance > 6.0 for distance in disagreements.values()):
                raise ValueError(
                    f"{asset}: inconsistent registration landmarks vs {parent}: "
                    + str(disagreements) + "; redraw/realign source instead of scaling it")
            registration = (parent, preferred, (dx, dy), disagreements)
            break
        if registration is None:
            translations[asset] = (0, 0)
            report[asset] = {"status": "no_common_anchors_visual_review_required",
                             "translation_xy": [0, 0]}
            continue
        parent, landmark, shift, errors = registration
        images[asset] = _register_image(images[asset], shift, asset)
        translations[asset] = shift
        report[asset] = {"status": "translation_registered", "parent": parent,
                         "primary_landmark": landmark,
                         "translation_xy": list(shift),
                         "shared_anchor_error_px": errors}
    return images, report


def composite_2d(face: Path, outfit: Path, hair: Path, output: Path,
                 accessory: Path | None = None) -> dict:
    """Fail on canvas mismatch; never hallucinate alignment with arbitrary resize."""
    inputs = {"outfit": outfit, "face": face, "hair": hair}
    if accessory is not None:
        inputs["accessory"] = accessory
    images = {name: _read_master(Path(path), name) for name, path in inputs.items()}
    canvas = images["outfit"].size
    for name, image in images.items():
        if image.size != canvas:
            raise ValueError(f"{name}: size {image.size} != OUTFIT {canvas}; "
                             "register artworks manually before See-through")
    anchors = {name: _read_registration_anchors(Path(path), name, canvas)
               for name, path in inputs.items()}
    images, registration = _register_landmark_layers(images, anchors)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    merged = Image.new("RGBA", canvas, (0, 0, 0, 0))
    for name in ("outfit", "face", "hair", "accessory"):
        if name in images:
            merged.alpha_composite(images[name])
    if not merged.getchannel("A").getbbox():
        raise ValueError("Completed source character is empty")
    master = output / "complete_character_for_see_through.png"
    merged.save(master)
    report = {
        "schema": "vtuber/see-through-only-composite-v1",
        "source_masters": {name: str(path) for name, path in inputs.items()},
        "composite_png": str(master.resolve()), "canvas": list(canvas),
        "alpha_present": True, "visual_alignment_verified": False,
        "landmark_registration": registration,
        "landmark_anchors_provided": {name: sorted(a) for name, a in anchors.items()},
        "manual_visual_review_required": True,
        "segmentation_provider": "see-through",
        "other_generating_splitters": [],
        "warning": "Landmark translations are positional checks, not proof of body geometry, paint continuity or overall composition. Inspect the composite before GPU inference."
    }
    (output / "composition_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def run_see_through(art: dict, output: Path, scope: str = "upper") -> dict:
    if scope not in ("upper", "full"):
        raise ValueError("Scope must be upper or full")
    from tools.vts_setup import prepare
    from tools.vts_production import make_cubism_handoff
    import os
    manifest_path = Path(prepare(qwen=False, install=True, sam_body=True))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    os.environ["VTUBER_SEETHROUGH_PYTHON"] = manifest["see_through_python"]
    result = make_cubism_handoff(
        Path(art["composite_png"]), output / "see_through_result",
        edition="free", scope=scope, qwen=False, psd2live=False)
    if result.get("state") != "artwork_ready_editor_rig_required":
        raise RuntimeError("See-through failed to produce checked layered PSD: " + str(result.get("state")))
    return result



def rig_see_through_artwork(separation: dict, output: Path,
                            scope: str = "upper") -> dict:
    """Continue a completed See-through artwork ZIP into PSD2Live without re-splitting.

    Native model artifacts are real but their artistic and VTube Studio behavior
    are not certified by producing the MOC3/CMO3 files.
    """
    if scope not in ("upper", "full"):
        raise ValueError("Scope must be upper or full")
    if separation.get("state") != "artwork_ready_editor_rig_required":
        raise ValueError("PSD2Live requires a completed See-through artwork handoff")
    package_value = separation.get("package")
    if not isinstance(package_value, str) or not package_value:
        raise ValueError("See-through result has no packaged PSD")
    package = Path(package_value)
    if not package.is_file() or package.suffix.lower() != ".zip":
        raise FileNotFoundError("Completed layered PSD artwork ZIP not found: " + str(package))
    from tools.vts_psd2live import prepare_psd2live, rig_existing_artwork_zip
    prepare_psd2live()
    rig = rig_existing_artwork_zip(
        package, Path(output) / "psd2live_result", edition="free", scope=scope)
    if rig.get("state") != "psd2live_rigged_unverified" or not rig.get("moc3_generated"):
        raise RuntimeError("PSD2Live did not produce its native model contract")
    return rig


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--face", type=Path, required=True)
    parser.add_argument("--hair", type=Path, required=True)
    parser.add_argument("--outfit", type=Path, required=True)
    parser.add_argument("--accessory", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scope", choices=("upper", "full"), default="upper")
    parser.add_argument("--run-see-through", action="store_true")
    parser.add_argument("--run-psd2live", action="store_true",
                        help="After See-through PSD, explicitly create native MOC3/CMO3")
    args = parser.parse_args()
    if args.run_psd2live and not args.run_see_through:
        parser.error("--run-psd2live requires --run-see-through")
    report = composite_2d(args.face, args.outfit, args.hair, args.output, args.accessory)
    if args.run_see_through:
        report["separation"] = run_see_through(report, args.output, args.scope)
    if args.run_psd2live:
        report["rigging"] = rig_see_through_artwork(
            report["separation"], args.output, args.scope)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
