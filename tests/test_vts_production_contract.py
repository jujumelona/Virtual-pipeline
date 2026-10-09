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
