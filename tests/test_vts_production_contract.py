"""CPU-only real PSD and VTS semantic importer contracts (no fake GPU tests)."""
from pathlib import Path
from zipfile import ZipFile

import pytest
from PIL import Image

from vtuber_pipeline.common.schemas import Part, PartsDocument, SourceSet
from vtuber_pipeline.two_d.build import _layers
from vtuber_pipeline.two_d.layer_export import write_psd_and_ora
from tools.vts_production import _semantic_family, psd_to_registered_rgba


def test_import_bakes_layer_opacity_into_registered_alpha(tmp_path):
    from io import BytesIO
    from tools.vts_psd_layer import new_import_psd, create_import_layer
    psd = new_import_psd((256, 256))
    layer = create_import_layer(Image.new("RGBA", (20, 20), (90, 120, 180, 128)),
                                psd, name="face", left=7, top=11)
    layer.opacity = 128
    path = tmp_path / "opacity.psd"; psd.save(path)
    _, archive, _ = psd_to_registered_rgba(path, tmp_path / "out", artmesh_max=None)
    with ZipFile(archive) as z:
        actual = Image.open(BytesIO(z.read(z.namelist()[0])))
        assert actual.getpixel((7, 11)) == (90, 120, 180, 64)


def test_psd_registration_recomposition_preserves_overlapping_layer_order(tmp_path):
    from io import BytesIO
    from tools.vts_artwork_export import _write_psd
    rear = Image.new("RGBA", (256, 256), (20, 80, 180, 255))
    front = Image.new("RGBA", rear.size)
    front.paste((230, 30, 70, 128), (30, 40, 200, 220))
    path = tmp_path / "ordered.psd"
    _write_psd([dict(name="hair.front", image=front, depth=0),
                dict(name="face", image=rear, depth=0)], path, free=False)
    _, archive, _ = psd_to_registered_rgba(path, tmp_path / "out", artmesh_max=None)
    recomposed = Image.new("RGBA", rear.size)
    with ZipFile(archive) as z:
        assert z.namelist()[0].startswith("hair.front")
        for name in reversed(z.namelist()):
            recomposed.alpha_composite(Image.open(BytesIO(z.read(name))))
    assert recomposed.tobytes() == Image.alpha_composite(rear, front).tobytes()


@pytest.mark.parametrize("setting", ["multiply", "group_opacity", "clipping"])
def test_import_rejects_compositing_attributes_it_cannot_preserve(tmp_path, setting):
    from psd_tools.constants import BlendMode
    from tools.vts_psd_layer import new_import_psd, create_import_layer
    psd = new_import_psd((256, 256))
    group = psd.create_group(name="FACE")
    layer = create_import_layer(Image.new("RGBA", (20, 20), "red"), group, name="face")
    if setting == "multiply":
        layer.blend_mode = BlendMode.MULTIPLY
    elif setting == "group_opacity":
        group.opacity = 128
    else:
        layer.clipping = True
    path = tmp_path / "unsupported.psd"; psd.save(path)
    with pytest.raises(ValueError, match="compositing"):
        psd_to_registered_rgba(path, tmp_path / "out", artmesh_max=None)


@pytest.mark.parametrize("case", ["disabled", "shifted", "white_outside"])
def test_import_respects_psd_mask_state_and_canvas_coordinates(tmp_path, case):
    from io import BytesIO
    from psd_tools import PSDImage
    from psd_tools.api.layers import PixelLayer
    psd = PSDImage.new("RGB", (256, 256))
    layer = PixelLayer.frompil(Image.new("RGB", (32, 32), "red"), psd,
                               name="hair.front", left=10, top=10)
    mask = layer.create_mask(Image.new("L", (32 if case == "shifted" else 8, 32 if case == "shifted" else 8), 128),
                             left=20, top=20)
    if case == "disabled":
        mask.disabled = True
    if case == "white_outside":
        mask.data.background_color = 255
    path = tmp_path / "masked.psd"
    psd.save(path)
    _, archive, count = psd_to_registered_rgba(path, tmp_path / "result", artmesh_max=100)
    assert count == 1
    with ZipFile(archive) as z:
        rgba = Image.open(BytesIO(z.read(z.namelist()[0]))).convert("RGBA")
    assert rgba.getpixel((10, 10))[3] == (0 if case == "shifted" else 255)
    assert rgba.getpixel((20, 20))[3] == (255 if case == "disabled" else 128)


