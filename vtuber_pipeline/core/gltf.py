"""Binary-aware glTF/GLB/VRM loading helpers."""

from __future__ import annotations

import pathlib
from typing import Any


GLB_MAGIC = b"glTF"


def load_gltf(path: str | pathlib.Path) -> Any:
    """Load JSON glTF or binary GLB/VRM by file bytes, not filename suffix.

    VRM 1.0 files are binary GLB containers but normally use the .vrm suffix.
    pygltflib's generic load() dispatches by suffix and can try to decode a
    valid binary VRM as UTF-8 JSON. Sniff GLB magic and select load_binary().
    """
    from pygltflib import GLTF2

    resolved = pathlib.Path(path)
    with resolved.open("rb") as handle:
        magic = handle.read(4)

    loader = GLTF2()
    if magic == GLB_MAGIC:
        return loader.load_binary(str(resolved))
    return loader.load(str(resolved))
