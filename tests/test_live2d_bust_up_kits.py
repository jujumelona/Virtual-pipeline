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
            advanced=z.read("06_ADVANCED_OFFICIAL_COMMUNITY.md").decode("utf-8")
            practical=z.read("08_PRACTICAL_TIPS.md").decode("utf-8")
            assert "precautions-for-psd-data" in advanced
            assert "synthesize-corners" in advanced
            assert "원본 기준 원화" in practical
            assert len(set(z.namelist())) == 14
            master=z.read("00_MASTER_FIRST.md").decode("utf-8")
            mode=z.read("03_MODE_RULES.md").decode("utf-8")
            safety=z.read("01_COMMON_RULES.md").decode("utf-8")
            output=z.read("04_OUTPUT_FILES.md").decode("utf-8")
            assert "live2d_bust_up" in master
            assert "하체" in mode
            if asset == "body":
                assert "52~61%" in mode
            else:
                assert "참조" in mode and "기준 신체" in mode
            assert "불투명" in safety and "마스크" in safety
            assert "isolated_parts/" in output
            assert f"live2d_bust_up__{asset}__ARTWORK.zip" in output
    assert "Live2D 바스트업" in (ROOT/"README.md").read_text(encoding="utf-8")


def test_bust_up_zips_keep_distinct_asset_specific_workmanship():
    expected = {
        "body": ("홍채", "입", "목"),
        "hair": ("앞머리", "뒷머리", "머리카락 뿌리"),
        "outfit": ("옷깃", "소매", "불투명"),
        "accessory": ("한 종류", "부착 앵커", "알파"),
    }
    distinct = set()
    for asset, phrases in expected.items():
        with ZipFile(KIT / "zips" / f"live2d_bust_up__{asset}.zip") as z:
            assert z.testzip() is None
            assert len(z.namelist()) == 14
            parts = z.read("02_ADVANCED_PARTS.md").decode("utf-8")
            tips = z.read("08_PRACTICAL_TIPS.md").decode("utf-8")
            official = z.read("06_ADVANCED_OFFICIAL_COMMUNITY.md").decode("utf-8")
            review = z.read("07_REVIEW_BEFORE_FINAL_ZIP.md").decode("utf-8")
            for phrase in phrases:
                assert phrase in (parts + tips), (asset, phrase)
            assert "precautions-for-psd-data" in official
            assert "synthesize-corners" in official
            assert "원본 기준 원화" in tips
            assert "불투명" in review
            distinct.add(tips)
    assert len(distinct) == 4
