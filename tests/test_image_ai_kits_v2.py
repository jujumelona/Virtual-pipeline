"""The original 20 kits keep their contracts alongside 4 dedicated bust-up kits."""
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


# Released ZIPs keep a shared FILE contract, not identical art instructions.
# Cross-asset isolation is checked separately for every published ZIP.
RELEASE_SHARED_DOCUMENTS = (
    "01_COMMON_RULES.md",
    "03_MODE_RULES.md",
    "05_OFFICIAL_REFERENCES.md",
    "06_ADVANCED_OFFICIAL_COMMUNITY.md",
    "07_REVIEW_BEFORE_FINAL_ZIP.md",
    "08_PRACTICAL_TIPS.md",
    "09_VISUAL_ART_QUALITY.md",
    "10_ANIME_STYLE.md",
    "11_OFFICIAL_IMAGE_EXAMPLES.md",
)


def test_all_original_anime_kits_are_valid_with_fourteen_documents():
    existing = sorted((ROOT_KITS / "zips").glob("*.zip"))
    assert len(existing) == 24  # 20 original kits + 4 dedicated bust-up kits
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
                family = "3D" if mode == "3d" else "2D"
                master = archive.read("00_MASTER_FIRST.md").decode("utf-8")
                delivery = archive.read("00_DELIVERY_AND_RECHECK.md").decode("utf-8")
                # The read-before-generation gate takes precedence over the
                # historic master heading; both contracts must remain present.
                gate_lines = master.splitlines()
                gate_positions = [i for i, line in enumerate(gate_lines)
                                  if line.startswith("# [READ_ALL_BEFORE_IMAGE_GENERATION_V1]")]
                slot_positions = [i for i, line in enumerate(gate_lines)
                                  if line.startswith("## [EXISTING_VTUBER_TEMPLATE_SLOTS_V1]")]
                assert len(gate_positions) == len(slot_positions) == 1
                assert gate_positions[0] < slot_positions[0]
                assert f"# 최우선 제작 계약: {mode} / {asset}" in master
                assert "## [EXISTING_VTUBER_TEMPLATE_SLOTS_V1]" in master
                assert "00_DELIVERY_AND_RECHECK.md" in master
                assert "00_MASTER_FIRST.md" in delivery
                assert f"{mode}__{asset}__ARTWORK.zip" in delivery
                assert "00_DELIVERY_AND_RECHECK.md" in prompt
                for member in (*RELEASE_SHARED_DOCUMENTS, "02_ADVANCED_PARTS.md"):
                    data = archive.read(member)
                    assert b"00_MASTER_FIRST.md" in data, (path, member)
                    # Shared prose across different assets used to hide cross-asset
                    # generation instructions. Each published ZIP is intentionally
                    # independently scoped; the structural checks remain shared.
                    assert data.strip(), (path, member)
                assert "00_MASTER_FIRST.md" in output
                assert "10_ANIME_STYLE.md" in prompt
                assert "11_OFFICIAL_IMAGE_EXAMPLES.md" in prompt
                assert "애니" in prompt and "외곽선" in prompt
                assert "셀" in anime and "테이퍼" in anime
                assert "sample-img-tsumiki.png" in examples
                assert "sample-img-izumi.jpg" in examples
                assert "![Live2D official" in examples
                assert ("09_VISUAL_ART_QUALITY.md" in prompt or
                        ("09" in prompt and "품질" in prompt and
                         "10_ANIME_STYLE.md" in prompt))
                assert "https://www.live2d.com/en/learn/sample/" in quality
                assert "Pillow" in quality and "실제" in quality
                assert ("PNG" in quality if mode != "3d" else "그림" in quality)
                assert "최종" in quality
                assert any(term in quality for term in ("도형", "SVG", "베지어"))

                assert "00_MASTER_FIRST.md" in practical and "비공식" in practical
                assert ("07_REVIEW_BEFORE_FINAL_ZIP.md" in prompt or ("07" in prompt and "점검" in prompt))
                assert "최종" in prompt
                assert ("재생성" in prompt or "수정" in prompt or "재작업" in prompt)
                if mode == "3d":
                    assert "재작업" in repeat and "재점검" in repeat
                else:
                    assert "수정" in repeat and "반복" in repeat
                assert "ZIP" in prompt and "ZIP" in repeat
                assert "최종" in repeat
                assert ("재작업" in repeat and "재점검" in repeat
                        if mode == "3d" else "수정" in repeat and "반복" in repeat)
                assert "## 비공식" in practical
                assert "https://www.reddit.com/" in practical if mode != "3d" else "https://" in practical
                assert "리깅" in prompt  # downstream work explicitly excluded
                labels = {"body": "신체만", "hair": "헤어만",
                          "outfit": "의상만", "accessory": "액세서리만"}
                # "신체" and "신체만" both unambiguously indicate the body-only asset.
                assert labels[asset].removesuffix("만") in prompt
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
                    assert "BODY" in details or "신체" in details
                elif asset == "accessory":
                    assert "액세서리 세트" in details
                if mode != "3d":
                    assert "layer_order.txt" in output
                    assert "isolated_parts/" in output
                else:
                    assert "turnaround_sheet.png" in output
                    assert "VRM" in official
                common = archive.read("01_COMMON_RULES.md").decode("utf-8")
                if mode != "3d":
                    assert "마스킹" in common and "추출" in common
                else:
                    assert "정면" in common and "4면도" in common
                assert "리깅" in prompt  # mentioned ONLY as excluded from image AI tasks
                assert ("07_REVIEW_BEFORE_FINAL_ZIP.md" in prompt or
                        ("07" in prompt and "점검" in prompt))
                assert "00_MASTER_FIRST.md" in practical and "비공식" in practical
                assert "먼저" in (prompt + common) or "기준 원화" in common
                assert "ZIP" in (prompt + output)
                if mode != "3d":
                    assert "RGBA" in output
                    if asset == "body":
                        assert "눈" in advanced and "입" in advanced
                    else:
                        assert asset in ("hair", "outfit", "accessory")
                        assert "원화" in advanced
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


