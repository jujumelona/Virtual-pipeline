"""Update all 20 published 2D instruction ZIPs to template-first part-by-part artwork.

The 4 three-dimensional image kits are left unchanged. Image AI draws
independent RGBA artwork; Colab performs PSD assembly/rigging.
"""
from __future__ import annotations

import argparse
import os
import re
from pathlib import Path
import tempfile
from zipfile import ZipFile

from tools.image_ai_source_only_contract import (
    BEGIN, END, source_contract, source_only_output_file,
)

ROOT = Path(__file__).resolve().parents[1] / "docs/image_ai_kits_v2/zips"
MODES = ("live2d_bust_up", "live2d_upper", "live2d_full",
         "inochi2d_upper", "inochi2d_full")
ASSETS = ("body", "hair", "outfit", "accessory")


def update_one(path: Path, *, write: bool) -> bool:
    with ZipFile(path) as original:
        infos = original.infolist()
        names = [x.filename for x in infos]
        if len(names) != 14 or len(set(names)) != 14 or original.testzip():
            raise ValueError("2D_KIT_EXPECTS_14_VALID_MDS: " + str(path))
        old = {name: original.read(name).decode("utf-8") for name in names}
    mode_name, asset = path.stem.split("__")
    contract = source_contract(mode_name, asset)
    updated = {}
    for name, body in old.items():
        old_start = "## [IMAGE_ART_MULTIVIEW_SOURCE_ONLY_V1]"
        old_end = "## [/IMAGE_ART_MULTIVIEW_SOURCE_ONLY_V1]"
        if body.count(old_start) != body.count(old_end) or body.count(old_start) > 1:
            raise ValueError("PARTIAL_OLD_MULTIVIEW_CONTRACT: " + path.name + "/" + name)
        if old_start in body:
            body = re.sub(re.escape(old_start) + r".*?" +
                          re.escape(old_end), "", body, flags=re.S)
        if body.count(BEGIN) != 1 or body.count(END) != 1:
            raise ValueError("SOURCE_ONLY_REFERENCE_MARKER_MISSING: " + path.name + "/" + name)
        begin = body.index(BEGIN) + len(BEGIN)
        end = body.index(END, begin)
        updated[name] = (
            source_only_output_file(mode_name, asset)
            if name == "04_OUTPUT_FILES.md"
            else body[:begin] + "\n" + contract + body[end:]
        )
    if updated == old:
        return False
    if not write:
        raise ValueError("2D_KIT_REBUILD_REQUIRED: " + path.name)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent, prefix="source-per-part-", suffix=".zip",
            delete=False,
        ) as stream:
            tmp = Path(stream.name)
        with ZipFile(tmp, "w") as written:
            for entry in infos:
                written.writestr(entry, updated[entry.filename].encode("utf-8"))
        with ZipFile(tmp) as check:
            if check.testzip() or check.namelist() != names:
                raise ValueError("2D_KIT_ARCHIVE_CHANGED_STRUCTURE: " + path.name)
        os.replace(tmp, path)
        tmp = None
        return True
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    args = parser.parse_args()
    changed = 0
    for mode_name in MODES:
        for asset in ASSETS:
            changed += int(update_one(
                ROOT / (mode_name + "__" + asset + ".zip"),
                write=args.write,
            ))
    print(f"20 two-dimensional source-art ZIPs verified; changed={changed}; "
          "four 3D ZIPs untouched")


if __name__ == "__main__":
    main()
