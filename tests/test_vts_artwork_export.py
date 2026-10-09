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
        assert set(("avatar.psd", "README_CUBISM.md", "LIVE2D_ARTWORK_GUIDE.md",
                    "QUALITY_REVIEW.md")).issubset(z.namelist())
        guide = z.read("LIVE2D_ARTWORK_GUIDE.md").decode("utf-8")
        quality = z.read("QUALITY_REVIEW.md").decode("utf-8")
        assert "FREE 제한 7항목" in guide
        assert "ArtPath" in guide and ".moc3" in guide
        assert "See-through" in guide and "Qwen" in guide
        assert "가려진" in quality and "- [ ]" in quality
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
        assert "PRO 헤어" in z.read("LIVE2D_ARTWORK_GUIDE.md").decode("utf-8")
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



def test_companion_files_are_real_and_coordinates_match(tmp_path):
    import hashlib
    import json
    from io import BytesIO
    from PIL import ImageChops
    source = make_layers(tmp_path / "original")
    result = build_artwork_package(source, tmp_path / "output",
                                   edition="free", scope="upper")
    with ZipFile(result["package"]) as archive:
        paths = archive.namelist()
        preview = Image.open(BytesIO(archive.read("preview/composite.png"))).convert("RGBA")
        manifest = json.loads(archive.read("metadata/layer_manifest.json"))
        guide = json.loads(archive.read("metadata/manual_rig_reference.json"))
        integrity = json.loads(archive.read("metadata/integrity_report.json"))
        trace = json.loads(archive.read("metadata/segmentation_trace.json"))
        assert guide["native_cubism_import"] is False
        assert guide["auto_rigged"] is False
        assert integrity["native_cubism_artmesh_deformer_keyforms_checked"] is False
        assert trace["attempts"] == []
        assert manifest["drawable_layer_count"] == len(manifest["layers"]) == 2
        assert manifest["canvas_width"] == 256 and manifest["canvas_height"] == 384
        reconstructed = Image.new("RGBA", (256, 384))
        for item in reversed(manifest["layers"]):
            rgba_bytes = archive.read(item["rgba_png"])
            mask_bytes = archive.read(item["alpha_mask_png"])
            img = Image.open(BytesIO(rgba_bytes)).convert("RGBA")
            mask = Image.open(BytesIO(mask_bytes))
            assert mask.mode == "L" and img.mode == "RGBA"
            assert mask.tobytes() == img.getchannel("A").tobytes()
            assert hashlib.sha256(rgba_bytes).hexdigest() == item["rgba_png_sha256"]
            assert hashlib.sha256(mask_bytes).hexdigest() == item["mask_png_sha256"]
            bbox = img.getchannel("A").getbbox()
            assert list(bbox) == item["canvas_xyxy_bbox"]
            assert 0 <= item["visible_alpha_centroid_xy"][0] < 256
            assert 0 <= item["visible_alpha_centroid_xy"][1] < 384
            reconstructed.alpha_composite(img)
        assert ImageChops.difference(preview, reconstructed).getbbox() is None


def test_qwen_invalid_recursion_parameters_rejected(tmp_path):
    archive = make_layers(tmp_path / "in")
    with pytest.raises(ValueError, match="Invalid Qwen"):
        build_artwork_package(archive, tmp_path / "wrong", edition="free",
                              scope="upper", per_pass_layers=11)
    with pytest.raises(ValueError, match="Invalid Qwen"):
        build_artwork_package(archive, tmp_path / "wrong2", edition="pro",
                              scope="upper", asset_kind="hair", max_qwen_passes=13)

@pytest.mark.parametrize("family", ["eyebrow", "arm", "hand", "leg", "foot", "ear", "neck", "nose", "shoe"])
def test_observed_anatomy_is_eligible_for_refinement(family):
    from tools.vts_artwork_export import _candidate_score
    part = {"name": family + ".left.000", "image": Image.new("RGBA", (16, 16), (80, 90, 100, 255)), "depth": 0}
    assert _candidate_score(part) > 0


def test_free_request_respects_remaining_layer_budget(tmp_path):
    archive = make_layers(tmp_path / "in", 99)
    def infer(source, output, **kw):
        assert kw["layer_count"] == 2
        output.mkdir(parents=True)
        im = Image.open(source).convert("RGBA")
        a = Image.new("RGBA", im.size)
        b = Image.new("RGBA", im.size)
        a.paste((50, 50, 50, 255), (0, 0, im.width // 2, im.height))
        b.paste((50, 50, 50, 255), (im.width // 2, 0, im.width, im.height))
        paths = [output / "a.png", output / "b.png"]
        a.save(paths[0]); b.save(paths[1])
        return {"layers": list(map(str, paths))}
    result = build_artwork_package(archive, tmp_path / "out", edition="free", scope="upper",
                                   qwen=True, qwen_infer=infer, per_pass_layers=8, max_qwen_passes=1)
    assert result["layer_count"] == 100
    assert result["qwen_attempts"][0]["accepted"] is True


def test_free_texture_budget_measures_cropped_layers_and_warns_without_resizing(tmp_path):
    import json
    from io import BytesIO
    folder = tmp_path / "input"
    folder.mkdir()
    registered = folder / "registered.zip"
    with ZipFile(registered, "w") as z:
        for i in range(2):
            im = Image.new("RGBA", (2048, 2048))
            im.paste((100, 80, 60, 255), (100, 100, 1900, 1900))
            buf = BytesIO(); im.save(buf, format="PNG")
            z.writestr(f"hair.front.{i}.png", buf.getvalue())
    result = build_artwork_package(registered, tmp_path / "out", edition="free", scope="full")
    with ZipFile(result["package"]) as z:
        report = json.loads(z.read("metadata/texture_budget.json"))
        assert report["native_scale_impossible"] is True
        assert report["cropped_area_px"] == 2 * 1800 * 1800
        assert report["uniform_scale_upper_bound"] < 1
        assert report["editor_packing_verified"] is False
        assert Image.open(BytesIO(z.read("layers_png/0000_hair.front.0.png"))).size == (2048, 2048)
        assert "texture_budget.json" in z.read("LIVE2D_ARTWORK_GUIDE.md").decode()
        assert "현재 크기" in z.read("TEXTURE_BUDGET.md").decode()


def test_pro_texture_budget_does_not_apply_free_ceiling(tmp_path):
    import json
    source = make_layers(tmp_path / "in")
    result = build_artwork_package(source, tmp_path / "out", edition="pro", scope="full", asset_kind="hair")
    with ZipFile(result["package"]) as z:
        report = json.loads(z.read("metadata/texture_budget.json"))
        assert report["free_limit_applied"] is False
        assert report["atlas_edge_px"] is None
        assert report["native_scale_impossible"] is None


def test_qwen_runtime_logs_are_in_final_package(tmp_path):
    source = make_layers(tmp_path / "in")
    def infer(src, output, **kwargs):
        output.mkdir(parents=True)
        log = output / "stable_layers_full.log"
        log.write_text("model completed: native worker evidence\n")
        image = Image.open(src).convert("RGBA")
        paths = []
        for i in range(2):
            path = output / f"layer_{i}.png"; image.save(path); paths.append(str(path))
        return {"layers": paths, "log": str(log)}
    result = build_artwork_package(source, tmp_path / "out", edition="free", scope="upper",
                                   qwen=True, qwen_infer=infer, max_qwen_passes=1)
    with ZipFile(result["package"]) as z:
        assert z.read("logs/qwen_000.log") == b"model completed: native worker evidence\n"
    assert "logs/qwen_000.log" in result["supporting_files"]
