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
            from tools.vts_psd_layer import validate_srgb_profile
            assert img.info.get("icc_profile")
            validate_srgb_profile(img.info["icc_profile"])
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
                              scope="upper", asset_kind="hair", max_qwen_passes=49)

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


def test_official_four_layer_default_applies_to_eyebrow_parts(tmp_path):
    archive = tmp_path / "eyebrows.zip"
    from io import BytesIO
    with ZipFile(archive, "w") as z:
        for name in ("eyebrow.left", "face"):
            data = BytesIO()
            Image.new("RGBA", (32, 48), (90, 120, 180, 255)).save(data, "PNG")
            z.writestr(name + ".png", data.getvalue())
    def infer(source, output, **kw):
        # Real orchestration records the requested setting; no model inference claim.
        return {"layers": [str(source)] * kw["layer_count"]}
    result = build_artwork_package(archive, tmp_path / "out", edition="free", scope="upper",
                                   qwen=True, qwen_infer=infer, max_qwen_passes=2)
    assert all(a["requested_count"] == 4 for a in result["qwen_attempts"])


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


def test_thin_part_accepts_published_16_pixel_inference_rounding(tmp_path):
    from tools.vts_artwork_export import _partition_part
    source = Image.new("RGBA", (4, 100), (90, 80, 70, 255))
    paths = []
    # compute_aspect_resize(4, 100, 640) in pinned decompose.py -> 32x640.
    for index in range(2):
        image = Image.new("RGBA", (32, 640))
        image.paste((10, 20, 30, 255), (16 * index, 0, 16 * (index + 1), 640))
        path = tmp_path / f"layer{index}.png"; image.save(path); paths.append(path)
    children = _partition_part({"name": "hair.strand", "image": source, "depth": 0}, paths)
    assert children is not None and len(children) == 2
    reconstructed = Image.new("RGBA", source.size)
    for child in children:
        reconstructed.alpha_composite(child["image"])
    assert reconstructed.tobytes() == source.tobytes()


def test_foreground_proposal_wins_equal_alpha_overlap(tmp_path):
    from tools.vts_artwork_export import _partition_part
    source = Image.new("RGBA", (40, 40), (90, 80, 70, 255))
    masks = [Image.new("RGBA", source.size, (0, 0, 0, 255)),
             Image.new("RGBA", source.size, (0, 0, 0, 255)),
             Image.new("RGBA", source.size)]
    masks[-1].paste((0, 0, 0, 255), (20, 0, 40, 40))
    paths = []
    for index, mask in enumerate(masks):
        path = tmp_path / f"layer{index}.png"; mask.save(path); paths.append(path)
    children = _partition_part({"name": "hair.front", "image": source, "depth": 0}, paths)
    assert children is not None and len(children) == 2
    assert {child["image"].getchannel("A").getbbox() for child in children} == {
        (0, 0, 20, 40), (20, 0, 40, 40)}
    # The package contract is top-to-bottom; Stable-Layers emits back-to-front.
    assert children[0]["image"].getchannel("A").getbbox() == (20, 0, 40, 40)
    assert children[1]["image"].getchannel("A").getbbox() == (0, 0, 20, 40)