def test_large_named_foreground_is_not_dropped_as_background(tmp_path):
    from psd_tools import PSDImage
    from psd_tools.api.layers import PixelLayer
    psd = PSDImage.new("RGB", (256, 256))
    PixelLayer.frompil(Image.new("RGB", (256, 256), "red"), psd, name="hair.back")
    path = tmp_path / "foreground.psd"
    psd.save(path)
    _, _, count = psd_to_registered_rgba(path, tmp_path / "result", artmesh_max=100)
    assert count == 1


def test_import_combines_transparency_channel_with_user_mask(tmp_path):
    from io import BytesIO
    from psd_tools import PSDImage
    from psd_tools.api.layers import PixelLayer
    psd = PSDImage.new("RGBA", (256, 256))
    PixelLayer.frompil(Image.new("RGBA", (32, 32), (255, 0, 0, 128)),
                       psd, name="hair.front", left=10, top=10)
    path = tmp_path / "alpha_and_mask.psd"
    psd.save(path)
    _, archive, _ = psd_to_registered_rgba(path, tmp_path / "result", artmesh_max=100)
    with ZipFile(archive) as z:
        rgba = Image.open(BytesIO(z.read(z.namelist()[0]))).convert("RGBA")
    assert rgba.getpixel((10, 10)) == (255, 0, 0, 64)


def test_explicit_opaque_background_is_excluded(tmp_path):
    from psd_tools import PSDImage
    from psd_tools.api.layers import PixelLayer
    psd = PSDImage.new("RGB", (256, 256))
    PixelLayer.frompil(Image.new("RGB", (256, 256), "white"), psd, name="background")
    PixelLayer.frompil(Image.new("RGB", (32, 32), "red"), psd, name="hair.front")
    path = tmp_path / "background.psd"
    psd.save(path)
    _, _, count = psd_to_registered_rgba(path, tmp_path / "result", artmesh_max=100)
    assert count == 1


@pytest.mark.parametrize("name,expected",[
    ("Back Hair", "hair.back"),
    ("front bangs", "hair.front"),
    ("sleeve fabric", "cloth"),
    ("left iris", "eye.left.iris"),
    ("hair.back", "hair.back"),
    ("eye.right.lid", "eye.right.lid"),
    ("eyebrow.left", "eyebrow.left"),
    ("accessory pendant", "ornament"),
    ("nose", "nose"),
])
def test_semantic_taxonomy(name, expected):
    assert _semantic_family(name) == expected


def test_psd_to_live2d_artmesh_zip_and_vts_input_profile(tmp_path):
    base = tmp_path / "original"
    base.mkdir()
    parts=[]
    for index, (label, color, box) in enumerate((
        ("hair.front", (100, 120, 230, 255), (64, 0, 190, 130)),
        ("face", (250, 200, 170, 255), (58, 100, 195, 230)),
        ("cloth", (40, 60, 70, 255), (30, 200, 220, 355)),
    )):
        layer=Image.new("RGBA",(256,384),(0,0,0,0))
        layer.paste(color,box)
        rgba=base/f"{index}.png"
        mask=base/f"{index}.mask.png"
        layer.save(rgba)
        layer.getchannel("A").save(mask)
        parts.append(Part(label,str(rgba),str(mask),None,
                          list(box),30+index,[],"user"))
    psd_info=write_psd_and_ora(PartsDocument(256,384,parts,None,""),
                               str(tmp_path/"art"))
    master,zipfile,count=psd_to_registered_rgba(
        Path(psd_info["psd"]),tmp_path/"registered",artmesh_max=100)
    assert count==3
    assert master.is_file()
    with ZipFile(zipfile) as z:
        names=z.namelist()
        assert len(names)==3
        assert any(name.startswith("hair.front") for name in names)
        assert any(name.startswith("face") for name in names)
        assert any(name.startswith("cloth") for name in names)
    src=SourceSet("live2d",str(master),user_layers_zip=str(zipfile),
                  artwork_profile="vts_auto")
    result=_layers(src,tmp_path/"vts_import")
    assert result is not None
    assert len(result.parts)==3
    assert {p.semantic_id.split(".")[0] for p in result.parts}=={"hair","face","cloth"}
    # Hairless 13-required-parts contract must still apply to old workflow.
    with pytest.raises(ValueError,match="incomplete"):
        _layers(SourceSet("live2d",str(master),user_layers_zip=str(zipfile)),
                tmp_path/"legacy_import")


