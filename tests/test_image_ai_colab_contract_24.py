"""Verify the published 24 image-AI instruction ZIPs against Colab input code.

Catches *real producer/consumer drift*, not merely matching ZIP member counts.
Checks reference-view paths in the actual shipped binary ZIPs, plus static
asset ownership and backend routing. Source-image quality is not certified.
"""
from __future__ import annotations
import re
from pathlib import Path
from zipfile import ZipFile

import pytest

from tools.colab_mode_ui import select_mode
from tools.vts_multiview_runtime import VIEW_SETS, VIEWS_FOR_3D

ROOT = Path(__file__).resolve().parents[1]
ZIPS = ROOT / "docs" / "image_ai_kits_v2" / "zips"
MODES = ("live2d_bust_up", "live2d_upper", "live2d_full",
         "inochi2d_upper", "inochi2d_full", "3d")
ASSETS = ("body", "hair", "outfit", "accessory")
IMAGE_FILES = re.compile(r"(?:reference_views|views)/[A-Za-z0-9_]+\.png")

@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("asset", ASSETS)
def test_shipped_ai_zip_produces_exact_view_paths_colab_accepts(mode, asset):
    zip_path = ZIPS / f"{mode}__{asset}.zip"
    with ZipFile(zip_path) as archive:
        assert archive.testzip() is None
        assert len(archive.namelist()) == 14
        assert all(name.endswith(".md") for name in archive.namelist())
        instructions = archive.read("04_OUTPUT_FILES.md").decode("utf-8")
        assert "필수 참조 시점 PNG" in instructions
        assert "Colab 입력 파츠·경로 계약" in instructions
        assert "24개" not in archive.namelist()
        assert "outputs/master.png" in instructions if mode != "3d" else True
        if mode != "3d":
            assert "isolated_parts/" in instructions and "layer_order.txt" in instructions
            assert "reference_views/ — 회전 보조(필요한 경우만)" not in instructions
        else:
            assert "isolated_parts/" not in instructions
        lines = [line for line in instructions.splitlines()
                 if line.startswith("- 최소 참고 파일 후보: ")]
        assert len(lines) == 1, f"{zip_path}: missing canonical view list"
        authored = set(IMAGE_FILES.findall(lines[0]))
        if mode == "3d":
            expected = {f"views/{asset}_{direction}.png" for direction in VIEWS_FOR_3D}
            expected.add(f"views/{asset}_detail_occlusion.png")
        else:
            expected = {f"reference_views/{name}.png" for name in VIEW_SETS[asset]}
        assert authored == expected, (
            f"{zip_path.name} does not match Colab reference view filenames: "
            f"missing from image-AI directions={sorted(expected - authored)}, "
            f"not consumed by Colab={sorted(authored - expected)}"
        )
        if mode != "3d":
            assert '다각도' in instructions and 'PSD' in instructions
    selected = select_mode(mode, asset)
    assert selected.asset_kind == asset
    assert selected.family == ("3d" if mode == "3d" else
                               "inochi2d" if mode.startswith("inochi") else "live2d")
