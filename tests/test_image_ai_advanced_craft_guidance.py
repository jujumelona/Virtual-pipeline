"""24-ZIP regression for advanced, asset-owned anime craft."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile

import pytest

REPO = Path(__file__).resolve().parents[1]
KITS = REPO / "docs" / "image_ai_kits_v2"
SPEC = json.loads((KITS / "source" / "ADVANCED_ARTWORK_CRAFT_GUIDANCE.json").read_text(encoding="utf-8"))
MODES = ("live2d_bust_up", "live2d_upper", "live2d_full", "inochi2d_upper", "inochi2d_full", "3d")
ASSETS = ("body", "hair", "outfit", "accessory")
FILES = ("02_ADVANCED_PARTS.md", "03_MODE_RULES.md", "06_ADVANCED_OFFICIAL_COMMUNITY.md",
         "07_REVIEW_BEFORE_FINAL_ZIP.md", "08_PRACTICAL_TIPS.md", "09_VISUAL_ART_QUALITY.md", "10_ANIME_STYLE.md")


def guidance(mode, asset):
    entries = dict(SPEC["3d" if mode == "3d" else "2d"][asset])
    entries["03_MODE_RULES.md"] = SPEC["modes"][mode]
    engine = "3d" if mode == "3d" else ("inochi2d" if mode.startswith("inochi2d") else "live2d")
    entries["06_ADVANCED_OFFICIAL_COMMUNITY.md"] += "\n" + SPEC["engine_notes"][engine]
    if engine == "inochi2d":
        entries["06_ADVANCED_OFFICIAL_COMMUNITY.md"] += (
            "\nLive2D 공식 링크는 그림을 부위별로 보완하는 참고일 뿐 "
            "Cubism의 편집/리깅 절차를 Inochi Creator에서 수행하라는 지시가 아니다."
        )
    return entries


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("asset", ASSETS)
def test_each_zip_contains_correct_seven_craft_sections(mode, asset):
    path = KITS / "zips" / f"{mode}__{asset}.zip"
    marker = f"## [고급 그림자·모근·소재·선폭 | {mode}/{asset}]"
    with ZipFile(path) as z:
        assert len(z.namelist()) == len(set(z.namelist())) == 14
        assert z.testzip() is None
        docs = {key: z.read(key).decode("utf-8") for key in z.namelist()}
    expected = guidance(mode, asset)
    assert set(expected) == set(FILES)
    for name, paragraph in expected.items():
        assert docs[name].count(marker) == 1, (mode, asset, name)
        assert paragraph in docs[name].split(marker, 1)[1], (mode, asset, name)


def test_shadow_ownership_stays_in_its_intended_asset():
    body = SPEC["2d"]["body"]["02_ADVANCED_PARTS.md"]
    hair = SPEC["2d"]["hair"]["02_ADVANCED_PARTS.md"]
    outfit = SPEC["2d"]["outfit"]["02_ADVANCED_PARTS.md"]
    accessory = SPEC["2d"]["accessory"]["02_ADVANCED_PARTS.md"]
    assert "헤어가 얼굴에 드리우는 그림자를 신체 기본 피부에 영구적으로" in body
    assert "헤어 소유의 선택적 별도 투명 그림자" in hair
    assert "피부의 자체 그림자는 신체, 옷감 주름/접촉 그림자는 의상" in outfit
    assert "체인·끈·매달린 리본" in accessory
    assert "기존 디자인을 유지" in accessory
    for asset in ("hair", "outfit", "accessory"):
        assert "E/F=" not in SPEC["2d"][asset]["02_ADVANCED_PARTS.md"]
        assert "홍채 폭/E" not in SPEC["2d"][asset]["02_ADVANCED_PARTS.md"]


def test_3d_artwork_does_not_request_2d_shadows_or_native_rigging():
    for asset in ASSETS:
        sections = guidance("3d", asset)
        assert "전후좌우" in sections["03_MODE_RULES.md"]
        assert "2D PNG 레이어·PSD 마스크·Multiply 설정을 요구하지 않고" in sections["03_MODE_RULES.md"]
        assert "REFERENCE ONLY" in sections["10_ANIME_STYLE.md"]
        assert "VRM" in sections["06_ADVANCED_OFFICIAL_COMMUNITY.md"]


def test_specialty_source_documents_and_10_entry_snapshots_match():
    for suffix in ("2D", "3D"):
        data = json.loads((KITS / "builder_inputs" / f"{suffix}.json").read_text(encoding="utf-8"))
        assert len(data) == 10
        for asset in ASSETS:
            name = f"{asset.upper()}_{suffix}.md"
            original = (KITS / "source" / name).read_text(encoding="utf-8")
            assert original == data[name]
            assert "2026-10-13" in original
            assert "그림자" in original


def test_combined_guidance_synchronizer_is_read_only_and_passes():
    proc = subprocess.run(
        [sys.executable, str(REPO / "tools" / "sync_image_ai_geometry_guidance.py"), "--check"],
        cwd=REPO, capture_output=True, text=True, timeout=45, check=False
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "PASS: 24 image-AI ZIPs" in proc.stdout


def test_write_restores_only_missing_craft_and_is_idempotent(tmp_path):
    p = REPO / "tools" / "sync_image_ai_geometry_guidance.py"
    spec = importlib.util.spec_from_file_location("image_ai_art_sync", p)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = KITS / "zips" / "live2d_upper__outfit.zip"
    target = tmp_path / source.name
    marker = module.craft_marker("live2d_upper", "outfit")
    with ZipFile(source) as z, ZipFile(target, "w") as out:
        for info in z.infolist():
            contents = z.read(info.filename)
            if info.filename == "09_VISUAL_ART_QUALITY.md":
                raw = contents.decode("utf-8")
                assert raw.count(marker) == 1
                contents = (raw.rsplit("\n\n" + marker, 1)[0] + "\n").encode("utf-8")
            out.writestr(info, contents)
    geometry = json.loads(module.SPEC.read_text(encoding="utf-8"))
    craft = json.loads(module.CRAFT_SPEC.read_text(encoding="utf-8"))
    changed, missing = module.inspect_and_patch(target, geometry, craft, write=True)
    assert changed and any("09_VISUAL_ART_QUALITY.md" in s for s in missing)
    with ZipFile(target) as z:
        assert z.testzip() is None
        result = z.read("09_VISUAL_ART_QUALITY.md").decode("utf-8")
    assert result.count(marker) == 1
    assert craft["2d"]["outfit"]["09_VISUAL_ART_QUALITY.md"] in result
    after = target.read_bytes()
    changed, missing = module.inspect_and_patch(target, geometry, craft, write=True)
    assert not changed and not missing
    assert target.read_bytes() == after
