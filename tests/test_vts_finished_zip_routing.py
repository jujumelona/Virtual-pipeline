"""Production routing contract for uploaded, finished 3D accessory artwork ZIPs."""
from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from tools.vts_finished_zip_routing import resolve_accessory_placement


def _make(tmp_path: Path, *, front: str = "views/accessory_front.png", metadata=None) -> Path:
    path = tmp_path / "artwork.zip"
    with ZipFile(path, "w") as archive:
        archive.writestr(front, b"PNG-for-routing-only")
        if metadata is not None:
            archive.writestr("metadata/attachment.json", json.dumps(metadata))
    return path


def test_metadata_declares_one_real_attachment(tmp_path):
    source = _make(tmp_path, metadata={"attachment": {"anchor": "NECK"}})
    assert resolve_accessory_placement(source, "views/accessory_front.png") == "NECK"


def test_descriptive_input_filename_resolves_unambiguous_attachment(tmp_path):
    source = _make(tmp_path, front="views/hat_front.png")
    assert resolve_accessory_placement(source, "views/hat_front.png") == "HEAD_TOP"


def test_generic_accessory_filename_never_silently_becomes_head(tmp_path):
    source = _make(tmp_path)
    with pytest.raises(ValueError, match="3D_ACCESSORY_PLACEMENT_UNKNOWN"):
        resolve_accessory_placement(source, "views/accessory_front.png")


def test_conflicting_explicit_and_inferred_locations_are_not_guessed(tmp_path):
    source = _make(tmp_path, front="views/hat_front.png",
                   metadata={"attachment_anchor": "NECK"})
    with pytest.raises(ValueError, match="3D_ACCESSORY_CONFLICTING_PLACEMENTS"):
        resolve_accessory_placement(source, "views/hat_front.png")


def test_multiple_attachment_sides_need_a_multi_part_plan(tmp_path):
    source = _make(tmp_path, front="views/earring_front.png")
    with pytest.raises(ValueError, match="3D_ACCESSORY_MULTIPLE_ANCHORS"):
        resolve_accessory_placement(source, "views/earring_front.png")
