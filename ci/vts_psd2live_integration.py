"""Real pinned JVM exports, including the sixty-layer FREE atlas regression."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from zipfile import ZipFile

from PIL import Image, ImageDraw

from tools.vts_artwork_export import _write_psd
from tools.vts_psd2live import package_psd2live, run_psd2live


def make_stress_psd(path: Path, *, oversized: bool = False) -> Path:
    """60 real layers; the cropped rectangles require more than eight pages."""
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas = (2304, 1536) if oversized else (960, 1280)
    layers = []
    for index in range(60):
        image = Image.new("RGBA", canvas)
        box = ((0, 0, *canvas) if oversized and index == 0 else
               (64, 64, 896, 1216))
        color = (40 + index * 3, 160 - index, 90 + index * 2, 255)
        image.paste(color, box)
        draw = ImageDraw.Draw(image)
        # Keep nonuniform source pixels in this source-preservation fixture.
        for x in range(box[0] + 8, box[2] - 8, 32):
            draw.line((x, box[1] + 8, x, box[3] - 8), fill=(240, 230, 220, 255))
        name = ("front hair" if index < 40 else "back hair") + f"_{index:04d}"
        layers.append({"name": name, "image": image})
    _write_psd(layers, path, free=True)
    return path


def verify_case(source: Path, destination: Path, *, edition: str,
                expected_layers: int | None = None, oversized: bool = False) -> dict:
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    result = run_psd2live(source, destination / "model", edition=edition,
                         timeout_seconds=900)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before, "Source PSD changed"
    assert result["runtime_references_valid"] is True
    assert result["cmo3"], "Editable CMO3 missing"
    fit = result["atlas_fit"]
    assert fit["source_rasters_preserved"] is True
    assert fit["artwork_resized"] is False
    if edition == "free":
        assert result["cubism_free_atlas_verified"] is True
        assert len(result["atlas_pages"]) == 1
        assert result["atlas_pages"][0]["size"] == [2048, 2048]
        assert 0 < fit["fit"] < 1, "Stress fixture did not exercise atlas fitting"
    if expected_layers is not None:
        assert fit["source_layer_count"] == expected_layers
        assert fit["packed_layer_count"] == expected_layers
    if oversized:
        assert 0 < fit["canvas_coordinate_scale"] < 1, "Oversized layer bypassed extent handling"
    else:
        assert fit["canvas_coordinate_scale"] == 1
    backup = destination / "source.zip"
    with ZipFile(backup, "w") as archive:
        archive.write(source, "avatar.psd")
    target = package_psd2live(result, backup, destination / "verified.zip")
    with ZipFile(target) as archive:
        names = archive.namelist()
        assert any(x.endswith(".model3.json") for x in names)
        assert any(x.endswith(".moc3") for x in names)
        assert any(x.endswith(".cmo3") for x in names)
        assert "metadata/psd2live_bridge.json" in names
        assert "vts_atlas.json" in names
    (destination / "bridge_result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"PSD2LIVE_REAL_ATLAS_PASS edition={edition} layers={fit['packed_layer_count']} "
          f"pages={len(result['atlas_pages'])} fit={fit['fit']} source_sha256={before}", flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=("all", "free", "oversized", "pro"), default="all")
    parser.add_argument("--output", type=Path, default=Path("psd2live-integration-output"))
    args = parser.parse_args()
    for case in ("free", "oversized", "pro"):
        if args.case not in ("all", case):
            continue
        destination = args.output / case
        if case == "pro":
            source = Path(os.environ["VTS_PSD2LIVE_HOME"]) / "examples/tml/psd-input/tml.psd"
            verify_case(source, destination, edition="pro")
        else:
            source = make_stress_psd(destination / "source" / "avatar.psd",
                                     oversized=case == "oversized")
            verify_case(source, destination, edition="free", expected_layers=60,
                        oversized=case == "oversized")


if __name__ == "__main__":
    main()
