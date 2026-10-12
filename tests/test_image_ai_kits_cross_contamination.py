"""Check all 24 released image-AI briefs for cross-asset/cross-mode instructions.

These tests check written drawing contracts and real ZIP integrity. They do
NOT assess artistic quality, model inference, or Cubism/Inochi/VRM rigging.
"""
from pathlib import Path
from zipfile import ZipFile

import pytest

ROOT = Path(__file__).resolve().parents[1] / "docs/image_ai_kits_v2"
ASSETS = ("body", "hair", "outfit", "accessory")
MODES = ("live2d_bust_up", "live2d_upper", "live2d_full",
         "inochi2d_upper", "inochi2d_full", "3d")
EXPECTED = {f"{mode}__{asset}.zip" for mode in MODES for asset in ASSETS}
REQUIRED = {
    "00_MASTER_FIRST.md", "00_DELIVERY_AND_RECHECK.md", "00_READ_FIRST.md",
    "01_COMMON_RULES.md", "02_ADVANCED_PARTS.md", "03_MODE_RULES.md",
    "04_OUTPUT_FILES.md", "05_OFFICIAL_REFERENCES.md",
    "06_ADVANCED_OFFICIAL_COMMUNITY.md", "07_REVIEW_BEFORE_FINAL_ZIP.md",
    "08_PRACTICAL_TIPS.md", "09_VISUAL_ART_QUALITY.md",
    "10_ANIME_STYLE.md", "11_OFFICIAL_IMAGE_EXAMPLES.md",
}
LEGACY_CONTRADICTIONS = (
    "2D 원본 분리/3D 참조 확장",
    "원화가 완성된 후 마스크로 뜯어내지 않는다",
    "자산 하나만 제작할 때는 해당 몸체를 새로 그리지 않는다",
)


@pytest.fixture(scope="module")
def published():
    files = sorted((ROOT / "zips").glob("*.zip"))
    assert {f.name for f in files} == EXPECTED
    out = {}
    for filename in files:
        with ZipFile(filename) as z:
            names = z.namelist()
            assert len(names) == len(set(names)) == 14
            assert set(names) == REQUIRED
            assert z.testzip() is None
            assert all(".." not in Path(x).parts and not x.startswith("/") for x in names)
            out[filename.stem] = {name: z.read(name).decode("utf-8") for name in names}
    return out


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("asset", ASSETS)
def test_all_documents_exclude_old_workflow_and_cross_mode_steps(published, mode, asset):
    docs = published[f"{mode}__{asset}"]
    for docname, document in docs.items():
        assert document.strip(), (mode, asset, docname)
        for old in LEGACY_CONTRADICTIONS:
            assert old not in document, (mode, asset, docname, old)
    assert f"{mode}__{asset}__ARTWORK.zip" in docs["04_OUTPUT_FILES.md"]
    assert f"ZIP 고유 작업 범위 잠금: {mode} / {asset}" in docs["00_MASTER_FIRST.md"]
    output = docs["04_OUTPUT_FILES.md"]
    if mode == "3d":
        assert f"views/{asset}_front.png" in output
        assert "previews/turnaround_sheet.png" in output
        assert "layer_order.txt" not in output
    else:
        assert "layer_order.txt" in output
        assert "isolated_parts/" in output


@pytest.mark.parametrize("mode", MODES)
def test_non_body_packages_do_not_request_body_only_part_files(published, mode):
    for asset in ("hair", "outfit", "accessory"):
        docs = published[f"{mode}__{asset}"]
        output = docs["04_OUTPUT_FILES.md"]
        for other_body_path in (
            "isolated_parts/face_skin.png", "isolated_parts/eye_L_white.png",
            "isolated_parts/neck.png", "isolated_parts/hand_L.png",
            "reference_views/body_six_heads_guide.png",
        ):
            assert other_body_path not in output, (mode, asset, other_body_path)
        assert "신체 안에서 눈·코·입·손·발 등 세부 그림을 전신 그림과" not in docs["03_MODE_RULES.md"]


@pytest.mark.parametrize("mode", MODES)
def test_accessory_is_not_fixed_to_headpiece_or_full_accessory_set(published, mode):
    docs = published[f"{mode}__accessory"]
    output = docs["04_OUTPUT_FILES.md"]
    assert "accessory_headpiece_main.png" not in output
    assert "한 종류" in docs["00_MASTER_FIRST.md"] or "한 종류" in docs["03_MODE_RULES.md"]
    if mode not in ("3d", "live2d_bust_up"):
        assert "accessory_<requested_type>_main.png" in output
        assert "소품" in output
    if mode == "3d":
        assert "views/accessory_front.png" in output


def test_bust_up_body_is_drawn_while_other_assets_are_reference_only(published):
    body = published["live2d_bust_up__body"]
    assert "신체 원화를 직접 새로 그린다" in body["00_MASTER_FIRST.md"]
    assert "납품 대상은 완성 신체 원화" in body["00_DELIVERY_AND_RECHECK.md"]
    for asset in ("hair", "outfit", "accessory"):
        docs = published[f"live2d_bust_up__{asset}"]
        assert "제공된 기준 몸체를 새로 그리지 않고" in docs["00_MASTER_FIRST.md"]
        assert "신체만이라는 이유로 PRO를 강제하지 않는다" not in docs["04_OUTPUT_FILES.md"]
    assert "1~2" in body["03_MODE_RULES.md"]
    assert "6등신 전신 이미지나 하체 파츠를 납품 조건으로 두지 않는다" in body["00_DELIVERY_AND_RECHECK.md"]


def test_3d_bundles_have_asset_owned_multiview_instead_of_2d_parts(published):
    for asset in ASSETS:
        docs = published[f"3d__{asset}"]
        assert "정면 기준 원화 먼저 생성 → 후면·좌우 측면" in docs["02_ADVANCED_PARTS.md"]
        assert "원화·파츠·미리보기 제작에 집중" not in docs["00_MASTER_FIRST.md"]
        tips = docs["08_PRACTICAL_TIPS.md"]
        if asset == "hair":
            assert "해당 헤어의 모근 연결" in tips
        elif asset == "outfit":
            assert "해당 의상의 옷깃·소매" in tips
        elif asset == "body":
            assert "신체 원화를 직접 제작" in tips
        else:
            assert "액세서리 한 종류의 앵커" in tips


def test_rebuild_inputs_keep_source_snapshots_without_legacy_parts_first():
    import json
    for family in ("2D", "3D"):
        payload = json.loads((ROOT / "builder_inputs" / f"{family}.json").read_text(encoding="utf-8"))
        assert len(payload) == 10
        for name, text in payload.items():
            assert text == (ROOT / "source" / name).read_text(encoding="utf-8")
    practical=(ROOT/"source/PRACTICAL_TIPS_2D.md").read_text(encoding="utf-8")
    assert "원화가 완성된 후 마스크로 뜯어내지 않는다" not in practical
    assert "완성 기준 원화 먼저" in practical
