"""Audit all 24 published AI-brief ZIPs for contradictory older instructions.

Unlike a banner-only test, this examines every line of all 336 Markdown files.
The images produced by an independent AI still need direct visual review.
"""
from pathlib import Path
from zipfile import ZipFile

import pytest

from tools.apply_image_ai_multiview_briefs import ROOT, MODES, ASSETS, EXPECTED
from tools.reconcile_image_ai_legacy_conflicts import (
    rewrite, BUSTUP_OLD_ORDER,
)

@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("asset", ASSETS)
def test_all_336_md_files_are_normalized_and_scoped(mode, asset):
    with ZipFile(ROOT / f"{mode}__{asset}.zip") as archive:
        names = archive.namelist()
        assert len(names) == 14 and set(names) == set(EXPECTED)
        assert archive.testzip() is None
        for name in names:
            content = archive.read(name).decode("utf-8")
            assert rewrite(content, mode=mode, asset=asset, name=name) == content, (
                f"{mode}/{asset}/{name} still has an old contradictory instruction")
            if mode == "3d":
                assert "4시점" not in content
                assert "4면으로" not in content
                assert "단순 캐릭터 마네킹 형태" not in content
                assert "수영복가" not in content
                assert "4면도" not in content
                assert "9방향 턴어라운드" not in content
                assert "정·후·좌·우 4면도" not in content
                assert "네 시점" not in content
                assert "4방향에서" not in content
                assert "8방향" in archive.read("00_MASTER_FIRST.md").decode("utf-8")
                assert "views/" in archive.read("04_OUTPUT_FILES.md").decode("utf-8")
            if mode == "live2d_bust_up":
                assert BUSTUP_OLD_ORDER not in content
            if mode == "3d" and asset == "body":
                assert "BODY 피부 베이스" not in content
                assert "단순 도형 프록시 자체는 BODY에 허용" not in content
            if mode != "3d" and asset == "body":
                assert "BODY 상의/터틀넥/보디슈트 금지" not in content
                assert "BODY에 터틀넥·상의 금지" not in content
                assert "신체는 애니풍 의상 장착용 마네킹" not in content
                assert "애니풍 2D 버추얼 마네킹 원화" not in content
            if mode == "live2d_bust_up" and asset == "body":
                assert "하나의 U형 턱으로 고정하지 않는다" not in content


@pytest.mark.parametrize("mode", MODES)
def test_clothed_body_and_asset_framing_do_not_conflict(mode):
    with ZipFile(ROOT / f"{mode}__body.zip") as archive:
        master = archive.read("00_MASTER_FIRST.md").decode("utf-8")
    assert master.startswith("# [READ_ALL_BEFORE_IMAGE_GENERATION_V1]")
    assert "성인(20세 이상)" in master
    assert "불투명" in master and "수영복" in master
    assert "IMAGE_AI_NATIVE_ART_FIRST_QUALITY_V1" in master
    if mode == "3d":
        assert "8방향" in master and "가림 세부" in master
        assert "9방향 턴어라운드" not in master
    else:
        assert "removable_neutral_modesty_band_upper" in master
        assert "하체가 화면에 존재" in master
        assert "빈 하의 레이어를 억지로 만들지 않는다" in master


@pytest.mark.parametrize("asset", ("hair", "outfit", "accessory"))
def test_bustup_nonbody_guides_do_not_require_repainting_body(asset):
    with ZipFile(ROOT / f"live2d_bust_up__{asset}.zip") as archive:
        mode_rules = archive.read("03_MODE_RULES.md").decode("utf-8")
    assert "이 ZIP은 " + asset.upper() in mode_rules
    assert "BODY 얼굴·손·피부를 새 납품 파츠로 포함하지 않는다" in mode_rules


