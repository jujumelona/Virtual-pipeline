"""Regression tests for actual AI-authored part ZIP files (not mask guesses)."""
from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

import pytest
from PIL import Image

from tools.vts_ai_pack_import import inspect_large_ai_pack, prepare_large_ai_pack


def _png(size, bbox, color=(255, 80, 20, 255)):
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    canvas.paste(Image.new("RGBA", (bbox[2] - bbox[0], bbox[3] - bbox[1]), color), bbox[:2])
    stream = BytesIO()
    canvas.save(stream, "PNG")
    return stream.getvalue()


def make_pack(tmp_path, *, cropped=False, method="generated", reverse=False):
    root = tmp_path / "ai.zip"
    master = Image.new("RGB", (640, 768), (200, 170, 180))
    stream = BytesIO()
    master.save(stream, "PNG")
    p1 = _png((40, 50) if cropped else (640, 768),
              (0, 0, 40, 50) if cropped else (100, 110, 140, 160))
    p2 = _png((640, 768), (120, 180, 150, 200), color=(20, 100, 230, 255))
    p3 = _png((640, 768), (220, 220, 240, 250), color=(55, 66, 99, 255))
    parts = [
        {"id": "hair_back", "file": "isolated_parts/hair_back.png",
         "creation_method": method, "draw_order": 1,
         "placement": {"left": 100, "top": 110, "width": 40, "height": 50} if cropped else None},
        {"id": "face_skin", "file": "isolated_parts/face_skin.png",
         "creation_method": "redrawn", "draw_order": 3, "placement": None},
        {"id": "hair_front", "file": "isolated_parts/hair_front.png",
         "creation_method": "edited_with_underpaint", "draw_order": 5, "placement": None},
    ]
    if reverse:
        parts.reverse()
    m = {
        "schema": "live2d/large-image-ai-artwork-pack-v2",
        "status": "GENERATED",
        "delivery_tier": "ARTWORK_SUBMITTED",
        "scope": "upper",
        "master": {"file": "outputs/master.png", "exists": True},
        "canvas": {"width": 640, "height": 768},
        "parts": parts,
    }
    with ZipFile(root, "w", ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(m))
        z.writestr("outputs/master.png", stream.getvalue())
        z.writestr("isolated_parts/hair_back.png", p1)
        z.writestr("isolated_parts/face_skin.png", p2)
        z.writestr("isolated_parts/hair_front.png", p3)
    return root


def test_manifest_deterministic_order_keeps_pixels_and_coordinates(tmp_path):
    src = make_pack(tmp_path, cropped=True, reverse=True)
    data = inspect_large_ai_pack(src)
    assert data["canvas"] == (640, 768)
    assert [p["id"] for p in data["parts"]] == ["hair_back", "face_skin", "hair_front"]
    assert data["parts"][0]["left"] == 100
    assert data["parts"][0]["top"] == 110
    assert data["parts"][0]["image"].size == (40, 50)
    assert data["visual_quality_verified"] is False


def test_mask_only_parts_are_not_accepted(tmp_path):
    src = make_pack(tmp_path, method="extracted_only")
    with pytest.raises(ValueError, match="AI_PACK_PART_NOT_AUTHORED"):
        inspect_large_ai_pack(src)


def test_draw_order_must_be_unique_and_explicit(tmp_path):
    src = make_pack(tmp_path)
    with ZipFile(src) as z:
        entries = {n: z.read(n) for n in z.namelist()}
    obj = json.loads(entries["manifest.json"])
    obj["parts"][0].pop("draw_order")
    entries["manifest.json"] = json.dumps(obj).encode()
    with ZipFile(src, "w") as z:
        for name, data in entries.items():
            z.writestr(name, data)
    with pytest.raises(ValueError, match="AI_PACK_DRAW_ORDER_REQUIRED_UNIQUE"):
        inspect_large_ai_pack(src)


def test_wrong_crop_placement_must_fail_not_guess(tmp_path):
    src = make_pack(tmp_path, cropped=True)
    with ZipFile(src) as z:
        entries = {n: z.read(n) for n in z.namelist()}
    obj = json.loads(entries["manifest.json"])
    obj["parts"][0]["placement"]["width"] = 41
    entries["manifest.json"] = json.dumps(obj).encode()
    with ZipFile(src, "w") as z:
        for name, data in entries.items():
            z.writestr(name, data)
    with pytest.raises(ValueError, match="PLACEMENT_SIZE_MISMATCH"):
        inspect_large_ai_pack(src)


def test_real_psd_import_uses_author_defined_order(tmp_path):
    pytest.importorskip("psd_tools")
    from psd_tools import PSDImage
    generated = prepare_large_ai_pack(make_pack(tmp_path, cropped=True, reverse=True), tmp_path / "result")
    psd = PSDImage.open(generated["psd"])
    leaves = [node for node in psd.descendants() if not node.is_group()]
    assert [layer.name for layer in leaves] == ["hair_back", "face_skin", "hair_front"]
    assert (leaves[0].left, leaves[0].top) == (100, 110)
    assert leaves[0].topil(apply_icc=False).size == (40, 50)
    assert generated["metadata"]["skipped_see_through"]
    assert generated["metadata"]["skipped_semantic_sam"]
    assert not generated["metadata"]["visual_quality_verified"]
