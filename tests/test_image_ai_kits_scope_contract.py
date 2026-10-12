"""Published image-AI ZIPs are executable, isolated drawing briefs, not interchangeable templates."""
from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import pytest

ROOT = Path(__file__).resolve().parents[1] / "docs" / "image_ai_kits_v2"
MODES = ("live2d_bust_up", "live2d_upper", "live2d_full",
         "inochi2d_upper", "inochi2d_full", "3d")
ASSETS = ("body", "hair", "outfit", "accessory")
SCOPED = ("00_MASTER_FIRST.md", "00_READ_FIRST.md", "01_COMMON_RULES.md",
          "03_MODE_RULES.md", "04_OUTPUT_FILES.md",
          "09_VISUAL_ART_QUALITY.md", "10_ANIME_STYLE.md",
          "11_OFFICIAL_IMAGE_EXAMPLES.md")
NO_LONGER_SHARED = ("01_COMMON_RULES.md", "03_MODE_RULES.md",
                    "07_REVIEW_BEFORE_FINAL_ZIP.md", "08_PRACTICAL_TIPS.md",
                    "09_VISUAL_ART_QUALITY.md", "10_ANIME_STYLE.md",
                    "11_OFFICIAL_IMAGE_EXAMPLES.md")

@pytest.fixture(scope="module")
def published():
    result = {}
    for mode in MODES:
        for asset in ASSETS:
            zip_name = f"{mode}__{asset}"
            path = ROOT / "zips" / f"{zip_name}.zip"
            assert path.is_file(), path
            with ZipFile(path) as archive:
                assert archive.testzip() is None, path
                assert len(archive.namelist()) == len(set(archive.namelist())) == 14
                result[(mode, asset)] = {
                    name: archive.read(name).decode("utf-8")
                    for name in archive.namelist()
                }
    assert len(result) == 24
    return result


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("asset", ASSETS)
def test_every_documented_asset_has_a_scope_lock(mode, asset, published):
    docs = published[(mode, asset)]
    lock = f"ZIP 고유 작업 범위 잠금: {mode} / {asset}"
    for filename in SCOPED:
        assert lock in docs[filename], (mode, asset, filename)
    assert f"{mode}__{asset}__ARTWORK.zip" in docs["00_DELIVERY_AND_RECHECK.md"]
    assert f"{mode}__{asset}__ARTWORK.zip" in docs["04_OUTPUT_FILES.md"]
    assert ("PSD" in docs["00_READ_FIRST.md"]
            or "VRM" in docs["00_READ_FIRST.md"])  # native output is excluded
    assert "00_MASTER_FIRST.md" in docs["00_DELIVERY_AND_RECHECK.md"]
    assert "Pillow" in docs["09_VISUAL_ART_QUALITY.md"]
    assert "sample-img-tsumiki.png" in docs["11_OFFICIAL_IMAGE_EXAMPLES.md"]


@pytest.mark.parametrize("mode", MODES)
def test_drawing_and_reviews_are_genuinely_asset_specific(mode, published):
    for filename in NO_LONGER_SHARED:
        texts = [published[(mode, a)][filename] for a in ASSETS]
        assert len(set(texts)) == len(ASSETS), (mode, filename)
    for asset in ASSETS:
        docs = published[(mode, asset)]
        scope_doc = docs["03_MODE_RULES.md"]
        assert "참조" in scope_doc and "자산" in scope_doc
        assert "다른" in docs["01_COMMON_RULES.md"]
        review = docs["07_REVIEW_BEFORE_FINAL_ZIP.md"]
        assert ("재작업" in review and "재점검" in review
                if mode == "3d" else
                ("반복" in review or ("수정" in review and "다시" in review)))
        if mode == "live2d_bust_up":
            assert "실무" in docs["08_PRACTICAL_TIPS.md"]
        else:
            assert "## 비공식" in docs["08_PRACTICAL_TIPS.md"]
        if mode == "3d":
            assert "views/" in scope_doc and "turnaround_sheet.png" in scope_doc
            assert "별도로 그" in scope_doc or "실제 다른 시점" in scope_doc
            assert "신체 안에서 눈·코·입·손·발" not in scope_doc
            assert "이미지 AI" in docs["06_ADVANCED_OFFICIAL_COMMUNITY.md"]
            assert "VRM" in docs["06_ADVANCED_OFFICIAL_COMMUNITY.md"]
        else:
            assert "RGBA" in scope_doc and "layer_order.txt" in scope_doc
            assert "모드가 상반신이면 머리·목·상체와 양팔/손까지" not in scope_doc
            if mode.startswith("inochi2d_"):
                assert "docs.inochi2d.com" in docs["06_ADVANCED_OFFICIAL_COMMUNITY.md"]
                assert "Inochi" in scope_doc
            else:
                assert "Live2D" in scope_doc
        if asset != "body":
            assert "신체 안에서 눈·코·입·손·발" not in scope_doc
            assert "신체만은 불투명한 비선정적 기본 속옷을 입힌 신체 원화로 시작한다" not in docs["01_COMMON_RULES.md"]
            assert "눈이 찢어짐/홍채가 속눈썹에 붙음 →" not in docs["07_REVIEW_BEFORE_FINAL_ZIP.md"]
        if asset == "hair":
            assert any(t in docs["08_PRACTICAL_TIPS.md"] for t in ("머리카락", "모근", "가닥"))
            assert "헤어" in scope_doc
        if asset == "outfit":
            assert any(t in docs["08_PRACTICAL_TIPS.md"] for t in ("옷깃", "소매", "의상"))
            assert "의상" in scope_doc
        if asset == "accessory":
            assert "한 종류" in docs["00_MASTER_FIRST.md"] or "한 종류" in docs["03_MODE_RULES.md"]
            assert "액세서리" in scope_doc