def test_published_3d_mode_scope_matches_authoritative_geometry_json():
    """Avoid invisible mismatch between the named geometry section and the source spec."""
    import json
    from tools.sync_image_ai_geometry_guidance import marker
    spec = json.loads(
        (ROOT.parent / "source" / "FACE_NECK_GEOMETRY_GUIDANCE.json")
        .read_text(encoding="utf-8"))
    expected = spec["modes"]["3d"]
    for asset in ASSETS:
        with ZipFile(ROOT / f"3d__{asset}.zip") as z:
            rule = z.read("03_MODE_RULES.md").decode("utf-8")
        segment = rule.split(marker("3d", asset), 1)[1]
        if asset == "body":
            assert expected in segment, "3d/body: geometry source/ZIP drift"
        else:
            # Detached assets intentionally replace the general BODY anatomy
            # sentence with an asset-only 8-angle reference instruction.
            assert f"3D용은 실제 다른 8방향의 {asset} 참조 그림만 생성" in segment
            assert "새로 그리지 않는다" in segment
            assert expected not in segment
        assert "가림 세부 1장" in expected


def test_bustup_geometry_sections_are_not_empty_and_match_source():
    import json
    from tools.sync_image_ai_geometry_guidance import marker, sections_for
    spec = json.loads(
        (ROOT.parent / "source" / "FACE_NECK_GEOMETRY_GUIDANCE.json")
        .read_text(encoding="utf-8"))
    for asset in ASSETS:
        with ZipFile(ROOT / f"live2d_bust_up__{asset}.zip") as z:
            md = z.read("03_MODE_RULES.md").decode("utf-8")
        tag = marker("live2d_bust_up", asset)
        expected = sections_for(spec, "live2d_bust_up", asset)["03_MODE_RULES.md"]
        assert tag in md
        assert md.count(tag) == 1
        assert expected in md.split(tag, 1)[1].split("\n## [", 1)[0]
        assert "양팔" in expected and "손" in expected



@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("asset", ASSETS)
def test_semantic_wardrobe_input_paths_and_work_sequence_are_consistent(mode, asset):
    """Every one of the 336 released MDs must agree about source art, not only markers."""
    source = ROOT / f"{mode}__{asset}.zip"
    with ZipFile(source) as archive:
        documents = {name: archive.read(name).decode("utf-8") for name in archive.namelist()}
    for name, doc in documents.items():
        for forbidden in (
            "중요한 부위의 최소 가림은 별도 단색 커버 파츠만 사용한다",
            "신체만 만든다. 선정적이지 않은 실제 애니풍으로 채색된 매끈한 BODY 피부 베이스",
            "신체 베이스의 중요 부위는 안전한 실제 애니풍으로 채색된 매끈한 BODY 피부 베이스",
            "기준 BODY의 기존 애니풍 피부와 최소 가림 파츠를 그대로 유지",
            "고급 세부 그림은 확정된 정면 기준 원화의 디자인을 참조해 필요한 경우만 추가 제작한다",
            "원화 한 장을 먼저 만든 후, 실제 필요한 부분을 마스크로 추출하고 숨은 면만 보완한다",
        ):
            assert forbidden not in doc, (mode, asset, name, forbidden)
        if mode == "3d":
            assert "- 기존 MD에서 reference_views/를" not in doc, (mode, asset, name)
            assert "사용자 PSD가 없는 신규 캐릭터에서도" not in doc, (mode, asset, name)
        if asset == "body":
            assert "불투명" in documents["00_MASTER_FIRST.md"]
            assert "수영복" in documents["00_MASTER_FIRST.md"]
        if asset != "body":
            assert "BODY_DEFAULT_OPAQUE_SWIMWEAR_V1" not in doc
    master = documents["00_MASTER_FIRST.md"]
    assert "이미지 생성 AI" in master
    assert "NATIVE_ART_FIRST_QUALITY_V1" in master
    if mode == "3d":
        assert "8방향" in master and "가림 세부" in master
        assert "views/" in documents["04_OUTPUT_FILES.md"]
    else:
        assert "reference_views/" in documents["04_OUTPUT_FILES.md"]
        assert "isolated_parts/" in documents["04_OUTPUT_FILES.md"]
