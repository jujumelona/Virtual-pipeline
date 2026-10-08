#!/usr/bin/env python3
"""Fetch only the pinned MakeHuman CC0 topology asset."""

from __future__ import annotations

import hashlib
import pathlib
import sys
import urllib.request


MAKEHUMAN_COMMIT = "a8bc2d54ff0ac92e78ff71431b1023eda42bf482"
MAKEHUMAN_BASE_GIT_BLOB_SHA1 = "d26635e9326e3cca30778fd7b9c00062b03cce09"
MAKEHUMAN_BASE_URL = (
    "https://raw.githubusercontent.com/makehumancommunity/makehuman/"
    f"{MAKEHUMAN_COMMIT}/makehuman/data/3dobjs/base.obj"
)


def _git_blob_sha1(path: pathlib.Path) -> str:
    size = path.stat().st_size
    digest = hashlib.sha1()
    digest.update(f"blob {size}\\0".encode("ascii"))
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
        actual_blob = _git_blob_sha1(tmp)
        if actual_blob != MAKEHUMAN_BASE_GIT_BLOB_SHA1:
            raise RuntimeError(
                "Downloaded MakeHuman base.obj blob mismatch: "
                f"expected {MAKEHUMAN_BASE_GIT_BLOB_SHA1}, got {actual_blob}"
            )
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
        "git_blob_sha1": MAKEHUMAN_BASE_GIT_BLOB_SHA1,
    }


if __name__ == "__main__":
    try:
        result = fetch_cc0_assets()
        print(f"Downloaded: {result['downloaded'][0]}")
    except Exception as exc:
        print(f"Failed: {exc}", file=sys.stderr)
        raise
