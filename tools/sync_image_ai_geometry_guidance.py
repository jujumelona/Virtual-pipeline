"""Restore and audit geometry AND asset-owned artwork craft in 24 image AI ZIPs.

The source of truth is docs/image_ai_kits_v2/source/FACE_NECK_GEOMETRY_GUIDANCE.json.
--check does not change anything; --write only fills MISSING sections.
Existing asset-specific art instructions are never overwritten or removed.
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
    sections["06_ADVANCED_OFFICIAL_COMMUNITY.md"] += (
        "\n" + spec["engine_notes"][engine]
    )
    if engine == "inochi2d":
        sections["06_ADVANCED_OFFICIAL_COMMUNITY.md"] += (
            "\nLive2D 공식 링크는 그림을 부위별로 보완하는 참고일 뿐 "
            "Cubism의 편집/리깅 절차를 Inochi Creator에서 수행하라는 지시가 아니다."
        )
    return sections


def inspect_and_patch(
    zip_path: Path, spec: dict, craft_spec: dict | None = None, *, write: bool
) -> tuple[bool, list[str]]:
    mode, asset = zip_path.stem.rsplit("__", 1)
    targets = [(marker(mode, asset), sections_for(spec, mode, asset))]
    if craft_spec is not None:
        targets.append((craft_marker(mode, asset),
                        craft_sections_for(craft_spec, mode, asset)))
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
            elif tag.startswith("## [고급 그림자") and added not in updated[name]:
                # Do not silently overwrite hand-edited ZIPs or append duplicate markers.
                raise ValueError(
                    f"{zip_path.name}: stale advanced-craft guidance in {name}; "
                    "manually reconcile the source and regenerate this section"
                )

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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true", help="read-only check (default)")
    group.add_argument("--write", action="store_true", help="append missing sections")
    args = parser.parse_args()
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    craft_spec = json.loads(CRAFT_SPEC.read_text(encoding="utf-8"))
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
                path, spec, craft_spec, write=args.write
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
