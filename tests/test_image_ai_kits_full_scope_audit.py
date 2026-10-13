"""Semantic ownership audit over all 336 member documents in 24 image-AI ZIPs.

A mention of another asset used for comparison is allowed. Imperatives that
make the AI draw another asset, or require other-engine workflows, are not.
Tests validate authored briefs and archive format; they cannot judge actual art.
"""
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
MODES = (
    "live2d_bust_up", "live2d_upper", "live2d_full",
    "inochi2d_upper", "inochi2d_full", "3d",
)
ASSETS = ("body", "hair", "outfit", "accessory")
ALL_ZIPS = {f"{m}__{a}.zip" for m in MODES for a in ASSETS}
MEMBERS = (
    "00_MASTER_FIRST.md", "00_DELIVERY_AND_RECHECK.md",
    "00_READ_FIRST.md", "01_COMMON_RULES.md", "02_ADVANCED_PARTS.md",
    "03_MODE_RULES.md", "04_OUTPUT_FILES.md", "05_OFFICIAL_REFERENCES.md",
    "06_ADVANCED_OFFICIAL_COMMUNITY.md", "07_REVIEW_BEFORE_FINAL_ZIP.md",
    "08_PRACTICAL_TIPS.md", "09_VISUAL_ART_QUALITY.md",
    "10_ANIME_STYLE.md", "11_OFFICIAL_IMAGE_EXAMPLES.md",
)


def load_sync():
    location = REPO / "tools" / "sync_image_ai_geometry_guidance.py"
    spec = importlib.util.spec_from_file_location("image_ai_kit_scope_sync", location)
    assert spec is not None and spec.loader is not None
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def kits():
    output = {}
    files = sorted((KITS / "zips").glob("*.zip"))
    assert {p.name for p in files} == ALL_ZIPS
    for path in files:
        with ZipFile(path) as z:
            assert len(z.namelist()) == len(set(z.namelist())) == 14
            assert set(z.namelist()) == set(MEMBERS)
            assert z.testzip() is None, path.name
            output[path.stem] = {
                member: z.read(member).decode("utf-8") for member in MEMBERS
            }
    assert len(output) == 24
    return output


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("asset", ASSETS)
def test_official_references_are_exactly_own_engine_and_own_asset(kits, mode, asset):
    m = load_sync()
    spec = json.loads(m.OFFICIAL_SPEC.read_text(encoding="utf-8"))
    refs = kits[f"{mode}__{asset}"]["05_OFFICIAL_REFERENCES.md"]
    assert refs == m.official_reference_text(spec, mode, asset)
    assert f"{mode} / {asset}" in refs
    assert "00_MASTER_FIRST.md" in refs
    if mode == "3d":
        assert "vrm.dev" in refs
        assert "docs.live2d.com" not in refs
        assert "docs.inochi2d.com" not in refs
    elif mode.startswith("inochi2d"):
        assert "docs.inochi2d.com" in refs
        assert "docs.live2d.com" not in refs
        assert "vrm.dev" not in refs
    else:
        assert "docs.live2d.com" in refs
        assert "docs.inochi2d.com" not in refs
        assert "vrm.dev" not in refs


@pytest.mark.parametrize("mode", ("inochi2d_upper", "inochi2d_full"))
@pytest.mark.parametrize("asset", ASSETS)
def test_inochi_expert_guide_does_not_inherit_cubism_steps_or_irrelevant_tips(kits, mode, asset):
    guide = kits[f"{mode}__{asset}"]["06_ADVANCED_OFFICIAL_COMMUNITY.md"]
    assert "docs.inochi2d.com" in guide
    assert "docs.live2d.com" not in guide
    assert "ArtMesh" not in guide
    assert "reddit.com/r/Live2D" not in guide
    assert "Live2D 공식 링크" not in guide
    if asset in ("outfit", "accessory"):
        assert "캐릭터 얼굴 비율의 스타일별 조정" not in guide
        assert "헤어 덩어리 작화" not in guide
    if asset == "outfit":
        assert "의상 작가 실무" in guide
    elif asset == "accessory":
        assert "소품 작가 실무" in guide
    elif asset == "hair":
        assert "모근" in guide
    else:
        assert "눈" in guide and "목 피부" in guide