@pytest.mark.parametrize("mode", MODES)
def test_body_only_details_are_not_required_for_other_assets(mode, published):
    for asset in ("hair", "outfit", "accessory"):
        rule = published[(mode, asset)]["03_MODE_RULES.md"]
        assert "신체 안에서 눈·코·입·손·발 등 세부 그림을 전신 그림과" not in rule
        assert "모드가 상반신이면 머리·목·상체와 양팔/손까지" not in rule
        assert "얼굴: 좌우 눈 흰자·홍채·속눈썹" not in published[(mode, asset)]["07_REVIEW_BEFORE_FINAL_ZIP.md"]


def test_bust_up_assets_do_not_demand_full_body_or_anatomy(published):
    for asset in ASSETS:
        docs = published[("live2d_bust_up", asset)]
        for name in ("00_READ_FIRST.md", "01_COMMON_RULES.md", "03_MODE_RULES.md"):
            assert "6등신 전신 배치 가이드에서 크롭" not in docs[name]
        framing = docs["03_MODE_RULES.md"]
        assert "1~2" in framing and "하체" in framing
        assert "마스크" in docs["01_COMMON_RULES.md"] or "마스킹" in docs["01_COMMON_RULES.md"]


def test_builder_templates_prioritize_master_first_and_no_cross_asset_generation():
    """A future regeneration must not reinstate pre-master part authoring or global body demands."""
    common=(ROOT / "source/COMMON.md").read_text(encoding="utf-8")
    practical=(ROOT / "source/PRACTICAL_TIPS_2D.md").read_text(encoding="utf-8")
    assert "원화가 완성된 후 마스크로 뜯어내지 않는다" not in practical
    assert "완성 기준 원화 먼저" in practical
    assert "바스트업에서는 처음부터" in common
    assert "눈 흰자·홍채·입안·귀·목·관절은 신체" in common
    assert "3D 참조도에서는" in common
    assert "다른 자산을 생성하지 않고" in practical


def test_3d_source_does_not_force_body_anatomy_into_other_assets():
    source=ROOT/"source"
    quality=(source/"QUALITY_STANDARD_3D.md").read_text(encoding="utf-8")
    anime=(source/"ANIME_VTUBER_STYLE_3D.md").read_text(encoding="utf-8")
    review=(source/"REPEAT_REVIEW_3D.md").read_text(encoding="utf-8")
    tips=(source/"PRACTICAL_TIPS_3D.md").read_text(encoding="utf-8")
    assert "**신체에만**" in quality and "**의상에만**" in quality
    assert "헤어라면" in anime and "장식이라면" in anime
    assert "신체 ZIP에서만" in anime
    assert "헤어는 머리 중심" in review
    assert "손발/골반 그림이나 인체 포즈를 강제하지 않는다" in tips


def test_bust_up_body_must_be_created_while_other_assets_do_not_redraw_it(published):
    """The body kit must not inherit the reference-only rule of detachable assets."""
    bad="자산 하나만 제작할 때는 해당 몸체를 새로 그리지 않는다"
    for asset in ASSETS:
        docs=published[("live2d_bust_up",asset)]
        for name,text in docs.items():
            assert bad not in text,(asset,name)
        master=docs["00_MASTER_FIRST.md"]
        if asset=="body":
            assert "신체 원화를 직접 새로 그린다" in master
            assert "납품 대상은 완성 신체 원화" in docs["00_DELIVERY_AND_RECHECK.md"]
        else:
            assert "제공된 기준 몸체를 새로 그리지 않고" in master
            assert "신체만이라는 이유로 PRO를 강제하지 않는다" not in docs["04_OUTPUT_FILES.md"]
