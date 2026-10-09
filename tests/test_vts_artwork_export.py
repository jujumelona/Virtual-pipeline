"""CPU-only tests: actual editable PSD packages and visible-pixel Qwen ownership."""
from pathlib import Path
from zipfile import ZipFile
from PIL import Image
import pytest

from tools.vts_artwork_export import build_artwork_package


def make_layers(folder, count=2):
    folder.mkdir()
    result = folder / "registered.zip"
    with ZipFile(result, "w") as z:
        for i in range(count):
            rgba = Image.new("RGBA", (256, 384), (0, 0, 0, 0))
            rgba.paste((i % 255, 100, 180, 255), (20, 40 + (i % 5), 220, 115 + (i % 5)))
            path = folder / ("part%d.png" % i)
            rgba.save(path)
            z.write(path, ("hair.front" if i == 0 else "cloth") + ".%03d.png" % i)
    return result


def test_free_is_editable_psd_with_all_real_layers(tmp_path):
    from psd_tools import PSDImage
    archive = make_layers(tmp_path / "in")
    result = build_artwork_package(archive, tmp_path / "out", edition="free", scope="upper")
    assert result["layer_count"] == 2
    assert result["moc3_generated"] is False
    with ZipFile(result["package"]) as z:
        assert set(("avatar.psd", "README_CUBISM.md")).issubset(z.namelist())
        assert len([n for n in z.namelist() if n.startswith("layers_png/")]) == 2
        assert "physics" in z.read("README_CUBISM.md").decode().lower()
        assert "moc3" in z.read("README_CUBISM.md").decode().lower()
    assert len([layer for layer in PSDImage.open(result["art_psd"]).descendants()
                if not layer.is_group()]) == 2


def test_pro_one_independent_asset_not_batch(tmp_path):
    archive = make_layers(tmp_path / "in")
    p = build_artwork_package(archive, tmp_path / "out", edition="pro", scope="full",
                              asset_kind="hair")
    with ZipFile(p["package"]) as z:
        assert "hair.psd" in z.namelist()
        assert "body.psd" not in z.namelist()
    with pytest.raises(ValueError, match="exactly one"):
        build_artwork_package(archive, tmp_path / "invalid", edition="pro", scope="full")


def test_qwen_splits_use_original_high_resolution_rgba(tmp_path):
    from psd_tools import PSDImage
    archive = make_layers(tmp_path / "in")
    before = Image.open(tmp_path / "in/part0.png").convert("RGBA")
    def fake_infer(source, output, **kwargs):
        assert kwargs["layer_count"] == 4
        output.mkdir(parents=True)
        path = []
        # Source is the bbox crop; all four layers preserve its aspect.
        base = Image.open(source).convert("RGBA")
        for i in range(4):
            out = Image.new("RGBA", base.size, (0, 0, 0, 0))
            x0 = base.width * i // 4
            x1 = base.width * (i + 1) // 4
            out.paste((100, 100, 100, 255), (x0, 0, x1, base.height))
            p = output / ("q%d.png" % i)
            out.save(p)
            path.append(str(p))
        return {"layers": path}
    p = build_artwork_package(archive, tmp_path / "out", edition="pro", scope="upper",
                              asset_kind="hair", qwen=True, max_qwen_passes=1,
                              qwen_infer=fake_infer)
    assert p["qwen_splits_accepted"] == ["hair.front.000"]
    assert p["layer_count"] == 5
    out = PSDImage.open(p["art_psd"])
    children = [x for x in out.descendants() if not x.is_group()
                and x.name.startswith("hair.front")]
    assert len(children) == 4
    # psd-tools uses USER_LAYER_MASK for RGBA in RGB PSDs. Use the
    # production importer that restores that native mask, not topil alone.
    from io import BytesIO
    from tools.vts_production import psd_to_registered_rgba
    _, layer_zip, _ = psd_to_registered_rgba(
        Path(p["art_psd"]), tmp_path / "verified", artmesh_max=None)
    canvas = Image.new("RGBA", before.size, (0, 0, 0, 0))
    with ZipFile(layer_zip) as z:
        names = [n for n in z.namelist() if n.startswith("hair.front")]
        assert len(names) == 4
        for name in reversed(names):
            canvas.alpha_composite(Image.open(BytesIO(z.read(name))).convert("RGBA"))
    from PIL import ImageChops
    assert ImageChops.difference(canvas, before).getbbox() is None


def test_free_rejects_more_than_100_parts(tmp_path):
    archive = make_layers(tmp_path / "in", 101)
    with pytest.raises(ValueError, match="FREE ArtMesh"):
        build_artwork_package(archive, tmp_path / "out", edition="free", scope="full")


def test_pro_keeps_incorrectly_classified_pixels_without_mixing_other_assets(tmp_path):
    archive = make_layers(tmp_path / "in")
    out = build_artwork_package(archive, tmp_path / "out", edition="pro",
                                scope="upper", asset_kind="hair")
    from psd_tools import PSDImage
    actual = PSDImage.open(out["art_psd"])
    assert all(layer.name.startswith("hair.") for layer in actual.descendants()
               if not layer.is_group())
    assert len([x for x in actual.descendants() if not x.is_group()]) == 2

def test_background_opaque_does_not_consume_foreground(tmp_path):
    archive = make_layers(tmp_path / "in", count=2)

    def infer(source, output, **kw):
        output.mkdir(parents=True, exist_ok=True)
        crop = Image.open(source).convert("RGBA")
        w, h = crop.size
        bg = Image.new("RGBA", (w, h), (0, 0, 0, 255))
        masks = [bg]
        for i in range(3):
            part = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            x0, x1 = w * i // 3, w * (i + 1) // 3
            part.paste((220, 120, 50, 255), (x0, 0, x1, h))
            masks.append(part)
        paths = []
        for n, image in enumerate(masks):
            path = output / f"layer_{n}.png"
            image.save(path)
            paths.append(str(path))
        return {"layers": paths}

    out = build_artwork_package(archive, tmp_path / "out", edition="pro",
                                scope="upper", asset_kind="hair", qwen=True,
                                max_qwen_passes=1, qwen_infer=infer)
    assert out["qwen_splits_accepted"] == ["hair.front.000"]
    assert out["layer_count"] >= 4