@pytest.mark.parametrize("mode", ("live2d_upper", "inochi2d_upper"))
def test_upper_body_is_created_directly_and_full_body_guide_is_not_required(kits, mode):
    docs = kits[f"{mode}__body"]
    assert "상반신도 동일한 전신 6등신 가이드에서 크롭" not in docs["00_MASTER_FIRST.md"]
    assert "상반신 자산도 같은 6등신 전신 배치 가이드에서 크롭" not in docs["02_ADVANCED_PARTS.md"]
    assert "상반신 원화를 직접 완성" in docs["00_MASTER_FIRST.md"]
    assert "reference_views/upper_body_proportion_guide.png" in docs["04_OUTPUT_FILES.md"]
    assert "reference_views/body_six_heads_guide.png" not in docs["04_OUTPUT_FILES.md"]
    assert "전신 이미지를 새로 그리지 않는다" in docs["04_OUTPUT_FILES.md"]


@pytest.mark.parametrize("mode", ("live2d_full", "inochi2d_full", "3d"))
def test_full_body_does_not_inherit_upper_crop_instructions(kits, mode):
    docs = kits[f"{mode}__body"]
    assert "상반신도 동일한 전신 6등신 가이드에서 크롭" not in docs["00_MASTER_FIRST.md"]
    if mode != "3d":
        assert "상반신 자산도 같은 6등신 전신 배치 가이드에서 크롭" not in docs["02_ADVANCED_PARTS.md"]
        assert "상반신 결과에서도 참고 가이드는 전신" not in docs["04_OUTPUT_FILES.md"]
    assert "6등신" in docs["00_MASTER_FIRST.md"]


@pytest.mark.parametrize("asset", ("hair", "outfit", "accessory"))
def test_bust_up_nonbody_never_requires_editing_skin_or_framing(kits, asset):
    docs = kits[f"live2d_bust_up__{asset}"]
    master = docs["00_MASTER_FIRST.md"]
    mode = docs["03_MODE_RULES.md"]
    assert "머리 높이를 H라 하면 가시적인 목·어깨·상체를 대략" not in master
    assert "기존 기준 신체의 불투명 의복·마스크 상태는 변경하지 않고" in master
    assert "중요 부위를 불투명 의복/속옷 또는 불투명 마스크로 가리고" not in docs["01_COMMON_RULES.md"]
    assert "기준 신체의 기존 1~2H 바스트업 구도는 좌표 참조에만 사용" in mode
    assert "머리 한 높이 H에 비해 화면에 보이는 목·어깨·상체를 약 1~2H 범위에서 디자인한다" not in mode
    assert "이 ZIP에서 머리·몸체 비율을 설계하거나 다시 그리지 않는다" in master
    assert "이 자산에서 피부·속옷·가림용 의복을 새로 생성하지 않는다" in docs["01_COMMON_RULES.md"]


@pytest.mark.parametrize("mode", ("live2d_upper", "live2d_full", "inochi2d_upper", "inochi2d_full", "3d"))
@pytest.mark.parametrize("asset", ("hair", "outfit", "accessory"))
def test_nonbody_scope_excludes_anatomy_creation(kits, mode, asset):
    docs = kits[f"{mode}__{asset}"]
    output = docs["04_OUTPUT_FILES.md"]
    scope = docs["03_MODE_RULES.md"]
    for basename in ("face_skin.png", "eye_L_white.png", "hand_L.png", "body_six_heads_guide.png"):
        assert basename not in output, (mode, asset, basename)
    if mode == "3d":
        assert "눈·코·입·손·옷/헤어/장식 세부 확대 그림을 각각 직접 그리는" not in docs["05_OFFICIAL_REFERENCES.md"]
        assert "3D용은 실제 다른 네 방향의 " + asset + " 참조 그림만 생성" in scope
        assert "신체만 6H 디자인을 적용하고 눈·귀·코·목의 전후좌우 형태를 일치시킨다" not in scope
    elif mode == "live2d_upper":
        assert f"**{asset} 자산 원화만 처음부터 제작**" in scope
    elif mode == "inochi2d_upper":
        assert f"**{asset} 원화만 직접 새로 제작**" in scope
    elif mode == "live2d_full":
        assert f"이 {asset} ZIP에서 새로 그리지 않는다" in scope
    elif mode == "inochi2d_full":
        assert f"이 {asset} ZIP에서 새 신체를 그리지 않는다" in scope


