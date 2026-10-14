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
