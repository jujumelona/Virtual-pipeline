"""Fail-closed structural validator for externally generated 2D artwork ZIPs.

Run: python validate_artwork_zip.py artwork.zip [free|pro]
This checks files and pixels, not whether the artwork is aesthetically correct.
"""
from collections import Counter
from io import BytesIO
from pathlib import Path
import re
import sys
from zipfile import ZipFile

from PIL import Image

_PART_ID = re.compile(r"[A-Za-z][A-Za-z0-9_-]*(?:\.[A-Za-z][A-Za-z0-9_-]*)*\Z")


def validate(path: str | Path, edition: str = "pro", *, final_live2d_body: bool = False) -> None:
    if edition not in ("free", "pro"):
        raise ValueError("edition must be free or pro")
    with ZipFile(path) as archive:
        members = [m for m in archive.infolist() if not m.is_dir()]
        filenames = [m.filename for m in members]
        if len(filenames) != len(set(filenames)):
            raise ValueError("ZIP contains duplicate member paths")
        if not members or len(members) > 500:
            raise ValueError("ZIP empty or too many files")
        if sum(m.file_size for m in members) > 650 * 1024 * 1024:
            raise ValueError("ZIP uncompressed size limit exceeded")
        if archive.testzip() is not None:
            raise ValueError("ZIP CRC verification failed")
        order_paths = [n for n in filenames
                       if n == "layer_order.txt"
                       or (n.endswith("/layer_order.txt") and n.count("/") == 1)]
        if len(order_paths) != 1:
            raise ValueError("One root or single-parent layer_order.txt required")
        prefix = order_paths[0][:-len("layer_order.txt")]
        if any(not name.startswith(prefix) for name in filenames):
            raise ValueError("Mixed root and wrapped folders: choose one layout")
        if prefix + "manifest.json" in filenames:
            raise ValueError("Do not include manifest.json in simple image-only ZIP")
        if final_live2d_body:
            # This stricter gate is for actual hand-off, not intermediate PNG sprite packs.
            # Do not mistake a correctly composited flat proxy for finished VTuber art.
            if any(n.rsplit("/", 1)[-1].lower() == "body_flat_proxy.png"
                   for n in filenames):
                raise ValueError("FINAL_ARTWORK_REJECTED: flat BODY proxy is not completed torso art")
            if not any(n.lower().endswith(".psd") for n in filenames):
                raise ValueError("FINAL_ARTWORK_REJECTED: layered PSD is missing")
            if not any(n.startswith(prefix + "alpha_masks/") and n.endswith(".png")
                       for n in filenames):
                raise ValueError("FINAL_ARTWORK_REJECTED: per-part alpha masks are missing")
            if not any(n.startswith(prefix + "inputs/") for n in filenames):
                raise ValueError("FINAL_ARTWORK_REJECTED: original input is missing")
            if not any(n.endswith(".json") for n in filenames):
                raise ValueError("FINAL_ARTWORK_REJECTED: layer/validation JSON is missing")
            if not any(n.startswith(prefix + "previews/") for n in filenames):
                raise ValueError("FINAL_ARTWORK_REJECTED: visual comparison previews missing")
            # Art quality remains subject to visual review; this code cannot certify it.
        master_name = prefix + "outputs/master.png"
        if master_name not in filenames:
            raise ValueError("Missing outputs/master.png")
        names = [n.strip() for n in archive.read(order_paths[0]).decode("utf-8-sig").splitlines()
                 if n.strip() and not n.lstrip().startswith("#")]
        counts = Counter(names)
        dupes = sorted(n for n, count in counts.items() if count != 1)
        isolated = [n[len(prefix):] for n in filenames
                    if n.startswith(prefix + "isolated_parts/")]
        invalid = sorted(n for n in isolated
                         if not n.startswith("isolated_parts/")
                         or not n.endswith(".png")
                         or not _PART_ID.fullmatch(n[len("isolated_parts/"):-4]))
        if invalid:
            raise ValueError(f"Invalid isolated sprite paths: {invalid}")
        actual = set(isolated)
        listed = set(names)
        missing = sorted(listed - actual)
        unlisted = sorted(actual - listed)
        if dupes or missing or unlisted:
            raise ValueError(
                f"layer_order mismatch: duplicate={dupes}; "
                f"listed_but_missing_png={missing}; "
                f"png_not_in_layer_order={unlisted}"
            )
        if not (1 if edition == "pro" else 2) <= len(names) <= (500 if edition == "pro" else 100):
            raise ValueError(f"Invalid part count for {edition}: {len(names)}")
        for name in names:
            if (not name.startswith("isolated_parts/") or not name.endswith(".png")
                    or not _PART_ID.fullmatch(name[len("isolated_parts/"):-4])):
                raise ValueError(f"Invalid sprite path: {name!r}")
        with Image.open(BytesIO(archive.read(master_name))) as master:
            if master.format != "PNG" or master.mode not in ("RGB", "RGBA"):
                raise ValueError("Master must be RGB/RGBA PNG")
            size = master.size
        if min(size) < 256 or size[0] * size[1] > 32_000_000:
            raise ValueError("Invalid master size")
        for name in names:
            with Image.open(BytesIO(archive.read(prefix + name))) as im:
                if im.format != "PNG" or im.mode != "RGBA" or im.size != size:
                    raise ValueError(f"PNG mode/canvas mismatch: {name}: {im.mode} {im.size} != {size}")
                alpha = im.getchannel("A")
                if alpha.getbbox() is None or alpha.getextrema()[0] == 255:
                    raise ValueError(f"Empty or fully opaque sprite: {name}")
        print(f"PASS: {len(names)} unique RGBA sprites match layer_order.txt and master canvas {size}")


if __name__ == "__main__":
    args = sys.argv[1:]
    production = "--final-live2d-body" in args
    args = [arg for arg in args if arg != "--final-live2d-body"]
    if len(args) not in (1, 2):
        raise SystemExit("Usage: python validate_artwork_zip.py ARTWORK.zip [free|pro] [--final-live2d-body]")
    validate(args[0], args[1] if len(args) == 2 else "pro", final_live2d_body=production)
