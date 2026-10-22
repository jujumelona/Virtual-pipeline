"""Real PSD round-trip: multiple image-AI-authored ZIPs retain original parts."""
import json
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
from PIL import Image


def _png(im):
    buf = BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def _build_source(path, asset, *, authored=True, mismatch=False):
    size = (320, 320)
    layers = []
    box = {"face": (100, 60, 190, 155),
           "outfit": (90, 155, 200, 280),
           "hair": (95, 45, 200, 100),
           "accessory": (198, 105, 225, 130)}[asset]
    bottom = Image.new("RGBA", size)
    bottom.paste((50, 105, 190, 255), box)
    layers.append((asset + ".base", bottom))
    stripe = Image.new("RGBA", size)
    stripe.paste((245, 205, 185, 255),
                 (box[0] + 12, box[1] + 12, box[0] + 24, box[1] + 24))
    layers.insert(0, (asset + ".detail", stripe))
    if asset == "face":
        # Mouth.Open must remain editable, but invisible at neutral.
        open_mouth = Image.new("RGBA", size)
        open_mouth.paste((80, 15, 30, 255), (137, 127, 150, 145))
        layers.insert(0, ("mouth.open", open_mouth))
    master = Image.new("RGBA", size)
    for name, im in reversed(layers):
        if name != "mouth.open":
            master.alpha_composite(im)
    if mismatch:
        master.paste((120, 200, 100, 255), (280, 280, 300, 300))
    with ZipFile(path, "w") as z:
        z.writestr("outputs/master.png", _png(master))
        if authored:
            ordered = []
            for name, im in layers:
                member = "part_art/" + name + ".png"
                z.writestr(member, _png(im))
                ordered.append(member)
            z.writestr("part_art/_order.txt", "\n".join(ordered) + "\n")
    return path


def _inputs(tmp_path, **options):
    return {name: _build_source(tmp_path / (name + ".zip"), name, **options)
            for name in ("face", "hair", "outfit")}


def test_original_rgba_parts_become_native_psd_without_gpu_split(tmp_path, monkeypatch):
    from tools.vts_see_through_only import composite_2d, run_see_through
    from psd_tools import PSDImage
    import tools.vts_setup as setup

    inputs = _inputs(tmp_path)
    composition = composite_2d(inputs["face"], inputs["outfit"],
                               inputs["hair"], tmp_path / "merged")
    monkeypatch.setattr(setup, "prepare",
                        lambda **kwargs: pytest.fail("Do not install See-through"))
    result = run_see_through(composition, tmp_path / "result", "upper")
    assert result["preserved_authored_parts"] is True
    assert result["see_through_inference_executed"] is False
    assert result["neutral_exact_same_as_composite"] is True
    assert result["layer_count"] == 7
    assert "mouth.open" in result["hidden_alternates"]
    with ZipFile(result["package"]) as z:
        assert "avatar.psd" in z.namelist()
        assert "metadata/preserved_part_art.json" in z.namelist()
    psd = PSDImage.open(result["art_psd"])
    layers = [layer for layer in psd.descendants() if not layer.is_group()]
    assert len(layers) == 7
    mouth = next(layer for layer in layers if layer.name == "mouth.open")
    assert mouth.is_visible() is False
    assert mouth.topil(apply_icc=False).getchannel("A").getbbox()
    with Image.open(composition["composite_png"]) as expected:
        from tools.vts_preserved_source_parts import _equivalent
        assert _equivalent(psd.composite(apply_icc=False).convert("RGBA"),
                           expected.convert("RGBA"))


def test_missing_all_authored_parts_allows_legacy_see_through(tmp_path):
    from tools.vts_preserved_source_parts import compose_preserved_parts
    inputs = _inputs(tmp_path, authored=False)
    assert compose_preserved_parts(inputs, tmp_path / "result") is None


def test_partial_authored_parts_cannot_erase_originals(tmp_path):
    from tools.vts_preserved_source_parts import compose_preserved_parts
    inputs = _inputs(tmp_path)
    _build_source(inputs["hair"], "hair", authored=False)
    with pytest.raises(ValueError, match="PARTIAL_AUTHORED_SOURCES"):
        compose_preserved_parts(inputs, tmp_path / "result")


def test_asset_parts_must_reconstruct_actual_master(tmp_path):
    from tools.vts_preserved_source_parts import compose_preserved_parts
    inputs = _inputs(tmp_path)
    _build_source(inputs["face"], "face", mismatch=True)
    with pytest.raises(ValueError, match="AUTHORED_ASSET_MASTER_RECONSTRUCTION_MISMATCH"):
        compose_preserved_parts(inputs, tmp_path / "result")


