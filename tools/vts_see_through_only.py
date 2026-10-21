"""Compose user-authored 2D source ZIP masters; run ONLY See-through on the composite.

No isolated FACE, OUTFIT, HAIR or ACCESSORY source may be falsely treated
as a complete body/head image. Compositing is not geometry verification.
"""
from __future__ import annotations
import argparse
from io import BytesIO
import json
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
        "manual_visual_review_required": True,
        "segmentation_provider": "see-through",
        "other_generating_splitters": [],
        "warning": "Same canvas does not prove face-neck/hair/collar alignment. Inspect the actual composite before GPU inference."
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
