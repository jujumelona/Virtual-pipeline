#!/usr/bin/env python3
"""Fetch only the pinned MakeHuman CC0 topology asset."""

from __future__ import annotations

import pathlib
import sys
import urllib.request


MAKEHUMAN_COMMIT = "a8bc2d54ff0ac92e78ff71431b1023eda42bf482"
MAKEHUMAN_BASE_URL = (
    "https://raw.githubusercontent.com/makehumancommunity/makehuman/"
    f"{MAKEHUMAN_COMMIT}/makehuman/data/3dobjs/base.obj"
)


def fetch_cc0_assets(output_dir: str = "assets/makehuman_cc0"):
    """Download the exact CC0 base.obj used by the production resolver."""
    output = pathlib.Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    target = output / "base.obj"
    tmp = target.with_suffix(".obj.tmp")

    try:
        with urllib.request.urlopen(MAKEHUMAN_BASE_URL, timeout=60) as response:
            with tmp.open("wb") as handle:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
        if not tmp.is_file() or tmp.stat().st_size == 0:
            raise RuntimeError("Downloaded MakeHuman base.obj is empty")
        tmp.replace(target)
    finally:
        if tmp.exists():
            tmp.unlink()

    (output / "LICENSE").write_text(
        "# MakeHuman CC0 base mesh\n\n"
        f"Pinned source commit: {MAKEHUMAN_COMMIT}\n"
        "Asset: makehuman/data/3dobjs/base.obj\n"
        "License: CC0 1.0 / Public Domain Dedication\n",
        encoding="utf-8",
    )
    return {
        "downloaded": [str(target)],
        "failed": [],
        "source_commit": MAKEHUMAN_COMMIT,
    }


if __name__ == "__main__":
    try:
        result = fetch_cc0_assets()
        print(f"Downloaded: {result['downloaded'][0]}")
    except Exception as exc:
        print(f"Failed: {exc}", file=sys.stderr)
        raise