def test_free_fails_closed_when_psd_has_more_than_artmesh_limit(tmp_path):
    # No silent merging/flattening to pretend to satisfy the FREE license.
    from psd_tools import PSDImage
    from psd_tools.api.layers import PixelLayer
    psd=PSDImage.new("RGB",(256,384))
    for index in range(3):
        tile=Image.new("RGBA",(256,384),(0,0,0,0))
        tile.paste((120,20+index,100,255),(index*20,20,index*20+25,90))
        psd.append(PixelLayer.frompil(tile,psd,name=f"hair {index}"))
    location=tmp_path/"parts.psd"
    psd.save(location)
    with pytest.raises(ValueError,match="ArtMesh limit"):
        psd_to_registered_rgba(location,tmp_path/"too_many",artmesh_max=2)


def test_see_through_heuristic_uses_only_observed_metadata(tmp_path):
    import json
    from tools.vts_production import _observed_split_tags
    path = tmp_path / "depth.psd.json"
    path.write_text(json.dumps({"parts": {
        "hair_side": {}, "arm_left": {}, "eye_left": {}, "unknown": {},
        "cloth": {},
    }}))
    assert _observed_split_tags(path, depth=True) == [
        "hair_side", "arm_left", "eye_left", "unknown", "cloth"
    ]
    assert _observed_split_tags(path, depth=False) == ["hair_side", "unknown", "cloth"]


@pytest.mark.parametrize("asset", ["body", "hair", "outfit", "accessory"])
def test_live2d_pro_builds_each_asset_without_batch_companions(tmp_path, asset):
    from tools.vts_production import make_cubism_handoff
    from vtuber_pipeline.two_d.layer_export import write_psd_and_ora
    folder = tmp_path / "source"
    folder.mkdir()
    png = folder / "asset.png"
    reference = folder / "base.png"
    Image.new("RGBA", (256, 384), (0, 0, 0, 0)).save(reference)
    im = Image.new("RGBA", (256, 384), (0, 0, 0, 0))
    im.paste((255, 180, 200, 255), (32, 30, 180, 180))
    im.save(png)
    mask = folder / "mask.png"
    im.getchannel("A").save(mask)
    part = Part("hair.front", str(png), str(mask), None,
                [32, 30, 180, 180], 7, [], "user")
    psd = write_psd_and_ora(PartsDocument(256, 384, [part], None, ""), str(folder))
    result = make_cubism_handoff(
        png, tmp_path / ("output_" + asset), edition="pro", scope="upper",
        asset_kind=asset, reference_image=None if asset == "body" else reference,
        external_psd=Path(psd["psd"]), qwen=False)
    with ZipFile(result["package"]) as zipfile:
        assert asset + ".psd" in zipfile.namelist()
        assert "README_CUBISM.md" in zipfile.namelist()
        assert "LIVE2D_ARTWORK_GUIDE.md" in zipfile.namelist()
        assert "QUALITY_REVIEW.md" in zipfile.namelist()
        assert "input_reference/source_asset.png" in zipfile.namelist()
        assert "source_psd/see_through_layers.psd" in zipfile.namelist()
        assert zipfile.read("source_psd/see_through_layers.psd")[:4] == b"8BPS"
        assert "preview/input_vs_psd_comparison.png" in zipfile.namelist()
        import json
        meta = json.loads(zipfile.read("metadata/input_vs_psd_geometry.json"))
        assert meta["source_fidelity_verified"] is False
        if asset != "body":
            assert "input_reference/body_base.png" in zipfile.namelist()
            assert "preview/pro_body_asset_overlay.png" in zipfile.namelist()
            assert "metadata/pro_reference_alignment.json" in zipfile.namelist()
            import json
            align = json.loads(zipfile.read("metadata/pro_reference_alignment.json"))
            assert align["automatic_pose_landmark_alignment_verified"] is False
        assert "metadata/layer_manifest.json" in zipfile.namelist()
        assert "metadata/manual_rig_reference.json" in zipfile.namelist()
        assert "avatar.moc3" not in zipfile.namelist()
    assert result["state"] == "artwork_ready_editor_rig_required"