def test_recursion_covers_other_observed_regions_before_repeating_hair(tmp_path):
    from io import BytesIO
    source = tmp_path / "regions.zip"
    with ZipFile(source, "w") as z:
        for name, box in [("hair.front", (0, 0, 200, 100)),
                          ("eye.left", (10, 110, 40, 130)),
                          ("mouth", (10, 140, 30, 160))]:
            image = Image.new("RGBA", (256, 384))
            image.paste((90, 80, 70, 255), box)
            buf = BytesIO(); image.save(buf, format="PNG")
            z.writestr(name + ".png", buf.getvalue())
    def infer(src, output, **kwargs):
        output.mkdir(parents=True)
        size = Image.open(src).size
        paths = []
        for index in range(2):
            image = Image.new("RGBA", size)
            image.paste((0, 0, 0, 255), (index * size[0] // 2, 0, (index + 1) * size[0] // 2, size[1]))
            path = output / f"layer{index}.png"; image.save(path); paths.append(path)
        return {"layers": paths}
    result = build_artwork_package(source, tmp_path / "out", edition="free", scope="upper",
                                   qwen=True, qwen_infer=infer, max_qwen_passes=3)
    assert {x["source_layer"] for x in result["qwen_attempts"]} == {"hair.front", "eye.left", "mouth"}


def test_free_single_flattened_character_is_not_reported_as_separated_artwork(tmp_path):
    source = make_layers(tmp_path / "in", count=1)
    with pytest.raises(ValueError, match="flattened"):
        build_artwork_package(source, tmp_path / "out", edition="free", scope="upper")


def test_cubism_psd_bakes_alpha_without_remaining_layer_masks(tmp_path):
    from psd_tools import PSDImage
    from tools.vts_artwork_export import _write_psd
    import numpy as np
    source = Image.new('RGBA', (256, 384))
    source.paste((70, 150, 210, 128), (20, 30, 100, 130))
    parts = [{'name': 'hair.front', 'image': source, 'depth': 0}]
    path = tmp_path / 'alpha.psd'
    _write_psd(parts, path, free=False)
    psd = PSDImage.open(path)
    leaves = [x for x in psd.descendants() if not x.is_group()]
    assert psd.color_mode.name == 'RGB'
    assert psd.depth == 8
    assert len(leaves) == 1
    assert leaves[0].mask is None  # Cubism official Apply Layer Mask prerequisite
    assert np.array_equal(np.asarray(leaves[0].topil().convert('RGBA')), np.asarray(source))


def test_cubism_psd_declares_the_official_srgb_profile(tmp_path):
    from io import BytesIO
    from PIL import ImageCms
    from psd_tools import PSDImage
    from psd_tools.constants import Resource
    from tools.vts_artwork_export import _write_psd
    source = Image.new('RGBA', (256, 384), (20, 80, 170, 128))
    path = tmp_path / 'profile.psd'
    _write_psd([{'name': 'hair.front', 'image': source, 'depth': 0}], path, free=False)
    profile = PSDImage.open(path).image_resources.get_data(Resource.ICC_PROFILE)
    assert profile
    assert 'srgb' in ImageCms.getProfileName(ImageCms.ImageCmsProfile(BytesIO(profile))).lower()


def test_official_editor_reference_keeps_parameter_and_physics_conventions():
    from tools.vts_official_settings import editor_settings_md
    guide = editor_settings_md()
    assert 'ParamAngleX / ParamAngleY / ParamAngleZ | -30 | 0 | 30' in guide
    assert 'ParamEyeLOpen / ParamEyeROpen | 0 | 1 | 1' in guide
    assert 'ParamBodyAngleX / ParamBodyAngleY / ParamBodyAngleZ | -10 | 0 | 10' in guide
    assert '60 FPS' in guide
    assert '실제 파라미터·키폼·물리를 생성하지 않습니다' in guide


@pytest.mark.parametrize("free", [True, False])
def test_realistic_multigroup_psd_roundtrip_preserves_z_order_and_translucent_rgba(tmp_path, free):
    """Source-derived stress case: many part families, thin translucent edges."""
    from tools.vts_artwork_export import _write_psd
    from psd_tools import PSDImage
    import numpy as np

    parts = []
    families = (("hair", "face", "eye", "body", "cloth", "mouth",
                 "accessory", "arm", "hand", "ear", "nose") * 5)
    for index, family in enumerate(families):
        rgba = np.zeros((128, 96, 4), dtype=np.uint8)
        top = (index * 9) % 60
        left = (index * 7) % 35
        rgba[top:top+45, left:left+40] = (
            (index * 19 + 40) % 256, 92, 181, 255
        )
        rgba[top:top+45, left] = (19, 88, 120, 1)
        rgba[top:top+45, left+39] = (210, 40, 60, 128)
        parts.append({
            "name": f"{family}.{index:03d}",
            "image": Image.fromarray(rgba, "RGBA"),
            "depth": 0,
        })
    target = tmp_path / "many_groups.psd"
    _write_psd(parts, target, free=free)
    saved = PSDImage.open(target)
    leaf_names = [x.name for x in saved.descendants() if not x.is_group()]
    assert leaf_names == [x["name"] for x in reversed(parts)]


def test_psd_roundtrip_preserves_hidden_rgb_under_zero_alpha(tmp_path):
    """Investigate whether psd-tools changes unseen RGB bytes in fully transparent pixels."""
    from tools.vts_artwork_export import _write_psd
    import numpy as np

    rgba = np.zeros((96, 80, 4), dtype=np.uint8)
    rgba[:, :, :3] = (73, 91, 121)
    rgba[10:70, 10:65, 3] = 255
    rgba[14:67, 14:60, 3] = 128
    _write_psd([
        {"name": "hair.hidden_rgb", "image": Image.fromarray(rgba, "RGBA"), "depth": 0},
    ], tmp_path / "hidden_rgb.psd", free=False)


def test_completed_see_through_psd_repackages_without_gpu_inference(tmp_path, monkeypatch):
    """A downstream PSD writer failure must not require 2x30 diffusion steps."""
    from psd_tools import PSDImage
    from tools.vts_psd_layer import new_import_psd, create_import_layer
    from tools import vts_production

    master = tmp_path / "source.png"
    Image.new("RGBA", (256, 384), (40, 80, 120, 255)).save(master)
    generated = tmp_path / "already_completed_see_through.psd"
    psd = new_import_psd((384, 384))
    for index, name in enumerate(("hair front", "torso body")):
        rgba = Image.new("RGBA", (384, 384))
        rgba.paste((45 + index * 60, 150, 160, 200),
                   (70 + index * 30, 80, 280, 300))
        create_import_layer(rgba, parent=psd, name=name, top=0, left=0)
    psd.save(generated)
    assert len([x for x in PSDImage.open(generated).descendants()
                if not x.is_group()]) == 2

    monkeypatch.setattr(
        vts_production, "run_see_through",
        lambda *a, **kw: pytest.fail("GPU inference called during PSD reuse"),
    )
    report = vts_production.make_cubism_handoff(
        master, tmp_path / "recovery",
        edition="free", scope="upper", generated_psd=generated,
        third_party=tmp_path,
    )
    assert report["state"] == "artwork_ready_editor_rig_required"
    assert report["reused_precomputed_see_through"] is True
    assert report["source_master_verified_against_reused_psd"] is False
    assert Path(report["art_psd"]).is_file()
    assert Path(report["package"]).is_file()


def test_generated_psd_and_external_psd_are_mutually_exclusive(tmp_path):
    from tools.vts_production import make_cubism_handoff
    master = tmp_path / "source.png"
    Image.new("RGBA", (256, 384), (40, 80, 120, 255)).save(master)
    with pytest.raises(ValueError, match="either external_psd or generated_psd"):
        make_cubism_handoff(
            master, tmp_path / "not_created", edition="free", scope="upper",
            external_psd=master, generated_psd=master,
        )
    assert not (tmp_path / "not_created").exists()


def test_native_psd_rgba_channel_roundtrip_photo_like_large_layers(tmp_path):
    """RGB-mode PSD has native transparency and losslessly stores complex RGBA."""
    from psd_tools import PSDImage
    from psd_tools.constants import ChannelID
    from tools.vts_artwork_export import _write_psd
    import numpy as np

    width, height = 768, 1024
    yy = np.arange(height, dtype=np.uint16)[:, None]
    xx = np.arange(width, dtype=np.uint16)[None, :]
    parts = []
    for part_index, family in enumerate(("hair", "face", "cloth")):
        rgba = np.empty((height, width, 4), dtype=np.uint8)
        rgba[..., 0] = ((xx * 7 + yy * 3 + part_index) % 256).astype("uint8")
        rgba[..., 1] = ((xx * 11 + yy * 5 + part_index) % 256).astype("uint8")
        rgba[..., 2] = ((xx * 2 + yy * 13 + part_index) % 256).astype("uint8")
        rgba[..., 3] = ((xx + yy * 3 + part_index * 29) % 256).astype("uint8")
        rgba[:height // 3, :width // 3, 3] = 0
        parts.append({
            "name": f"{family}.{part_index:03d}",
            "image": Image.fromarray(rgba, "RGBA"),
            "depth": 0,
        })
    path = tmp_path / "source_like_2d_artwork.psd"
    _write_psd(parts, path, free=False)
    doc = PSDImage.open(path)
    assert doc.color_mode.name == "RGB"
    assert doc.depth == 8
    assert doc.channels == 4  # native RGB plus alpha; NOT a user layer mask
    leaves = [x for x in doc.descendants() if not x.is_group()]
    assert len(leaves) == 3
    for layer in leaves:
        assert layer.mask is None
        assert ChannelID.TRANSPARENCY_MASK in {
            channel.id for channel in layer._record.channel_info
        }


def test_psd_runtime_preflight_checks_all_alpha_values_and_reports_loaded_codec():
    from tools.vts_psd_layer import verify_import_psd_runtime
    report = verify_import_psd_runtime()
    assert report['state'] == 'PASS'
    assert report['tested_alpha_values'] == 256
    assert report['rgba_byte_exact'] is True
    assert report['psd_tools_version']
    assert report['psd_tools_path']
    assert report['writer_sha256']


def test_psd_runtime_preflight_blocks_expensive_inference_on_codec_corruption(tmp_path, monkeypatch):
    from tools import vts_psd_layer, vts_production
    original = vts_psd_layer.create_import_layer

    def corrupt_translucent_pixel(image, parent, **kwargs):
        # Reproduce the reported R=127,A=2 -> R=0,A=2 failure through a real PSD.
        broken = image.copy()
        broken.putpixel((2, 0), (0, 90, 180, 2))
        return original(broken, parent, **kwargs)

    monkeypatch.setattr(vts_psd_layer, 'create_import_layer', corrupt_translucent_pixel)
    monkeypatch.setattr(vts_production, 'run_see_through',
                        lambda *a, **k: pytest.fail('Inference ran before codec validation'))
    master = tmp_path / 'master.png'
    Image.new('RGBA', (256, 384), (40, 80, 120, 255)).save(master)
    with pytest.raises(RuntimeError, match='PSD_RUNTIME_PREFLIGHT.*RGBA'):
        vts_production.make_cubism_handoff(master, tmp_path / 'out',
                                          edition='free', scope='upper')
    import json
    failure = json.loads((tmp_path / 'out/vts_failure.json').read_text())
    assert failure['stage'] == 'psd_runtime_preflight'
    assert failure['error_type'] == 'RuntimeError'
    assert 'PSD serialization mismatch' in failure['traceback']
    assert failure['runtime']['writer_sha256']
    assert (tmp_path / 'out/logs/psd_runtime/probe.psd.diagnostics/failure.json').is_file()


def test_psd_mismatch_writes_raw_channel_diagnosis_and_crops(tmp_path, monkeypatch, capsys):
    import json
    from psd_tools.api.layers import PixelLayer
    from tools.vts_artwork_export import _write_psd
    original = PixelLayer.topil

    def changed_readback(self, channel=None, apply_icc=True):
        image = original(self, channel=channel, apply_icc=apply_icc)
        if channel is None and image is not None:
            image.putpixel((433, 0), (0, 90, 180, 2))
        return image

    monkeypatch.setattr(PixelLayer, 'topil', changed_readback)
    source = Image.new('RGBA', (512, 64), (127, 90, 180, 2))
    target = tmp_path / 'avatar.psd'
    with pytest.raises(RuntimeError, match='PSD serialization mismatch'):
        _write_psd([{'name': 'hair.front.0.000', 'image': source}], target, free=False)
    diagnostic = json.loads((tmp_path / 'avatar.psd.diagnostics' / 'failure.json').read_text())
    assert diagnostic['first_difference']['xy'] == [433, 0]
    assert diagnostic['first_difference']['source_rgba'] == [127, 90, 180, 2]
    assert diagnostic['first_difference']['saved_rgba'] == [0, 90, 180, 2]
    assert diagnostic['first_difference']['raw_rgba'] == [127, 90, 180, 2]
    assert diagnostic['runtime']['psd_tools_version']
    assert (tmp_path / 'avatar.psd.diagnostics' / 'source_crop.png').is_file()
    assert (tmp_path / 'avatar.psd.diagnostics' / 'saved_crop.png').is_file()
    assert 'PSD_ROUNDTRIP_FAIL' in capsys.readouterr().out


def test_generated_psd_save_avoids_float_compositor_and_preserves_real_layers(tmp_path, monkeypatch):
    from psd_tools import PSDImage
    from tools.vts_artwork_export import _write_psd

    def unexpected_compositor(*args, **kwargs):
        pytest.fail('Generated Normal-only PSD must not load the floating point compositor')

    monkeypatch.setattr(PSDImage, 'composite', unexpected_compositor)
    source = Image.new('RGBA', (256, 384), (127, 90, 180, 2))
    target = tmp_path / 'bounded.psd'
    _write_psd([{'name': 'hair.front', 'image': source}], target, free=False)
    saved = PSDImage.open(target)
    leaf = [x for x in saved.descendants() if not x.is_group()][0]
    assert leaf.topil().tobytes() == source.tobytes()
    assert saved._record.image_data.get_data(saved._record.header)
    steps = [__import__('json').loads(line) for line in
             (tmp_path / 'bounded.psd.steps.jsonl').read_text().splitlines()]
    assert steps[-1]['operation'] == 'verified'


def test_bounded_psd_merged_preview_preserves_overlapping_opaque_scene(tmp_path):
    from psd_tools import PSDImage
    from tools.vts_artwork_export import _write_psd
    background = Image.new('RGBA', (40, 60), (80, 90, 120, 255))
    front = Image.new('RGBA', background.size)
    front.paste((190, 70, 30, 128), (5, 10, 30, 40))
    target = tmp_path / 'overlap.psd'
    _write_psd([{'name':'hair.front', 'image':front},
                {'name':'body', 'image':background}], target, free=False)
    expected = background.copy(); expected.alpha_composite(front)
    assert PSDImage.open(target).topil(apply_icc=False).tobytes() == expected.tobytes()


def test_byte_exact_roundtrip_does_not_run_icc_color_transform(tmp_path, monkeypatch):
    from psd_tools.api import pil_io
    from psd_tools import PSDImage
    from psd_tools.constants import Resource
    from tools.vts_artwork_export import _write_psd
    def forbidden(*args, **kwargs):
        pytest.fail('Serialization verification invoked the native ICC transform')
    monkeypatch.setattr(pil_io, '_apply_icc', forbidden)
    source = Image.new('RGBA', (256, 4), (127, 90, 180, 2))
    target = tmp_path / 'raw_roundtrip.psd'
    _write_psd([{'name': 'hair.front.0.000', 'image': source}], target, free=False)
    doc = PSDImage.open(target)
    assert doc.image_resources.get_data(Resource.ICC_PROFILE)
    leaf = next(x for x in doc.descendants() if not x.is_group())
    assert leaf.topil(apply_icc=False).tobytes() == source.tobytes()


def test_bilateral_geometry_split_preserves_visible_pixels_and_side_ownership():
    import numpy as np
    from tools.vts_artwork_export import _split_clear_bilateral_layer
    image = Image.new("RGBA", (200, 100))
    image.paste((220, 80, 50, 255), (15, 10, 60, 85))
    image.paste((40, 120, 220, 180), (125, 10, 184, 85))
    original = np.asarray(image)
    children = _split_clear_bilateral_layer(
        {"name": "eye.sclera.000", "depth": 0, "image": image})
    assert children is not None and len(children) == 2
    assert children[0]["name"].endswith(".image_left")
    assert children[1]["name"].endswith(".image_right")
    combined = Image.alpha_composite(children[0]["image"], children[1]["image"])
    assert np.array_equal(np.asarray(combined), original)
    assert not children[0]["image"].getchannel("A").getbbox()[2] > 60
    assert children[1]["image"].getchannel("A").getbbox()[0] >= 125
    # One connected mask cannot be correctly split without creative inpainting.
    joined = Image.new("RGBA", (200, 100), (70, 90, 120, 255))
    assert _split_clear_bilateral_layer(
        {"name": "eye.sclera.000", "depth": 0, "image": joined}) is None


def test_bilateral_splits_are_exported_to_real_psd_and_trace(tmp_path):
    import json
    from io import BytesIO
    from psd_tools import PSDImage
    source = tmp_path / "split.zip"
    with ZipFile(source, "w") as z:
        eye = Image.new("RGBA", (256, 384))
        eye.paste((60, 70, 180, 255), (40, 100, 80, 130))
        eye.paste((60, 70, 180, 255), (160, 100, 200, 130))
        face = Image.new("RGBA", eye.size)
        face.paste((190, 150, 140, 255), (70, 130, 160, 270))
        for name, im in (("eye.sclera.0", eye), ("face.0", face)):
            data = BytesIO()
            im.save(data, format="PNG")
            z.writestr(name + ".png", data.getvalue())
    result = build_artwork_package(source, tmp_path / "out",
                                   edition="free", scope="upper")
    assert result["layer_count"] == 3
    assert result["bilateral_splits"] == ["eye.sclera.0"]
    assert len([p for p in PSDImage.open(result["art_psd"]).descendants()
                if not p.is_group()]) == 3
    with ZipFile(result["package"]) as z:
        trace = json.loads(z.read("metadata/segmentation_trace.json"))
        integrity = json.loads(z.read("metadata/integrity_report.json"))
        assert trace["bilateral_image_side_splits"] == ["eye.sclera.0"]
        assert trace["qwen_attempt_count"] == 0
        assert integrity["automatic_image_side_splits"] == 1
        assert integrity["high_quality_anatomical_parts_verified"] is False


def test_qwen_request_never_silently_passes_without_any_model_attempt(tmp_path):
    from io import BytesIO
    source = tmp_path / "unknown.zip"
    with ZipFile(source, "w") as z:
        for i in range(2):
            data = BytesIO()
            Image.new("RGBA", (256, 384), (30, 40, 50, 255)).save(data, "PNG")
            z.writestr(f"unknown.{i}.png", data.getvalue())
    def must_run(*args, **kwargs):
        raise AssertionError("No semantic candidate should reach the model")
    with pytest.raises(RuntimeError, match="no eligible part"):
        build_artwork_package(source, tmp_path / "out",
                              edition="free", scope="upper", qwen=True,
                              max_qwen_passes=2, qwen_infer=must_run)


def test_qwen_partition_accepts_invisible_rgb_from_actual_psd_roundtrip(tmp_path):
    """Alpha-zero RGB is not a visible-pixel error and must not reject splitting."""
    import numpy as np
    from tools.vts_artwork_export import _partition_part
    arr = np.zeros((40, 80, 4), dtype=np.uint8)
    arr[:, :, :3] = (180, 70, 120)  # Real PSD decoders often retain RGB at alpha 0.
    arr[5:35, 8:72, :] = (30, 120, 210, 255)
    original = Image.fromarray(arr, "RGBA")
    paths = []
    for n in range(2):
        im = Image.new("RGBA", (64, 30))
        x0, x1 = (0, 32) if n == 0 else (32, 64)
        im.paste((200, 20, 60, 255), (x0, 0, x1, 30))
        path = tmp_path / f"candidate_{n}.png"
        im.save(path)
        paths.append(path)
    result = _partition_part(
        {"name": "hair.front", "depth": 0, "image": original}, paths)
    assert result is not None and len(result) == 2
    rebuilt = Image.new("RGBA", original.size)
    for child in reversed(result):
        rebuilt.alpha_composite(child["image"])
    before = np.asarray(original)
    after = np.asarray(rebuilt)
    assert np.array_equal(after[:, :, 3], before[:, :, 3])
    assert np.array_equal(after[before[:, :, 3] > 0, :3],
                          before[before[:, :, 3] > 0, :3])


def test_qwen_rejection_diagnostics_identify_mask_coverage_failure(tmp_path):
    from tools.vts_artwork_export import _partition_part
    original = Image.new("RGBA", (128, 80), (140, 80, 160, 255))
    blank = Image.new("RGBA", (128, 80))
    paths = []
    for idx in range(2):
        path = tmp_path / f"empty_{idx}.png"
        blank.save(path)
        paths.append(path)
    diagnostics = {}
    assert _partition_part({"name": "hair.front", "depth": 0, "image": original},
                           paths, diagnostics=diagnostics) is None
    assert diagnostics["result"] == "rejected"
    assert diagnostics["reason"] == "insufficient_qwen_alpha_coverage"
    assert diagnostics["coverage"] == 0


def test_sparse_alpha_bridge_still_splits_bilateral_anatomical_part():
    """A thin stray bridge must not keep two eyes trapped in one ArtMesh."""
    import numpy as np
    from PIL import Image
    from tools.vts_artwork_export import _split_clear_bilateral_layer
    arr = np.zeros((80, 200, 4), dtype=np.uint8)
    arr[10:70, 10:75] = (90, 80, 70, 255)
    arr[10:70, 125:190] = (90, 80, 70, 255)
    arr[35, 74:126] = (90, 80, 70, 32)
    original = Image.fromarray(arr, "RGBA")
    children = _split_clear_bilateral_layer({"name": "eye.sclera", "image": original, "depth": 0})
    assert children is not None and len(children) == 2
    assert all(ch["image"].getchannel("A").getbbox() for ch in children)
    recovered = np.zeros_like(arr)
    for child in children:
        mask = np.asarray(child["image"])[:, :, 3] > 0
        recovered[mask] = np.asarray(child["image"])[mask]
    np.testing.assert_array_equal(recovered, arr)


def test_connected_solid_anatomy_is_not_falsely_split():
    from PIL import Image
    from tools.vts_artwork_export import _split_clear_bilateral_layer
    original = Image.new("RGBA", (200, 80), (90, 80, 70, 255))
    assert _split_clear_bilateral_layer(
        {"name": "eye.sclera", "image": original, "depth": 0}) is None
