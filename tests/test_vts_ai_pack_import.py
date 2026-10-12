"""Regression tests for actual AI-authored part ZIP files (not mask guesses)."""
from __future__ import annotations

from io import BytesIO
import hashlib
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

def test_one_outer_zip_folder_is_allowed_without_guessing_artwork(tmp_path):
    src = make_pack(tmp_path)
    with ZipFile(src) as z:
        entries = {n: z.read(n) for n in z.namelist()}
    with ZipFile(src, "w") as z:
        for name, data in entries.items():
            z.writestr("Live2D_Character_Assets/" + name, data)
    checked = inspect_large_ai_pack(src)
    assert checked["archive_prefix"] == "Live2D_Character_Assets/"
    assert len(checked["parts"]) == 3

def make_simple_image_ai_pack(tmp_path, *, parent_prefix=""):
    path = tmp_path / "image_ai_only.zip"
    master = Image.new("RGB", (640, 768), (245, 240, 250))
    out = BytesIO()
    master.save(out, "PNG")
    p1 = _png((640, 768), (100, 110, 180, 260))
    p2 = _png((640, 768), (130, 180, 190, 280), color=(30, 70, 120, 255))
    with ZipFile(path, "w", ZIP_DEFLATED) as z:
        z.writestr(parent_prefix + "outputs/master.png", out.getvalue())
        z.writestr(parent_prefix + "isolated_parts/hair_back.png", p1)
        z.writestr(parent_prefix + "isolated_parts/face_skin.png", p2)
        z.writestr(parent_prefix + "layer_order.txt",
                   "isolated_parts/hair_back.png\n"
                   "isolated_parts/face_skin.png\n")
    return path


@pytest.mark.parametrize("prefix", ["", "Live2D_Character_Artwork/"])
def test_image_ai_only_zip_no_manifest_or_coordinates_required(tmp_path, prefix):
    source = make_simple_image_ai_pack(tmp_path, parent_prefix=prefix)
    result = inspect_large_ai_pack(source)
    assert result["archive_prefix"] == prefix
    assert result["manifest"]["schema"] == "live2d/simple-image-artwork-zip-v1"
    assert [part["id"] for part in result["parts"]] == ["hair_back", "face_skin"]
    assert all(part["image"].size == result["canvas"] for part in result["parts"])
    assert result["visual_quality_verified"] is False


def test_image_ai_only_zip_reaches_real_psd_without_metadata(tmp_path):
    pytest.importorskip("psd_tools")
    from psd_tools import PSDImage
    pack = make_simple_image_ai_pack(tmp_path)
    result = prepare_large_ai_pack(pack, tmp_path / "art")
    psd = PSDImage.open(result["psd"])
    leaves = [x for x in psd.descendants() if not x.is_group()]
    assert [p.name for p in leaves] == ["hair_back", "face_skin"]
    assert result["metadata"]["visual_quality_verified"] is False


def test_image_ai_only_zip_misaligned_canvas_refused(tmp_path):
    pack = make_simple_image_ai_pack(tmp_path)
    with ZipFile(pack) as z:
        data = {name: z.read(name) for name in z.namelist()}
    data["isolated_parts/hair_back.png"] = _png((300, 400), (20, 30, 60, 80))
    with ZipFile(pack, "w") as z:
        for name, content in data.items():
            z.writestr(name, content)
    with pytest.raises(ValueError, match="AI_PACK_CANVAS_MISMATCH"):
        inspect_large_ai_pack(pack)


def _rewrite_artwork_pack(path, modify):
    with ZipFile(path) as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}
    manifest = json.loads(entries["manifest.json"])
    modify(entries, manifest)
    entries["manifest.json"] = json.dumps(manifest).encode("utf-8")
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)


@pytest.mark.parametrize("identifier", ["eye.left.iris", "hair.back", "outfit.sleeve.left"])
def test_hierarchical_part_id_keeps_semantic_identity(tmp_path, identifier):
    source = make_pack(tmp_path)

    def modify(entries, manifest):
        manifest["parts"][0]["id"] = identifier
        manifest["parts"][0]["file"] = f"isolated_parts/{identifier}.png"
        entries[f"isolated_parts/{identifier}.png"] = entries.pop("isolated_parts/hair_back.png")

    _rewrite_artwork_pack(source, modify)
    imported = inspect_large_ai_pack(source)
    assert imported["parts"][0]["id"] == identifier


@pytest.mark.parametrize("identifier", ["eye..iris", "hair.", ".hair", "eye/left"])
def test_hierarchical_part_id_rejects_invalid_segments(tmp_path, identifier):
    source = make_pack(tmp_path)

    def modify(entries, manifest):
        manifest["parts"][0]["id"] = identifier
        manifest["parts"][0]["file"] = f"isolated_parts/{identifier}.png"

    _rewrite_artwork_pack(source, modify)
    with pytest.raises(ValueError, match="AI_PACK_PART_ID_INVALID"):
        inspect_large_ai_pack(source)


def test_manifest_declared_png_sha256_checks_bytes(tmp_path):
    source = make_pack(tmp_path)

    def modify(entries, manifest):
        manifest["master"]["sha256"] = hashlib.sha256(entries["outputs/master.png"]).hexdigest()
        manifest["parts"][0]["sha256"] = hashlib.sha256(
            entries["isolated_parts/hair_back.png"]).hexdigest()

    _rewrite_artwork_pack(source, modify)
    assert len(inspect_large_ai_pack(source)["parts"]) == 3

    def tamper(entries, manifest):
        entries["isolated_parts/hair_back.png"] = _png(
            (640, 768), (100, 110, 140, 160), color=(10, 99, 40, 255))

    _rewrite_artwork_pack(source, tamper)
    with pytest.raises(ValueError, match="AI_PACK_SHA256_MISMATCH"):
        inspect_large_ai_pack(source)


def test_manifest_rejects_wrong_master_hash_and_malformed_digest(tmp_path):
    source = make_pack(tmp_path)

    def invalid(entries, manifest):
        manifest["master"]["sha256"] = "not-a-sha256"

    _rewrite_artwork_pack(source, invalid)
    with pytest.raises(ValueError, match="AI_PACK_SHA256_INVALID"):
        inspect_large_ai_pack(source)

    def wrong(entries, manifest):
        manifest["master"]["sha256"] = "0" * 64

    _rewrite_artwork_pack(source, wrong)
    with pytest.raises(ValueError, match="AI_PACK_SHA256_MISMATCH"):
        inspect_large_ai_pack(source)