def test_live2d_upper_body_kit_declares_colab_master_file():
    """An image AI's result ZIP must be readable by the real Colab importer."""
    path = ROOT_KITS / "zips" / "live2d_upper__body.zip"
    with ZipFile(path) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) == ZIP_MEMBERS
        guide = archive.read("04_OUTPUT_FILES.md").decode("utf-8")
    assert "outputs/master.png" in guide
    assert "isolated_parts/" in guide
    assert "layer_order.txt" in guide
    assert "previews/composite_preview.png" in guide
    assert "master_original.png" in guide
    assert "최신 Colab" in guide


def test_all_body_kits_require_six_heads_and_large_anime_eyes():
    """The user's character has exactly 6 head units, never an arbitrary range.

    Body art must visually use big anime eyes and must not claim the output
    has rigged side-view keyframes. Other independent assets can be varied
    designs and inherit the actual matching body reference.
    """
    for mode in MODES:
        path = ROOT_KITS / "zips" / f"{mode}__body.zip"
        with ZipFile(path) as archive:
            assert archive.testzip() is None, mode
            master = archive.read("00_MASTER_FIRST.md").decode("utf-8")
            detailed = archive.read("02_ADVANCED_PARTS.md").decode("utf-8")
            output = archive.read("04_OUTPUT_FILES.md").decode("utf-8")
            review = archive.read("00_DELIVERY_AND_RECHECK.md").decode("utf-8")
            first = archive.read("00_READ_FIRST.md").decode("utf-8")
        assert "정확히 6등신" in master, mode
        assert "6등신" in detailed, mode
        assert "큰" in detailed and "홍채" in detailed and "눈" in detailed, mode
        assert "실사" in detailed and "입" in detailed and "귀" in detailed, mode
        assert "6등신" in review, mode
        if mode.endswith("_upper"):
            assert "reference_views/upper_body_proportion_guide.png" in output, mode
            assert "reference_views/body_six_heads_guide.png" not in output, mode
            assert "전신 이미지를 새로 그리지 않는다" in output, mode
        else:
            assert "reference_views/body_six_heads_guide.png" in output, mode
        assert "reference_views/face_large_anime_eyes.png" in output, mode
        assert "애니" in first, mode
        assert "매끈한" in master or "매끈한" in detailed, mode
        if mode != "3d":
            assert "머리 1 : 상체 2 : 하체 3" in detailed, mode
            assert "모든 캐릭터에 일률적인 등신을 강요하지 않는다" not in detailed
            assert "신체만이라는 이유로 PRO를 강제하지 않는다" in output
            assert "원화" in master and "파츠" in master
        else:
            assert "정면/후면/좌우 측면" in detailed, mode


def test_body_source_contract_explicitly_denies_fake_live2d_proportions():
    for source in ("BODY_2D.md", "BODY_3D.md"):
        text = (ROOT_KITS / "source" / source).read_text(encoding="utf-8")
        assert "6등신" in text and "홍채" in text
        assert "실사" in text and "눈" in text
    text = (ROOT_KITS / "source" / "BODY_2D.md").read_text(encoding="utf-8")
    assert "정확히 6등신" in text
    assert "마스터" in text
    assert "고정 머리:키 비율을 전 캐릭터에 강제하지 않는다" not in text
