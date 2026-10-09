"""CPU-only real PSD and VTS semantic importer contracts (no fake GPU tests)."""
from pathlib import Path
from zipfile import ZipFile

import pytest
from PIL import Image

from vtuber_pipeline.common.schemas import Part, PartsDocument, SourceSet
from vtuber_pipeline.two_d.build import _layers
from vtuber_pipeline.two_d.layer_export import write_psd_and_ora
from tools.vts_production import _semantic_family, psd_to_registered_rgba


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
        "hair_side", "arm_left", "eye_left", "cloth"
    ]
    assert _observed_split_tags(path, depth=False) == ["hair_side", "cloth"]


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
    assert "nose" not in observed
    assert "mouth" not in observed

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
