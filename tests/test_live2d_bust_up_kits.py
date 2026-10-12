"""Dedicated image-AI bust-up ZIPs are real archives with independent mode contracts."""
from pathlib import Path
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parents[1]
KIT=ROOT/"docs/image_ai_kits_v2"
ASSETS=("body","hair","outfit","accessory")


def test_bust_up_four_published_zips_are_valid_and_distinct():
    index=(KIT/"README.md").read_text(encoding="utf-8")
    for asset in ASSETS:
        path=KIT/"zips"/f"live2d_bust_up__{asset}.zip"
        assert path.is_file()
        assert f"zips/live2d_bust_up__{asset}.zip" in index
        with ZipFile(path) as z:
            assert z.testzip() is None
            assert len(z.namelist()) == 14
            assert len(set(z.namelist())) == 14
            master=z.read("00_MASTER_FIRST.md").decode("utf-8")
            mode=z.read("03_MODE_RULES.md").decode("utf-8")
            safety=z.read("01_COMMON_RULES.md").decode("utf-8")
            output=z.read("04_OUTPUT_FILES.md").decode("utf-8")
            assert "live2d_bust_up" in master
            assert "1~2" in mode and "하체" in mode
            assert "불투명" in safety and "마스크" in safety
            assert "isolated_parts/" in output
            assert f"live2d_bust_up__{asset}__ARTWORK.zip" in output
    assert "Live2D 바스트업" in (ROOT/"README.md").read_text(encoding="utf-8")