@pytest.mark.parametrize("upstream,expected", [
    ("headwear", "ornament.head"),
    ("eyewear", "ornament.eyes"),
    ("earwear", "ornament.ears"),
    ("neckwear", "ornament.neck"),
    ("handwear", "cloth.gloves"),
    ("topwear", "cloth.upper"),
    ("bottomwear", "cloth.lower"),
    ("legwear", "cloth.legs"),
    ("footwear", "shoe"),
    ("tail", "accessory.tail"),
    ("wings", "accessory.wings"),
    ("objects", "ornament.objects"),
    ("irides", "eye.iris"),
    ("eyewhite", "eye.sclera"),
    ("eyelash", "eye.lash"),
    ("head", "body.head"),
])
def test_official_see_through_names_are_not_misclassified(upstream, expected):
    assert _semantic_family(upstream) == expected

def test_eye_and_face_parts_eligible_for_real_left_right_split(tmp_path):
    import json
    from tools.vts_production import _observed_split_tags
    path = tmp_path / "sidecar.psd.json"
    path.write_text(json.dumps({"parts": {
        "eyes": {}, "irides": {}, "eyewhite": {},
        "eyebrow": {}, "eyelash": {}, "ears": {}, "nose": {}, "mouth": {},
    }}))
    observed = _observed_split_tags(path, depth=False)
    assert "eyes" in observed
    assert "irides" in observed
    assert "eyewhite" in observed
    assert "ears" in observed
    assert "nose" in observed
    assert "mouth" in observed

@pytest.mark.parametrize("name,expected", [
    ("left eyebrow", "eyebrow.left"),
    ("right brow", "eyebrow.right"),
    ("foot.left.toes", "foot.left.toes"),
    ("ornament.eyes.left", "ornament.eyes.left"),
    ("ear.right.inner", "ear.right.inner"),
    ("mouth.inner.tongue", "mouth.inner.tongue"),
])
def test_anatomy_detail_ids_survive_import(name, expected):
    assert _semantic_family(name) == expected

@pytest.mark.parametrize("name,expected", [
    ("eyebrow-l", "eyebrow.left"), ("irides-r", "eye.right.iris"),
    ("eyewhite-l", "eye.left.sclera"), ("eyelash-r", "eye.right.lash"),
    ("hairb", "hair.back"), ("hairf", "hair.front"),
    ("earr", "ear.right"), ("eyer", "eye.right"),
    ("browl", "eyebrow.left"), ("handwear-r", "cloth.gloves.right"),
])
def test_pinned_upstream_split_ids_are_preserved(name, expected):
    assert _semantic_family(name) == expected


def test_generated_square_layers_return_to_source_frame(tmp_path):
    from tools.vts_production import restore_source_canvas
    from io import BytesIO
    registered = tmp_path / "registered.zip"
    # Original portrait 256x384 pads by 64px on the left, with no scaling.
    with ZipFile(registered, "w") as z:
        im = Image.new("RGBA", (384, 384))
        im.paste((100, 150, 200, 255), (80, 20, 110, 60))
        buf = BytesIO(); im.save(buf, format="PNG")
        z.writestr("eye.left.000.png", buf.getvalue())
    restored, geometry = restore_source_canvas(registered, (256, 384), tmp_path / "restored.zip")
    assert geometry["padding_removed_xy"] == [64, 0]
    with ZipFile(restored) as z:
        layer = Image.open(BytesIO(z.read("eye.left.000.png")))
        assert layer.size == (256, 384)
        assert layer.getchannel("A").getbbox() == (16, 20, 46, 60)
        assert layer.getpixel((20, 30)) == (100, 150, 200, 255)


