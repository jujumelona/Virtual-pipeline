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
                assert "양손" in mode
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



def test_bust_up_body_never_contains_actionable_gray_proxy_or_missing_hands():
    from zipfile import ZipFile
    path = KIT / "zips" / "live2d_bust_up__body.zip"
    marker = "## [BUSTUP_COMPLETE_BODY_FINAL_PSD_V4]"
    forbidden = (
        "중립색 불투명 2D 도형 프록시",
        "단색 BODY 도형 생성",
        "목 아래 몸통은 불투명 중립색 프록시/마스크로만",
        "no elbows or hands",
        "1.65~1.95H",
        "팔꿈치·손은 그리지",
    )
    with ZipFile(path) as archive:
        assert archive.testzip() is None
        for name in archive.namelist():
            content = archive.read(name).decode("utf-8")
            if name not in ("04_OUTPUT_FILES.md", "05_OFFICIAL_REFERENCES.md"):
                assert marker in content
                original_instructions = content.split(marker, 1)[0]
                for legacy in forbidden:
                    assert legacy not in original_instructions, (name, legacy)
                # A statement prohibiting fixed framing percentages is not
                # itself an instruction to use that percentage.
                for line in original_instructions.splitlines():
                    if "52~61%" in line:
                        assert "머리의 화면 점유율" in line
                        assert "고정하지 않는다" in line, (name, line)
        delivery = archive.read("04_OUTPUT_FILES.md").decode("utf-8")
        assert "최종 결과 원화 ZIP에는 실제 편집 가능한 다층 PSD" in delivery
        assert "각 파츠의 알파 마스크" in delivery
        body = archive.read("00_MASTER_FIRST.md").decode("utf-8")
        assert "양손" in body and "배 위" in body