def test_multiple_source_part_names_must_not_collide(tmp_path):
    from tools.vts_preserved_source_parts import compose_preserved_parts
    inputs = _inputs(tmp_path)
    # A duplicated role is a semantic ambiguity, not an excuse to merge PNGs.
    path = inputs["hair"]
    with ZipFile(path, "r") as z:
        data = {name: z.read(name) for name in z.namelist()}
    data["part_art/face.detail.png"] = data.pop("part_art/hair.detail.png")
    data["part_art/_order.txt"] = data["part_art/_order.txt"].replace(
        b"hair.detail.png", b"face.detail.png")
    with ZipFile(path, "w") as z:
        for name, body in data.items():
            z.writestr(name, body)
    with pytest.raises(ValueError, match="AUTHORED_PART_ID_COLLISION"):
        compose_preserved_parts(inputs, tmp_path / "result")



def test_same_psd_global_layer_order_keeps_rear_hair_behind_face(tmp_path):
    import hashlib
    from psd_tools import PSDImage
    from tools.vts_see_through_only import composite_2d, run_see_through
    inputs = _inputs(tmp_path)
    # Give back hair a DIFFERENT painted color so front/behind order is
    # visibly testable, not merely inferred from metadata.
    hair_zip = inputs["hair"]
    with ZipFile(hair_zip) as archive:
        data = {name: archive.read(name) for name in archive.namelist()}
    from PIL import Image
    import io
    for member, fill in (("part_art/hair.base.png", (190, 40, 85)),
                         ("part_art/hair.detail.png", (230, 130, 150))):
        img = Image.open(io.BytesIO(data[member])).convert("RGBA")
        a = img.getchannel("A")
        painted = Image.new("RGBA", img.size, (*fill, 0))
        painted.putalpha(a)
        buf = io.BytesIO()
        painted.save(buf, "PNG")
        data[member] = buf.getvalue()
    parts = [x.strip() for x in data["part_art/_order.txt"].decode().splitlines()]
    neutral = Image.new("RGBA", (320, 320))
    for member in reversed(parts):
        neutral.alpha_composite(Image.open(io.BytesIO(data[member])).convert("RGBA"))
    buf = io.BytesIO()
    neutral.save(buf, "PNG")
    data["outputs/master.png"] = buf.getvalue()
    with ZipFile(hair_zip, "w") as archive:
        for member, content in data.items():
            archive.writestr(member, content)
    source_hash = hashlib.sha256(b"one-original-PSD-with-interleaved-parts").hexdigest()
    positions = {
        "face.detail": 0, "face.base": 1,
        "hair.detail": 2, "hair.base": 3,
        "outfit.detail": 4, "outfit.base": 5,
        "mouth.open": 6,
    }
    for name, path in inputs.items():
        with ZipFile(path, "r") as archive:
            names = [x.removesuffix(".png").removeprefix("part_art/")
                     for x in archive.namelist()
                     if x.startswith("part_art/") and x.endswith(".png")]
        manifest = {
            "schema": "vtuber/source-psd-global-order-v1",
            "original_psd_sha256": source_hash,
            "top_first": {n: positions[n] for n in names},
        }
        with ZipFile(path, "a") as archive:
            archive.writestr("metadata/global_layer_order.json",
                             json.dumps(manifest))
    comp = composite_2d(inputs["face"], inputs["outfit"],
                        inputs["hair"], tmp_path / "composite")
    assert comp["original_global_psd_z_order_used"] is True
    from PIL import Image
    with Image.open(comp["composite_png"]) as image:
        # Hair crosses the face area, but back hair must remain behind skin.
        assert image.convert("RGBA").getpixel((150, 80))[:3] == (50, 105, 190)
    assembled = run_see_through(comp, tmp_path / "converted", "upper")
    assert assembled["original_global_psd_z_order_used"]
    assert assembled["preserved_authored_parts"]
    with Image.open(assembled["art_psd"]) as actual:
        assert actual.format == "PSD"
    neutral = Image.open(Path(assembled["art_psd"]).with_name("neutral_preserved.png"))
    with Image.open(comp["composite_png"]) as reference:
        from tools.vts_preserved_source_parts import _equivalent
        assert _equivalent(neutral.convert("RGBA"), reference.convert("RGBA"))


def test_source_psd_global_z_order_rejects_mixed_provenance(tmp_path):
    import hashlib
    from tools.vts_preserved_source_parts import compose_preserved_parts
    inputs = _inputs(tmp_path)
    for asset, path in inputs.items():
        with ZipFile(path) as z:
            entries = [x.rsplit("/", 1)[-1][:-4] for x in z.namelist()
                       if x.startswith("part_art/") and x.endswith(".png")]
        # Deliberately not the same character source: no silent mixing.
        with ZipFile(path, "a") as z:
            z.writestr("metadata/global_layer_order.json", json.dumps({
                "schema": "vtuber/source-psd-global-order-v1",
                "original_psd_sha256": hashlib.sha256(asset.encode()).hexdigest(),
                "top_first": {name: i for i, name in enumerate(entries)}
            }))
    with pytest.raises(ValueError, match="GLOBAL_LAYER_ORDER_MIXED_CHARACTER_SOURCES"):
        compose_preserved_parts(inputs, tmp_path / "out")