def test_generated_pro_body_handoff_uses_source_coordinate_frame(tmp_path, monkeypatch):
    import json
    from psd_tools import PSDImage
    from psd_tools.api.layers import PixelLayer
    from tools import vts_production as production
    master = tmp_path / "base.png"
    body = tmp_path / "body.png"
    Image.new("RGBA", (256, 384)).save(master)
    Image.new("RGBA", (256, 384)).save(body)
    psd = PSDImage.new("RGB", (384, 384))
    layer = Image.new("RGBA", (384, 384))
    layer.paste((100, 150, 200, 255), (80, 20, 110, 60))
    PixelLayer.frompil(layer, parent=psd, name="face")
    path = tmp_path / "generated.psd"; psd.save(path)
    # A pre-generated PSD intentionally skips fresh GPU decomposition and
    # its second-pass batch; keep this unit test strictly CPU-only.
    result = production.make_cubism_handoff(master, tmp_path / "out", edition="pro", scope="upper",
                                           asset_kind="body", reference_image=body,
                                           generated_psd=path)
    assert PSDImage.open(result["art_psd"]).size == (256, 384)
    with ZipFile(result["package"]) as z:
        report = json.loads(z.read("metadata/pro_reference_alignment.json"))
        assert report["output_canvas_matches_body"] is True
        from io import BytesIO
        overlay = Image.open(BytesIO(z.read("preview/pro_body_asset_overlay.png")))
        assert overlay.getpixel((20, 30))[0] > 0  # actual PSD, not blank submitted master
        manifest = json.loads(z.read("metadata/layer_manifest.json"))
        assert manifest["layers"][0]["canvas_xyxy_bbox"] == [16, 20, 46, 60]
        geometry = json.loads(z.read("metadata/input_vs_psd_geometry.json"))
        assert geometry["coordinate_transform"]["padding_removed_xy"] == [64, 0]


def test_handoff_inventory_lists_all_final_companion_files(tmp_path):
    from tools.vts_production import make_cubism_handoff
    from psd_tools import PSDImage
    from psd_tools.api.layers import PixelLayer
    master = tmp_path / "master.png"
    im = Image.new("RGBA", (256, 384)); im.paste((90, 80, 70, 255), (20, 30, 90, 100)); im.save(master)
    psd = PSDImage.new("RGB", im.size)
    PixelLayer.frompil(im, parent=psd, name="face")
    hair = Image.new("RGBA", im.size); hair.paste((20, 30, 40, 255), (10, 10, 100, 30))
    PixelLayer.frompil(hair, parent=psd, name="front hair")
    path = tmp_path / "source.psd"; psd.save(path)
    result = make_cubism_handoff(master, tmp_path / "out", edition="free", scope="upper", external_psd=path)
    with ZipFile(result["package"]) as z:
        assert set(result["supporting_files"]) == set(z.namelist()) - {"avatar.psd"}

@pytest.mark.parametrize("name,expected", [
    ("irides-l-0", "eye.left.iris.0"),
    ("eyewhite-2-r", "eye.right.sclera.2"),
    ("hairb-0", "hair.back.0"),
    ("headwear-1-l", "ornament.head.left.1"),
    ("front hair-2", "hair.front.2"),
])
def test_depth_and_side_suffixes_survive_native_postprocessing(name, expected):
    assert _semantic_family(name) == expected


def test_native_already_sided_tags_are_not_left_right_split_again(tmp_path):
    import json
    from tools.vts_production import _observed_split_tags
    path = tmp_path / "parts.json"
    path.write_text(json.dumps({"parts": {"irides-l-0": {}, "eyebrow-r": {}, "hairb-0": {}}}))
    assert _observed_split_tags(path, depth=False) == ["hairb-0"]
    assert _observed_split_tags(path, depth=True) == ["irides-l-0", "eyebrow-r", "hairb-0"]