def test_regeneration_sources_do_not_restore_deprecated_instructions():
    source = KITS / "source"
    mode2 = (source / "MODE_2D.md").read_text(encoding="utf-8")
    body2 = (source / "BODY_2D.md").read_text(encoding="utf-8")
    advanced2 = (source / "ADVANCED_VERIFIED_2D.md").read_text(encoding="utf-8")
    mode3 = (source / "MODE_3D.md").read_text(encoding="utf-8")
    advanced3 = (source / "ADVANCED_VERIFIED_3D.md").read_text(encoding="utf-8")
    assert "모드가 상반신이면 머리·목·상체와 양팔/손까지" not in mode2
    assert "전신 그림을 새로 그리지 않은 채 상반신 원화를 처음부터 제작" in body2
    assert "처음부터 독립 파츠로 그리는 것만" not in advanced2
    assert "생성 첫 단계부터 분리" not in advanced2
    assert "마스터를 잘라내기" not in advanced2
    assert "신체 ZIP에서만" in mode3 and "신체 ZIP에서만" in advanced3
    assert "동일 캐릭터, 같은 키·몸 비례·헤어볼륨·의상 재질·소품 위치" not in advanced3
    for fname in ("OFFICIAL_2D.md", "OFFICIAL_3D.md"):
        txt = (source / fname).read_text(encoding="utf-8")
        assert "ASSET_SCOPED_OFFICIAL_REFERENCES.json" in txt
    for suffix in ("2D", "3D"):
        b = json.loads((KITS / "builder_inputs" / f"{suffix}.json").read_text(encoding="utf-8"))
        assert len(b) == 10
        for name, paragraph in b.items():
            assert paragraph == (source / name).read_text(encoding="utf-8")


def test_synchronizer_read_only_catches_all_24_zip_scope_regressions():
    proc = subprocess.run(
        [sys.executable, str(REPO / "tools" / "sync_image_ai_geometry_guidance.py"), "--check"],
        cwd=REPO, text=True, capture_output=True, timeout=45, check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "PASS: 24 image-AI ZIPs" in proc.stdout


def test_rebuild_can_repair_stale_official_reference_without_touching_art(tmp_path):
    m = load_sync()
    source = KITS / "zips" / "inochi2d_upper__hair.zip"
    target = tmp_path / source.name
    with ZipFile(source) as z, ZipFile(target, "w") as out:
        for member in z.infolist():
            content = z.read(member.filename)
            if member.filename == "05_OFFICIAL_REFERENCES.md":
                content = b"# stale cross-engine guide\n"
            out.writestr(member, content)
    geom = json.loads(m.SPEC.read_text(encoding="utf-8"))
    craft = json.loads(m.CRAFT_SPEC.read_text(encoding="utf-8"))
    refs = json.loads(m.OFFICIAL_SPEC.read_text(encoding="utf-8"))
    did_edit, missing = m.inspect_and_patch(target, geom, craft, refs, write=True)
    assert did_edit and any("05_OFFICIAL_REFERENCES.md" in x for x in missing)
    with ZipFile(source) as original, ZipFile(target) as fixed:
        assert fixed.testzip() is None
        assert fixed.namelist() == original.namelist()
        for name in fixed.namelist():
            assert fixed.read(name) == original.read(name)
    changed_again, missing_again = m.inspect_and_patch(target, geom, craft, refs, write=True)
    assert not changed_again and not missing_again
