"""24-ZIP regression for optional face proportions, authentic profiles and neck seams."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile

import pytest

REPO = Path(__file__).resolve().parents[1]
KIT = REPO / "docs" / "image_ai_kits_v2"
SPEC = json.loads(
    (KIT / "source" / "FACE_NECK_GEOMETRY_GUIDANCE.json").read_text(encoding="utf-8")
)
MODES = ("live2d_bust_up", "live2d_upper", "live2d_full",
         "inochi2d_upper", "inochi2d_full", "3d")
ASSETS = ("body", "hair", "outfit", "accessory")


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("asset", ASSETS)
def test_each_zip_contains_only_its_geometric_and_profile_guidance(mode, asset):
    path = KIT / "zips" / f"{mode}__{asset}.zip"
    tag = f"## [정량 추천과 옆얼굴·목 접합 개선 | {mode}/{asset}]"
    with ZipFile(path) as archive:
        assert len(archive.namelist()) == 14
        assert archive.testzip() is None
        docs = {name: archive.read(name).decode("utf-8") for name in archive.namelist()}
    required = ("03_MODE_RULES.md", "06_ADVANCED_OFFICIAL_COMMUNITY.md",
                "07_REVIEW_BEFORE_FINAL_ZIP.md", "08_PRACTICAL_TIPS.md")
    if asset == "body":
        required += ("02_ADVANCED_PARTS.md",)
    for name in required:
        assert tag in docs[name], (mode, asset, name)
    if asset == "body":
        if mode == "live2d_bust_up":
            assert "23~29%" in docs["02_ADVANCED_PARTS.md"]
            assert "62~80%" in docs["02_ADVANCED_PARTS.md"]
        else:
            assert "18~22%" in docs["02_ADVANCED_PARTS.md"]
            assert "55~70%" in docs["02_ADVANCED_PARTS.md"]
        if mode == "3d":
            assert "앞목" in docs["08_PRACTICAL_TIPS.md"]
            assert "후면" in docs["08_PRACTICAL_TIPS.md"]
        else:
            assert "입 높이" in docs["08_PRACTICAL_TIPS.md"]
        if mode == "live2d_bust_up":
            assert "1.65~1.95H" in docs["03_MODE_RULES.md"]
            assert "52~61%" in docs["03_MODE_RULES.md"]
    else:
        tail = "\n".join(
            docs[name].split(tag, 1)[1] for name in required
        )
        assert "E/F=18~22%" not in tail
        assert "홍채/E=55~70%" not in tail
        if asset == "hair":
            assert "모근" in tail or "뿌리" in tail
        elif asset == "outfit":
            assert "카라" in tail or "옷깃" in tail
        else:
            assert "부착" in tail
    if mode != "live2d_bust_up":
        reference = dict(SPEC["3d" if mode == "3d" else "2d"][asset])
        if mode.startswith("inochi2d_"):
            reference["06_ADVANCED_OFFICIAL_COMMUNITY.md"] = SPEC["engine_asset_06"]["inochi2d"][asset]
        for name, guidance in reference.items():
            assert guidance in docs[name], (mode, asset, name)


def test_every_mode_and_asset_has_single_canonical_source():
    assert set(SPEC["modes"]) == set(MODES)
    for category in ("2d", "3d"):
        assert set(SPEC[category]) == set(ASSETS)
        for asset in ASSETS:
            assert "08_PRACTICAL_TIPS.md" in SPEC[category][asset]
            if asset != "body":
                assert "02_ADVANCED_PARTS.md" not in SPEC[category][asset]
            else:
                assert "02_ADVANCED_PARTS.md" in SPEC[category][asset]


def test_read_only_zip_synchronizer_passes_without_rebuilding_artwork():
    command = [
        sys.executable,
        str(REPO / "tools" / "sync_image_ai_geometry_guidance.py"),
        "--check",
    ]
    finished = subprocess.run(
        command, cwd=REPO, capture_output=True, text=True, timeout=45, check=False
    )
    assert finished.returncode == 0, finished.stdout + finished.stderr
    assert "PASS: 24 image-AI ZIPs" in finished.stdout


def test_snapshot_keeps_asset_ownership_after_geometry_source_changes():
    for mode, suffix in (("2D", "2D"), ("3D", "3D")):
        snapshot = json.loads(
            (KIT / "builder_inputs" / f"{mode}.json").read_text(encoding="utf-8")
        )
        for asset in ASSETS:
            key = f"{asset.upper()}_{suffix}.md"
            assert snapshot[key] == (KIT / "source" / key).read_text(encoding="utf-8")
            assert "2026-10-13" in snapshot[key]