@pytest.mark.parametrize("scope", ["upper", "full"])
@pytest.mark.parametrize("edition,asset", [("free", None), ("pro", "body"), ("pro", "hair"),
                                           ("pro", "outfit"), ("pro", "accessory")])
def test_all_ten_public_modes_make_registered_psd_handoffs(tmp_path, scope, edition, asset):
    import json
    from psd_tools import PSDImage
    from psd_tools.api.layers import PixelLayer
    from tools.vts_production import make_cubism_handoff
    # Real external PSD skips GPU inference only, exercising the complete
    # selected-mode import, package, reference and Editor-guide boundary.
    source = tmp_path / "source.png"
    body = tmp_path / "body.png"
    rgba = Image.new("RGBA", (256, 384)); rgba.paste((120, 100, 80, 255), (20, 30, 90, 100))
    rgba.save(source); rgba.save(body)
    psd = PSDImage.new("RGB", rgba.size)
    PixelLayer.frompil(rgba, parent=psd, name="face")
    hair = Image.new("RGBA", rgba.size); hair.paste((20, 30, 40, 255), (10, 10, 100, 30))
    PixelLayer.frompil(hair, parent=psd, name="front hair")
    original_psd = tmp_path / "original.psd"; psd.save(original_psd)
    result = make_cubism_handoff(source, tmp_path / "output", edition=edition, scope=scope,
                                asset_kind=asset, external_psd=original_psd,
                                reference_image=body if edition == "pro" and asset != "body" else None)
    assert result["edition"] == edition and result["scope"] == scope and result["asset_kind"] == asset
    assert result["moc3_generated"] is False
    output_name = (asset if edition == "pro" else "avatar") + ".psd"
    with ZipFile(result["package"]) as archive:
        assert output_name in archive.namelist()
        assert "OFFICIAL_EDITOR_SETTINGS.md" in archive.namelist()
        assert "60 FPS" in archive.read("OFFICIAL_EDITOR_SETTINGS.md").decode()
        assert not any(name.endswith(".moc3") for name in archive.namelist())
        manifest = json.loads(archive.read("metadata/layer_manifest.json"))
        assert manifest["edition"] == edition and manifest["scope"] == scope
        assert manifest["asset_kind"] == asset
        assert (manifest["canvas_width"], manifest["canvas_height"]) == (256, 384)
        assert ("상반신" if scope == "upper" else "전신") in archive.read("LIVE2D_ARTWORK_GUIDE.md").decode()
        assert set(result["supporting_files"]) == set(archive.namelist()) - {output_name}
    final = PSDImage.open(result["art_psd"])
    assert final.size == (256, 384)
    assert len([x for x in final.descendants() if not x.is_group()]) == 2


@pytest.mark.parametrize('scope', ['upper', 'full'])
@pytest.mark.parametrize('asset', ['hair', 'outfit', 'accessory'])
def test_detached_transparent_asset_never_enters_head_body_model(tmp_path, monkeypatch, scope, asset):
    import json
    import numpy as np
    from io import BytesIO
    from tools import vts_production as production
    image = Image.new('RGBA', (256, 384))
    image.paste((115, 50, 220, 128), (64, 40, 192, 160))
    master = tmp_path / 'asset.png'; image.save(master)
    base = tmp_path / 'base.png'; Image.new('RGBA', image.size).save(base)
    def reject(*args, **kwargs):
        raise AssertionError('An isolated asset has no full-character head/body input')
    monkeypatch.setattr(production, 'run_see_through', reject)
    result = production.make_cubism_handoff(master, tmp_path / 'out', edition='pro',
        scope=scope, asset_kind=asset, reference_image=base, qwen=False)
    with ZipFile(result['package']) as z:
        final = Image.open(BytesIO(z.read('preview/composite.png'))).convert('RGBA')
        occupied = np.array(image)[:, :, 3] > 0
        assert np.array_equal(np.array(final)[occupied], np.array(image)[occupied])
        assert final.getpixel((0, 0))[3] == 0
        preparation = json.loads(z.read('metadata/asset_preparation.json'))
        assert preparation['method'] == 'registered_source_alpha'
        assert preparation['inferred_hidden_pixels'] is False


