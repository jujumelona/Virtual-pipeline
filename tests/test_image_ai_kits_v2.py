"""All 20 published image-AI ZIPs must be standalone and scope-specific."""
from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
ROOT_KITS = ROOT / "docs/image_ai_kits_v2"
MODES = ("live2d_upper", "live2d_full", "inochi2d_upper", "inochi2d_full", "3d")
ASSETS = ("body", "hair", "outfit", "accessory")
ZIP_MEMBERS = {
    "00_READ_FIRST.md",
    "01_COMMON_RULES.md",
    "02_ADVANCED_PARTS.md",
    "03_MODE_RULES.md",
    "04_OUTPUT_FILES.md",
    "05_OFFICIAL_REFERENCES.md",
    "06_ADVANCED_OFFICIAL_COMMUNITY.md",
    "references/ARTWORK_FLOW.svg",
}


def test_every_one_of_twenty_zips_is_readable_with_eight_complete_documents():
    existing = sorted((ROOT_KITS / "zips").glob("*.zip"))
    assert len(existing) == 20
    for mode in MODES:
        for asset in ASSETS:
            path = ROOT_KITS / "zips" / f"{mode}__{asset}.zip"
            assert path.is_file(), path
            with ZipFile(path) as archive:
                assert archive.testzip() is None, path
                assert set(archive.namelist()) == ZIP_MEMBERS, path
                prompt = archive.read("00_READ_FIRST.md").decode("utf-8")
                details = archive.read("02_ADVANCED_PARTS.md").decode("utf-8")
                official = archive.read("05_OFFICIAL_REFERENCES.md").decode("utf-8")
                output = archive.read("04_OUTPUT_FILES.md").decode("utf-8")
                advanced = archive.read("06_ADVANCED_OFFICIAL_COMMUNITY.md").decode("utf-8")
                expected_source = ROOT_KITS / "source" / ("ADVANCED_VERIFIED_3D.md" if mode == "3d" else "ADVANCED_VERIFIED_2D.md")
                assert archive.read("06_ADVANCED_OFFICIAL_COMMUNITY.md") == expected_source.read_bytes()
                assert "## 비공식" in advanced
                assert "https://" in advanced
                assert "공식" in advanced
                assert "원화" in advanced
                assert not any(n.lower().endswith((".psd", ".moc3", ".vrm", ".glb", ".fbx")) for n in archive.namelist())
                assert prompt and details and official and output
                assert f"{mode}__{asset}__ARTWORK.zip" in output
                assert "실제" in details
                assert "https://" in official
                if asset == "body":
                    assert "눈" in details and "코" in details and "입" in details
                    assert "속옷" in details and "불투명" in details
                elif asset == "accessory":
                    assert "액세서리 세트" in details
                if mode != "3d":
                    assert "layer_order.txt" in output
                    assert "isolated_parts/" in output
                else:
                    assert "turnaround_sheet.png" in output
                    assert "VRM" in official
                assert "자동분리" in prompt or "자동" in prompt
                assert "리깅" in prompt  # mentioned ONLY as excluded from image AI tasks
                assert "06" in prompt
                assert "처음" in prompt
                assert "ZIP" in prompt
                if mode != "3d":
                    assert "RGBA" in output
                    assert "눈" in advanced and "입" in advanced
                else:
                    assert "3D" in advanced and "SpringBone" in advanced


def test_main_readme_links_to_twenty_kit_index():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    index = (ROOT_KITS / "README.md").read_text(encoding="utf-8")
    assert "docs/image_ai_kits_v2/README.md" in readme
    for mode in MODES:
        for kind in ASSETS:
            assert f"zips/{mode}__{kind}.zip" in index
