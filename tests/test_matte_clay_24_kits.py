"""Source-only BODY artwork is neutral, opaque, uniform base color."""
from zipfile import ZipFile
import pytest
from tools.audit_24_image_kits import ROOT, MODES, ASSETS

@pytest.mark.parametrize("mode",MODES)
@pytest.mark.parametrize("asset",ASSETS)
def test_all_24_packages_are_scoped_and_only_request_artwork(mode,asset):
    with ZipFile(ROOT/(mode+"__"+asset+".zip")) as z:
        assert z.testzip() is None and len(z.namelist())==14
        master=z.read("00_MASTER_FIRST.md").decode("utf8")
        output=z.read("04_OUTPUT_FILES.md").decode("utf8")
        detail=z.read("02_ADVANCED_PARTS.md").decode("utf8")
    assert "SOURCE_ART_ONLY_V7" in master
    assert "Colab" in master
    assert "파츠" in master
    assert "part_art/" not in output
    assert "isolated_parts/" not in output
    if asset=="body":
        assert "FACE_SKIN_BASE" in master
        assert "마네킹" in detail
        assert "무광" in detail
        assert "해부학적" in detail
        assert "머리카락·패션 의상·장신구를 그리지 않는다" in master
    else:
        assert "BODY" in master
    if mode=="3d":
        assert "8방향" in master and "views/" in output
    else:
        assert "outputs/master.png" in output and "reference_views/" in output

def test_exactly_six_body_eighteen_detached():
    paths=list(ROOT.glob("*.zip"))
    assert len(paths)==24
    assert sum(x.name.endswith("__body.zip") for x in paths)==6