def test_opaque_detached_asset_needs_foreground_proposal_not_head_hallucination(tmp_path, monkeypatch):
    from tools import vts_production as production
    master = tmp_path / 'outfit.png'
    Image.new('RGB', (256, 384), 'white').save(master)
    base = tmp_path / 'base.png'; Image.new('RGB', (256, 384), 'white').save(base)
    monkeypatch.setattr(production, 'run_see_through', lambda *a, **k: pytest.fail('wrong model'))
    with pytest.raises(ValueError, match='opaque.*Qwen'):
        production.make_cubism_handoff(master, tmp_path / 'out', edition='pro',
            scope='full', asset_kind='outfit', reference_image=base, qwen=False)


def test_opaque_detached_asset_uses_only_qwen_foreground_alpha_and_original_rgb(tmp_path, monkeypatch):
    import json
    from io import BytesIO
    from tools import vts_production as production, vts_qwen_refine as qwen
    master = tmp_path / 'outfit.png'
    image = Image.new('RGB', (256, 384), 'white')
    image.paste((120, 30, 220), (60, 40, 160, 180)); image.save(master)
    base = tmp_path / 'base.png'; Image.new('RGBA', image.size).save(base)
    calls = []
    def infer(source, output, **kwargs):
        calls.append(kwargs)
        output.mkdir(parents=True)
        background = output / 'layer_0.png'
        foreground = output / 'layer_1.png'
        Image.new('RGBA', image.size, (0, 0, 0, 255)).save(background)
        mask = Image.new('RGBA', image.size)
        mask.paste((0, 255, 0, 128), (60, 40, 160, 180)); mask.save(foreground)
        return {'layers': [str(background), str(foreground)]}
    monkeypatch.setattr(qwen, 'infer', infer)
    monkeypatch.setattr(production, 'run_see_through', lambda *a, **k: pytest.fail('wrong model'))
    result = production.make_cubism_handoff(master, tmp_path / 'out', edition='pro',
        scope='full', asset_kind='outfit', reference_image=base, qwen=True,
        qwen_passes=1, qwen_layers=4)
    assert len(calls) == 1  # initial extraction counts against the pass budget
    with ZipFile(result['package']) as z:
        final = Image.open(BytesIO(z.read('preview/composite.png'))).convert('RGBA')
        assert final.getpixel((80, 80)) == (120, 30, 220, 128)
        assert final.getpixel((0, 0))[3] == 0
        preparation = json.loads(z.read('metadata/asset_preparation.json'))
        assert preparation['method'] == 'qwen_foreground_mask_original_rgb'
        assert preparation['mask_visual_accuracy_verified'] is False


def test_external_psd_cannot_silently_relabel_an_incompatible_icc_profile(tmp_path):
    from PIL import ImageCms
    from psd_tools import PSDImage
    from psd_tools.constants import Resource
    from psd_tools.psd.image_resources import ImageResource
    from psd_tools.api.layers import PixelLayer
    psd = PSDImage.new('RGB', (256, 384))
    PixelLayer.frompil(Image.new('RGBA', (32, 32), (120, 20, 80, 255)), psd, name='face')
    psd.image_resources[Resource.ICC_PROFILE] = ImageResource(key=Resource.ICC_PROFILE,
        data=ImageCms.ImageCmsProfile(ImageCms.createProfile('LAB')).tobytes())
    path = tmp_path / 'profile.psd'; psd.save(path)
    with pytest.raises(ValueError, match='sRGB'):
        psd_to_registered_rgba(path, tmp_path / 'out', artmesh_max=100)


