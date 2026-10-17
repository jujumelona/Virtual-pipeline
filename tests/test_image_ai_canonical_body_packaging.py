"""Published BODY instruction ZIPs use face/body color consistency."""
from pathlib import Path
from zipfile import ZipFile
import pytest

ROOT=Path(__file__).resolve().parents[1]
KITS=ROOT/"docs/image_ai_kits_v2"
MODES=("live2d_bust_up","live2d_upper","live2d_full")

@pytest.mark.parametrize("mode",MODES)
def test_body_zip_requires_only_source_artwork_and_matching_color(mode):
    path=KITS/"zips"/(mode+"__body.zip")
    with ZipFile(path) as z:
        assert z.testzip() is None
        assert len(z.namelist())==14
        master=z.read("00_MASTER_FIRST.md").decode("utf8")
        details=z.read("02_ADVANCED_PARTS.md").decode("utf8")
        outputs=z.read("04_OUTPUT_FILES.md").decode("utf8")
    assert "SOURCE_ART_ONLY_V7" in master
    assert "FACE_SKIN_BASE=#F2D4BE" in master
    assert "Colab" in master
    assert "목·어깨" in master
    assert "눈" in details and "홍채" in details
    assert "outputs/master.png" in outputs
    assert "expression_refs/mouth_closed.png" in outputs
    assert "expression_refs/mouth_open.png" in outputs
    assert "part_art/" not in outputs

def test_exactly_24_canonical_urls():
    files=list((KITS/"zips").glob("*.zip"))
    assert len(files)==24
    index=(KITS/"README.md").read_text(encoding="utf8")
    for mode in MODES:
        for asset in ("body","hair","outfit","accessory"):
            assert "zips/"+mode+"__"+asset+".zip" in index
    assert "docs/image_ai_kits_v2/README.md" in (ROOT/"README.md").read_text(encoding="utf8")
