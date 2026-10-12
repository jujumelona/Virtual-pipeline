"""All 20 published image-AI ZIPs must be standalone and scope-specific."""
from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
ROOT_KITS = ROOT / "docs/image_ai_kits_v2"
MODES = ("live2d_upper", "live2d_full", "inochi2d_upper", "inochi2d_full", "3d")
ASSETS = ("body", "hair", "outfit", "accessory")
ZIP_MEMBERS = {
    "00_MASTER_FIRST.md",
    "00_DELIVERY_AND_RECHECK.md",
    "00_READ_FIRST.md",
    "01_COMMON_RULES.md",
    "02_ADVANCED_PARTS.md",
    "03_MODE_RULES.md",
    "04_OUTPUT_FILES.md",
    "05_OFFICIAL_REFERENCES.md",
    "06_ADVANCED_OFFICIAL_COMMUNITY.md",
    "07_REVIEW_BEFORE_FINAL_ZIP.md",
    "08_PRACTICAL_TIPS.md",
    "09_VISUAL_ART_QUALITY.md",
    "10_ANIME_STYLE.md",
    "11_OFFICIAL_IMAGE_EXAMPLES.md",
}


def test_all_twenty_anime_kits_are_valid_with_fourteen_documents():
    existing = sorted((ROOT_KITS / "zips").glob("*.zip"))
    assert len(existing) == 20
    for mode in MODES:
        for asset in ASSETS:
            path = ROOT_KITS / "zips" / f"{mode}__{asset}.zip"
            assert path.is_file(), path
            with ZipFile(path) as archive:
                assert archive.testzip() is None, path
                assert set(archive.namelist()) == ZIP_MEMBERS, path
                # The master-first and delivery/recheck instructions are now
                # mandatory parts of every published kit, not optional extras.
                for required in ("00_MASTER_FIRST.md", "00_DELIVERY_AND_RECHECK.md"):
                    assert archive.read(required).strip(), (path, required)
                prompt = archive.read("00_READ_FIRST.md").decode("utf-8")
                details = archive.read("02_ADVANCED_PARTS.md").decode("utf-8")
                official = archive.read("05_OFFICIAL_REFERENCES.md").decode("utf-8")
                output = archive.read("04_OUTPUT_FILES.md").decode("utf-8")
                advanced = archive.read("06_ADVANCED_OFFICIAL_COMMUNITY.md").decode("utf-8")
                repeat = archive.read("07_REVIEW_BEFORE_FINAL_ZIP.md").decode("utf-8")
                practical = archive.read("08_PRACTICAL_TIPS.md").decode("utf-8")
                quality = archive.read("09_VISUAL_ART_QUALITY.md").decode("utf-8")
                anime = archive.read("10_ANIME_STYLE.md").decode("utf-8")
                examples = archive.read("11_OFFICIAL_IMAGE_EXAMPLES.md").decode("utf-8")
                assert anime == (ROOT_KITS / "source" / (
                    "ANIME_VTUBER_STYLE_3D.md" if mode == "3d"
                    else "ANIME_VTUBER_STYLE_2D.md")).read_text(encoding="utf-8")
                assert examples == (ROOT_KITS / "source" / "OFFICIAL_VISUAL_EXAMPLES.md").read_text(encoding="utf-8")
                assert "10_ANIME_STYLE.md" in prompt
                assert "11_OFFICIAL_IMAGE_EXAMPLES.md" in prompt
                assert "애니" in prompt and "외곽선" in prompt
                assert "셀" in anime and "테이퍼" in anime
                assert "sample-img-tsumiki.png" in examples
                assert "sample-img-izumi.jpg" in examples
                assert "![Live2D official" in examples
                assert quality == (ROOT_KITS / "source" / (
                    "QUALITY_STANDARD_3D.md" if mode == "3d"
                    else "QUALITY_STANDARD_2D.md")).read_text(encoding="utf-8")
                assert ("09_VISUAL_ART_QUALITY.md" in prompt or
                        ("09" in prompt and "품질" in prompt and
                         "10_ANIME_STYLE.md" in prompt))
                assert "https://www.live2d.com/en/learn/sample/" in quality
                assert "Pillow" in quality and "실제" in quality
                assert ("PNG" in quality if mode != "3d" else "그림" in quality)
                assert "최종" in quality
                assert "도형" in prompt or "SVG" in prompt or "베지어" in prompt

                assert ("08_PRACTICAL_TIPS.md" in prompt or
                        (("08" in prompt or "01~09" in prompt) and "비공식" in prompt))
                assert ("07_REVIEW_BEFORE_FINAL_ZIP.md" in prompt or ("07" in prompt and "점검" in prompt))
                assert "최종" in prompt
                assert ("재생성" in prompt or "수정" in prompt or "재작업" in prompt)
                assert "다시" in (prompt + repeat)
                assert "ZIP" in prompt and "ZIP" in repeat
                assert "최종" in repeat and "반복" in repeat
                assert "수정" in repeat
                assert "## 비공식" in practical
                assert "https://www.reddit.com/" in practical if mode != "3d" else "https://" in practical
                assert "리깅" in prompt  # downstream work explicitly excluded
                assert archive.read("07_REVIEW_BEFORE_FINAL_ZIP.md") == (
                    ROOT_KITS / "source" / ("REPEAT_REVIEW_3D.md" if mode == "3d"
                                          else "REPEAT_REVIEW_2D.md")).read_bytes()
                assert archive.read("08_PRACTICAL_TIPS.md") == (
                    ROOT_KITS / "source" / ("PRACTICAL_TIPS_3D.md" if mode == "3d"
                                          else "PRACTICAL_TIPS_2D.md")).read_bytes()

                expected_source = ROOT_KITS / "source" / ("ADVANCED_VERIFIED_3D.md" if mode == "3d" else "ADVANCED_VERIFIED_2D.md")
                assert archive.read("06_ADVANCED_OFFICIAL_COMMUNITY.md") == expected_source.read_bytes()
                # Exact per-mode/per-asset source reconciliation prevents a
                # valid but wrong kit (e.g. hair rules inside the body ZIP).
                family = "3D" if mode == "3d" else "2D"
                kind_source = ROOT_KITS / "source" / f"{asset.upper()}_{family}.md"
                mode_source = ROOT_KITS / "source" / f"MODE_{family}.md"
                official_source = ROOT_KITS / "source" / f"OFFICIAL_{family}.md"
                assert archive.read("01_COMMON_RULES.md") == (ROOT_KITS / "source" / "COMMON.md").read_bytes()
                assert archive.read("02_ADVANCED_PARTS.md") == kind_source.read_bytes()
                assert archive.read("03_MODE_RULES.md") == mode_source.read_bytes()
                assert archive.read("05_OFFICIAL_REFERENCES.md") == official_source.read_bytes()
                labels = {"body": "신체만", "hair": "헤어만",
                          "outfit": "의상만", "accessory": "액세서리만"}
                assert labels[asset] in prompt
                assert ("3D" if mode == "3d" else
                        "Inochi2D" if mode.startswith("inochi2d") else "Live2D") in prompt

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
                common = archive.read("01_COMMON_RULES.md").decode("utf-8")
                assert "자동분리" in (prompt + common) or "자동 분리" in (prompt + common)
                assert "마스크" in common
                assert "리깅" in prompt  # mentioned ONLY as excluded from image AI tasks
                assert ("07_REVIEW_BEFORE_FINAL_ZIP.md" in prompt or
                        ("07" in prompt and "점검" in prompt))
                assert ("08_PRACTICAL_TIPS.md" in prompt or
                        (("08" in prompt or "01~09" in prompt) and "비공식" in prompt))
                assert "처음" in (prompt + common)
                assert "ZIP" in (prompt + output)
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


def test_rebuild_source_snapshots_are_identical_to_sources():
    import json
    for family in ("2D", "3D"):
        bundle = json.loads((ROOT_KITS / "builder_inputs" / f"{family}.json").read_text(encoding="utf-8"))
        assert len(bundle) == 10
        for name, body in bundle.items():
            assert body == (ROOT_KITS / "source" / name).read_text(encoding="utf-8")