def test_srgb_psd_registration_keeps_stored_rgba_without_icc_transform(tmp_path, monkeypatch):
    from psd_tools.api import pil_io
    from tools.vts_psd_layer import new_import_psd, create_import_layer, save_import_psd
    source = Image.new('RGBA', (256, 384), (127, 90, 180, 2))
    psd = new_import_psd(source.size)
    create_import_layer(source, psd, name='hair.front')
    path = tmp_path / 'source.psd'
    save_import_psd(psd, path)
    def forbidden(*args, **kwargs):
        pytest.fail('Validated sRGB registration invoked native ICC conversion')
    monkeypatch.setattr(pil_io, '_apply_icc', forbidden)
    _, registered, _ = psd_to_registered_rgba(path, tmp_path / 'registered', artmesh_max=100)
    assert registered.is_file()
    with ZipFile(registered) as archive:
        from io import BytesIO
        images = [name for name in archive.namelist() if name.endswith('.png')]
        assert images
        image = Image.open(BytesIO(archive.read(images[0]))).convert('RGBA')
        assert image.tobytes() == source.tobytes()


def test_visible_source_rgb_fidelity_is_measured_not_declared_verified():
    from tools.vts_production import _visible_rgb_fidelity
    source = Image.new("RGB", (16, 8), (100, 130, 180))
    same = Image.new("RGBA", source.size, (100, 130, 180, 255))
    m = _visible_rgb_fidelity(source, same, rows=3)
    assert m["same_canvas"] and not m["verified"]
    assert m["fully_visible_pixel_count"] == 128
    assert m["visible_rgb_mean_absolute_error_0_255"] == 0
    assert m["exact_visible_rgb_pixel_fraction"] == 1
    same.putpixel((0, 0), (10, 20, 30, 255))
    same.putpixel((1, 0), (10, 20, 30, 0))
    altered = _visible_rgb_fidelity(source, same, rows=3)
    assert altered["fully_visible_pixel_count"] == 127
    assert altered["visible_rgb_mean_absolute_error_0_255"] > 0
    assert altered["exact_visible_rgb_pixel_fraction"] < 1
    other_size = Image.new("RGBA", (10, 8))
    assert _visible_rgb_fidelity(source, other_size)["same_canvas"] is False


def test_official_lr_runs_even_if_independent_depth_stage_fails(tmp_path, monkeypatch):
    """Depth failure must not skip eligible official left/right processing."""
    from psd_tools import PSDImage
    from tools.vts_production import _safe_refine_psd
    from tools import vts_subprocess
    import json
    from PIL import Image

    script = tmp_path / "inference" / "scripts" / "heuristic_partseg.py"
    script.parent.mkdir(parents=True)
    script.write_text("# mocked native worker", encoding="utf-8")
    source = tmp_path / "original.psd"
    source.write_bytes(b"mock psd for patched reader")
    (tmp_path / "original_depth.psd").write_bytes(b"depth")
    (tmp_path / "original.psd.json").write_text(
        json.dumps({"parts": {"handwear": {"tag": "handwear"}}}),
        encoding="utf-8")
    modes = []

    def fake_run(command, **kwargs):
        mode = command[3]
        modes.append(mode)
        if mode == "seg_wdepth":
            return 1
        assert mode == "seg_wlr"
        (tmp_path / "original_lrsplit.psd").write_bytes(b"new psd")
        return 0

    class FakePSD:
        size = (64, 64)

        def __init__(self, path):
            self.path = str(path)

        def composite(self):
            return Image.new("RGBA", (64, 64), (75, 45, 25, 255))

        def descendants(self):
            class Leaf:
                def is_group(self):
                    return False
            return [Leaf() for _ in range(3 if "lrsplit" in self.path else 2)]

    monkeypatch.setattr(vts_subprocess, "run_logged", fake_run)
    monkeypatch.setattr(PSDImage, "open", lambda p: FakePSD(p))
    result = _safe_refine_psd(source, third_party=tmp_path, worker_python="python")
    assert modes == ["seg_wdepth", "seg_wlr"]
    assert result == tmp_path / "original_lrsplit.psd"


def test_official_metadata_tag_list_does_not_truncate_at_32(tmp_path):
    import json
    from tools.vts_production import _observed_split_tags
    info = tmp_path / "all.psd.json"
    tags = {f"handwear_{i:03d}": {} for i in range(41)}
    info.write_text(json.dumps({"parts": tags}), encoding="utf-8")
    assert len(_observed_split_tags(info, depth=True)) == len(tags)
    assert len(_observed_split_tags(info, depth=False)) == len(tags)
