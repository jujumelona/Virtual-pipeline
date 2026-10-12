"""Resolve 3D accessory attachment without exposing an irrelevant global UI option.

Use one unambiguous accessory-type filename or an explicit attachment field
from the user-supplied ZIP. Never silently default to a head attachment.
"""
from __future__ import annotations

import json
from pathlib import PurePosixPath, Path
from zipfile import ZipFile

from tools.colab_native import ANCHORS, _resolve_accessory_anchors

_METADATA = {
    "attachment.json", "metadata/attachment.json",
    "metadata/accessory_attachment.json", "metadata/asset.json",
    "manifest.json",
}
_TYPE_KEYS = ("accessory_type", "item_type", "subtype", "item_name")


def _type_anchor(value: str) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        anchors = _resolve_accessory_anchors(value + ".png", "AUTO")
    except ValueError:
        return None
    if len(anchors) != 1:
        raise ValueError(
            "3D_ACCESSORY_MULTIPLE_ANCHORS: cannot place paired attachments "
            "from a single one-sided image"
        )
    return anchors[0]


def resolve_accessory_placement(zip_file: Path, front_member: str) -> str:
    """Return one evidence-backed anchor; reject unknown/conflicting locations."""
    with ZipFile(zip_file) as archive:
        names = archive.namelist()
        if front_member not in names:
            raise ValueError("3D_ACCESSORY_FRONT_VIEW_MISSING")
        if len({x.casefold() for x in names}) != len(names):
            raise ValueError("3D_ACCESSORY_DUPLICATE_CASEFOLD_PATH")
        candidates = []
        for filename in names:
            if filename.casefold() not in _METADATA:
                continue
            info = archive.getinfo(filename)
            if info.file_size > 65536:
                raise ValueError("3D_ACCESSORY_METADATA_TOO_LARGE")
            try:
                data = json.loads(archive.read(info).decode("utf-8"))
            except (UnicodeError, ValueError) as exc:
                raise ValueError("3D_ACCESSORY_BAD_METADATA: " + filename) from exc
            if not isinstance(data, dict):
                raise ValueError("3D_ACCESSORY_METADATA_NOT_OBJECT")
            attach = data.get("attachment")
            objects = [data, attach] if isinstance(attach, dict) else [data]
            for obj in objects:
                for field in ("anchor", "attachment_anchor", "attach_to"):
                    if field in obj:
                        value = obj[field]
                        if not isinstance(value, str) or value.upper() not in ANCHORS:
                            raise ValueError("3D_ACCESSORY_BAD_ANCHOR: " + str(value))
                        candidates.append(value.upper())
                for field in _TYPE_KEYS:
                    guess = _type_anchor(obj.get(field))
                    if guess:
                        candidates.append(guess)
        guess = _type_anchor(PurePosixPath(front_member).stem)
        if guess:
            candidates.append(guess)
        unique = tuple(dict.fromkeys(candidates))
        if len(unique) != 1:
            if unique:
                raise ValueError("3D_ACCESSORY_CONFLICTING_PLACEMENTS: " + str(unique))
            raise ValueError(
                "3D_ACCESSORY_PLACEMENT_UNKNOWN: provide a descriptive "
                "accessory filename or attachment.json in the input ZIP"
            )
        return unique[0]
