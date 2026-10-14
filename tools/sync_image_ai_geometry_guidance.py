"""Restore and audit geometry AND asset-owned artwork craft in 24 image AI ZIPs.

The source of truth is docs/image_ai_kits_v2/source/FACE_NECK_GEOMETRY_GUIDANCE.json.
--check does not change anything; --write only fills MISSING sections.
Existing asset-specific art guidance is retained. The selected 05_OFFICIAL_REFERENCES.md
is repaired as an engine-and-asset-specific canonical text when it is stale.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1] / "docs" / "image_ai_kits_v2"
SPEC = ROOT / "source" / "FACE_NECK_GEOMETRY_GUIDANCE.json"
CRAFT_SPEC = ROOT / "source" / "ADVANCED_ARTWORK_CRAFT_GUIDANCE.json"
OFFICIAL_SPEC = ROOT / "source" / "ASSET_SCOPED_OFFICIAL_REFERENCES.json"
BUSTUP_SPEC = ROOT / "source" / "BUST_UP_FACE_FIRST_CONTRACT.json"
ZIP_ROOT = ROOT / "zips"
MODES = ("live2d_bust_up", "live2d_upper", "live2d_full",
         "inochi2d_upper", "inochi2d_full", "3d")
ASSETS = ("body", "hair", "outfit", "accessory")
DOC_NAMES = (
    "00_MASTER_FIRST.md", "00_DELIVERY_AND_RECHECK.md", "00_READ_FIRST.md",
    "01_COMMON_RULES.md", "02_ADVANCED_PARTS.md", "03_MODE_RULES.md",
    "04_OUTPUT_FILES.md", "05_OFFICIAL_REFERENCES.md",
    "06_ADVANCED_OFFICIAL_COMMUNITY.md", "07_REVIEW_BEFORE_FINAL_ZIP.md",
    "08_PRACTICAL_TIPS.md", "09_VISUAL_ART_QUALITY.md",
    "10_ANIME_STYLE.md", "11_OFFICIAL_IMAGE_EXAMPLES.md",
)


def marker(mode: str, asset: str) -> str:
    return f"## [정량 추천과 옆얼굴·목 접합 개선 | {mode}/{asset}]"


def sections_for(spec: dict, mode: str, asset: str) -> dict[str, str]:
    family = "3d" if mode == "3d" else "2d"
    sections = dict(spec[family][asset])
    sections["03_MODE_RULES.md"] = spec["modes"][mode]
    if asset != "body":
        sections["03_MODE_RULES.md"] += (
            " 눈·홍채·목 피부의 실제 파츠 제작은 신체 ZIP만 담당하며"
            " 이 자산은 제공된 기준 몸체에 정렬한다."
        )
    engine = ("3d" if mode == "3d" else
              "inochi2d" if mode.startswith("inochi2d") else "live2d")
    extra = spec.get("engine_asset_06", {}).get(engine, {}).get(asset)
    if extra is not None:
        sections["06_ADVANCED_OFFICIAL_COMMUNITY.md"] = extra
    sections["06_ADVANCED_OFFICIAL_COMMUNITY.md"] += (
        "\n" + spec["engine_notes"][engine]
    )
    return sections



def craft_marker(mode: str, asset: str) -> str:
    return f"## [고급 그림자·모근·소재·선폭 | {mode}/{asset}]"


def craft_sections_for(spec: dict, mode: str, asset: str) -> dict[str, str]:
    family = "3d" if mode == "3d" else "2d"
    sections = dict(spec[family][asset])
    sections["03_MODE_RULES.md"] = spec["modes"][mode]
    engine = ("3d" if mode == "3d" else
              "inochi2d" if mode.startswith("inochi2d") else "live2d")
    extra = spec.get("engine_asset_06", {}).get(engine, {}).get(asset)
    if extra is not None:
        sections["06_ADVANCED_OFFICIAL_COMMUNITY.md"] = extra
    sections["06_ADVANCED_OFFICIAL_COMMUNITY.md"] += (
        "\n" + spec["engine_notes"][engine]
    )

    return sections




def bustup_marker(asset: str) -> str:
    return f"## [2026-10-13 FACE-FIRST 애니 바스트업 긴급 교정 | {asset}]"


def bustup_sections_for(spec: dict, asset: str) -> dict[str, str]:
    base = spec["short_scope"][asset]
    sections = {
        "00_MASTER_FIRST.md": base,
        "00_READ_FIRST.md": base,
        "03_MODE_RULES.md": base,
        "07_REVIEW_BEFORE_FINAL_ZIP.md": (
            spec["body_visual_qa"] if asset == "body" else ""
        ),
        "09_VISUAL_ART_QUALITY.md": (
            spec["body_visual_qa"] if asset == "body" else ""
        ),
        "10_ANIME_STYLE.md": (
            spec["image_prompt_body"] if asset == "body"
            else spec["image_prompt_other"][asset]
        ),
    }
    if asset == "body":
        sections["02_ADVANCED_PARTS.md"] = spec["body_face"]
    return sections


def check_bustup_legacy(archive_name: str, documents: dict[str, str]) -> None:
    import re

    forbidden = re.compile(
        r"2\.2~2\.8H|40~50%|1~2H|1~2높이|"
        r"목·어깨·상체 약 1~2|18~22%|55~70%"
    )
    offenders = [name for name, value in documents.items()
                 if forbidden.search(value)]
    if offenders:
        raise ValueError(
            f"{archive_name}: torso-heavy/weak-eyes old rules persist: "
            + ", ".join(offenders)
        )


def official_reference_text(spec: dict, mode: str, asset: str) -> str:
    """Only the selected engine and selected asset appear as actionable references."""
    engine = ("3d" if mode == "3d" else
              "inochi2d" if mode.startswith("inochi2d") else "live2d")
    if engine == "3d":
        title = f"# {mode} / {asset} — 해당 3D 참조 자산의 공식 배경"
        intro = (
            "> 00_MASTER_FIRST.md의 정면 마스터 먼저 완성 → 후면·좌우 시점 "
            "독립 원화 순서를 따른다. VRM/Blender/모델링 도구는 실행하지 않는다."
        )
    elif engine == "inochi2d":
        title = f"# {mode} / {asset} — Inochi2D 해당 자산 공식 근거"
        intro = (
            "> 00_MASTER_FIRST.md의 완성 원화 우선 계약을 따른다. "
            "Inochi Creator 실행/노드/리깅은 이 ZIP의 출력물이 아니다."
        )
    elif mode == "live2d_bust_up":
        title = f"# {mode} / {asset} — 해당 엔진·자산 공식 근거"
        intro = (
            "> 00_MASTER_FIRST.md의 원화 먼저 제작 계약을 우선한다. "
            "외부 엔진의 구현 단계는 실행하지 않는다."
        )
    else:
        title = f"# {mode} / {asset} — 해당 엔진·자산 공식 근거"
        intro = (
            "> 00_MASTER_FIRST.md의 완성 원화 우선 계약을 따른다. "
            "Cubism Editor 실행/리깅은 이 ZIP의 출력물이 아니다."
        )
    return (
        title + "\n\n" + intro + "\n\n"
        + spec["references"][engine][asset] + "\n\n"
        + spec["footer"] + "\n"
    )


def inspect_and_patch(
    zip_path: Path, spec: dict, craft_spec: dict | None = None,
    official_spec: dict | None = None, bustup_spec: dict | None = None, *, write: bool
) -> tuple[bool, list[str]]:
    mode, asset = zip_path.stem.rsplit("__", 1)
    targets = [(marker(mode, asset), sections_for(spec, mode, asset))]
    if craft_spec is not None:
        targets.append((craft_marker(mode, asset),
                        craft_sections_for(craft_spec, mode, asset)))
    if mode == "live2d_bust_up" and bustup_spec is not None:
        targets.append((bustup_marker(asset),
                        bustup_sections_for(bustup_spec, asset)))
    with zipfile.ZipFile(zip_path) as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if len(names) != 14 or set(names) != set(DOC_NAMES):
            raise ValueError(f"{zip_path.name}: unexpected 14-MD contract: {names}")
        if len(set(names)) != len(names) or archive.testzip() is not None:
            raise ValueError(f"{zip_path.name}: duplicate path or CRC failure")
        originals = {name: archive.read(name).decode("utf-8") for name in names}

    updated = originals.copy()
    missing = []
    for tag, sections in targets:
        for name, added in sections.items():
            if name not in updated:
                raise ValueError(f"{zip_path.name}: missing required {name}")
            if tag not in updated[name]:
                missing.append(f"{name} ({tag})")
                if write:
                    updated[name] += "\n\n" + tag + "\n" + added + "\n"
            elif (tag.startswith("## [고급 그림자")
                  or tag.startswith("## [2026-10-13 FACE-FIRST")) and added and added not in updated[name]:
                # Do not silently overwrite hand-edited ZIPs or append duplicate markers.
                raise ValueError(
                    f"{zip_path.name}: stale advanced-craft guidance in {name}; "
                    "manually reconcile the source and regenerate this section"
                )

    if official_spec is not None:
        expected_official = official_reference_text(official_spec, mode, asset)
        if updated["05_OFFICIAL_REFERENCES.md"] != expected_official:
            missing.append("05_OFFICIAL_REFERENCES.md (engine/asset scope)")
            if write:
                updated["05_OFFICIAL_REFERENCES.md"] = expected_official

    check_asset_scope_conflicts(zip_path.name, updated, asset)

    if mode == "live2d_bust_up":
        # Fail closed even in --write: do not mix new framing with old, torso-heavy prose.
        check_bustup_legacy(zip_path.name, updated)

    if not write or not missing:
        return False, missing

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix="geometry-", suffix=".zip", dir=zip_path.parent,
            delete=False,
        ) as tmp:
            tmp_path = Path(tmp.name)
        with zipfile.ZipFile(tmp_path, "w") as output:
            for info in infos:
                output.writestr(info, updated[info.filename].encode("utf-8"))
        with zipfile.ZipFile(tmp_path) as verify:
            if verify.testzip() is not None or verify.namelist() != names:
                raise ValueError(f"repacked ZIP integrity failure: {zip_path.name}")
        os.replace(tmp_path, zip_path)
        tmp_path = None
        return True, missing
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)


def check_asset_scope_conflicts(archive_name: str, documents: dict[str, str], asset: str) -> None:
    """Reject contradictory positive generation orders, even if a newer heading overrides them."""
    import re

    body_legacy = (
        r"중립색 기하학적 프록시|중립색 불투명 2D 도형|"
        r"불투명 중립색 도형|불투명 중립색 마네킹 프록시|"
        r"도형 프록시를 프로그램으로|몸통은 회색·베이지|"
        r"신체 도형은 완성 캐릭터 일러스트가 아니라"
    )
    other_legacy = (
        r"BODY 최종 납품|BODY 최종 ZIP|"
        r"isolated_parts/eye_L_iris\.png 같은|"
        r"독창적인 완성 원화를 처음부터 제작한다"
    )
    errors: list[str] = []
    for name, content in documents.items():
        for line_no, line in enumerate(content.splitlines(), 1):
            if asset == "body" and re.search(body_legacy, line):
                errors.append(f"{name}:{line_no}: geometric-proxy generation conflict")
            if asset != "body" and re.search(other_legacy, line):
                errors.append(f"{name}:{line_no}: foreign BODY/eye delivery or generation instruction")
    if errors:
        raise ValueError(f"{archive_name}: conflicting instructions remain: " + "; ".join(errors[:12]))


def check_builder_input_snapshots() -> None:
    """Prevent repack/build inputs from resurrecting removed proxy guidance."""
    root = ROOT / "builder_inputs"
    for family in ("2D", "3D"):
        snapshot = json.loads((root / f"{family}.json").read_text(encoding="utf-8"))
        for filename in ("COMMON.md", f"BODY_{family}.md"):
            original = (ROOT / "source" / filename).read_text(encoding="utf-8")
            if snapshot.get(filename) != original:
                raise ValueError(f"{family}.json: stale {filename} source snapshot")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true", help="read-only check (default)")
    group.add_argument("--write", action="store_true", help="append missing sections")
    args = parser.parse_args()
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    craft_spec = json.loads(CRAFT_SPEC.read_text(encoding="utf-8"))
    official_spec = json.loads(OFFICIAL_SPEC.read_text(encoding="utf-8"))
    bustup_spec = json.loads(BUSTUP_SPEC.read_text(encoding="utf-8"))
    check_builder_input_snapshots()
    found = {p.name for p in ZIP_ROOT.glob("*.zip")}
    expected = {f"{m}__{a}.zip" for m in MODES for a in ASSETS}
    if found != expected:
        raise SystemExit(f"ZIP set mismatch: missing={expected-found}, extra={found-expected}")

    missing_all: list[str] = []
    patched = 0
    for mode in MODES:
        for asset in ASSETS:
            path = ZIP_ROOT / f"{mode}__{asset}.zip"
            modified, missing = inspect_and_patch(
                path, spec, craft_spec, official_spec, bustup_spec, write=args.write
            )
            patched += int(modified)
            if missing and not args.write:
                missing_all.append(f"{path.name}: {', '.join(missing)}")

    if missing_all:
        print("\n".join(missing_all))
        return 1
    print(f"PASS: {len(expected)} image-AI ZIPs; updated {patched}; all 14 MD/CRC contracts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
