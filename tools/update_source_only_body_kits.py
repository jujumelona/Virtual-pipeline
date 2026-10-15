"""Update all 20 published 2D instruction ZIPs to template-first part-by-part artwork.

The 4 three-dimensional image kits are left unchanged. Image AI draws
independent RGBA artwork; Colab performs PSD assembly/rigging.
"""
from __future__ import annotations

import argparse
import os
import re
from pathlib import Path
import tempfile
from zipfile import ZipFile

from tools.image_ai_source_only_contract import (
    BEGIN, END, source_contract, source_only_output_file,
)

ROOT = Path(__file__).resolve().parents[1] / "docs/image_ai_kits_v2/zips"
MODES = ("live2d_bust_up", "live2d_upper", "live2d_full",
         "inochi2d_upper", "inochi2d_full")
ASSETS = ("body", "hair", "outfit", "accessory")

# Phrases previously published into first-page/quality/template sections.
# They are active output instructions (NOT links or background PSD examples).
# Replace in their original location; a newer appended contract alone cannot
# resolve two simultaneously active and contradictory production orders.
OUTDATED_2D_OUTPUT = (
    (
        "완성 마스터에서 편집 가능한 다층 PSD·파츠 PNG·마스크를 만든다.",
        "완성 마스터와 실제 템플릿 슬롯에 맞춰 독립 RGBA 파츠 PNG를 하나씩 그린다. PSD·마스크는 Colab에서 만든다."
    ),
    (
        "독립 의상 파츠·가림 후면·마스크·PSD를 납품한다.",
        "독립 의상 파츠 RGBA PNG와 가림 후면을 한 장씩 제작한다. PSD·마스크는 Colab에서 제작한다."
    ),
    (
        "2D는 원화·독립 알파 PNG·마스크·레이어 순서·편집 가능한 다층 PSD, 목/턱/어깨 관절의 단색 underpaint를 남긴다.",
        "2D 이미지 AI는 템플릿 각 슬롯을 보고 마스터와 동일 좌표의 독립 RGBA 파츠 원화를 하나씩 그린다. 후속 Colab에서 마스크·다층 PSD·리깅 입력을 조립한다."
    ),
    (
        "**원화 먼저, 파츠 분리 나중.**",
        "**기준 마스터 확정 뒤 템플릿 파츠 슬롯을 하나씩 독립 작화.**"
    ),
    (
        "원화 파츠 분리·보완 → 실제 PSD·PNG·검증 기록·ZIP",
        "파츠 하나씩 독립 RGBA PNG 제작·가림 보완 → 원화 ZIP·검증 기록 (PSD는 후속 Colab)"
    ),
    (
        "독립 PSD·PNG·마스크로 제작한다.",
        "독립 RGBA 파츠 PNG를 하나씩 그린다. PSD·마스크는 후속 Colab에서 제작한다."
    ),
    (
        "개별 파츠 채색 보존 분리·PSD/ZIP 조립",
        "공식 템플릿 대응 슬롯의 파츠별 독립 RGBA 원화 제작·검수·PNG ZIP 납품"
    ),
    (
        "실제 생성한 원화에서 레이어를 분리하고 세부를 손상시키지 않는다.",
        "각 세부 파츠는 실제 템플릿 대응 슬롯을 확인한 뒤 고유한 독립 그림으로 제작한다."
    ),
    (
        "편집 가능한 PSD는 고품질 기준 원화와 파츠 분리를 마친 후에 제작한다.",
        "편집 가능한 PSD는 후속 Colab에서 독립 파츠 RGBA를 조립하여 제작한다."
    ),
    (
        "독립 RGBA 파츠는 isolated_parts/*.png, 실제 가림 순서는 layer_order.txt",
        "독립 RGBA 파츠는 part_art/*.png, 실제 앞뒤 순서는 part_art/_order.txt"
    ),
    (
        "기본 layer_order.txt에는",
        "중립 합성에는"
    ),
    (
        "isolated_parts/와 layer_order.txt에는",
        "part_art/와 part_art/_order.txt에는"
    ),
    (
        "실제 생성·PSD 파츠·PNG에는",
        "실제 생성한 독립 RGBA PNG에는"
    ),
    (
        "별도 PNG/PSD 파츠",
        "별도 독립 RGBA PNG 파츠"
    ),
)


def modernize_2d_steps(text: str) -> str:
    for old, new in OUTDATED_2D_OUTPUT:
        text = text.replace(old, new)
    return text


def update_one(path: Path, *, write: bool) -> bool:
    with ZipFile(path) as original:
        infos = original.infolist()
        names = [x.filename for x in infos]
        if len(names) != 14 or len(set(names)) != 14 or original.testzip():
            raise ValueError("2D_KIT_EXPECTS_14_VALID_MDS: " + str(path))
        old = {name: original.read(name).decode("utf-8") for name in names}
    # The 2026-10-16 files were individually inspected, reviewed, and
    # directly modified. Do not reconstruct/overwrite their native content
    # using a generic 14-MD contract replacement.
    # A separate manual edit must review *every* affected document before
    # the published binary is replaced.
    acceptance = "[VTUBER_SIDE_NECK_RIG_ACCEPTANCE_V1]"
    if any(acceptance in body for body in old.values()):
        if not all(body.count(acceptance) == 1 for body in old.values()):
            raise ValueError("MANUALLY_REVIEWED_KIT_ACCEPTANCE_INCONSISTENT: " + path.name)
        if not all(body.count(BEGIN) == 1 and body.count(END) == 1
                   for body in old.values()):
            raise ValueError("MANUALLY_REVIEWED_KIT_CONTRACT_MISSING: " + path.name)
        return False
    mode_name, asset = path.stem.split("__")
    contract = source_contract(mode_name, asset)
    updated = {}
    for name, body in old.items():
        old_start = "## [IMAGE_ART_MULTIVIEW_SOURCE_ONLY_V1]"
        old_end = "## [/IMAGE_ART_MULTIVIEW_SOURCE_ONLY_V1]"
        if body.count(old_start) != body.count(old_end) or body.count(old_start) > 1:
            raise ValueError("PARTIAL_OLD_MULTIVIEW_CONTRACT: " + path.name + "/" + name)
        if old_start in body:
            body = re.sub(re.escape(old_start) + r".*?" +
                          re.escape(old_end), "", body, flags=re.S)
        body = modernize_2d_steps(body)
        if body.count(BEGIN) != 1 or body.count(END) != 1:
            raise ValueError("SOURCE_ONLY_REFERENCE_MARKER_MISSING: " + path.name + "/" + name)
        begin = body.index(BEGIN) + len(BEGIN)
        end = body.index(END, begin)
        updated[name] = (
            source_only_output_file(mode_name, asset)
            if name == "04_OUTPUT_FILES.md"
            else body[:begin] + "\n" + contract + body[end:]
        )
    if updated == old:
        return False
    if not write:
        raise ValueError("2D_KIT_REBUILD_REQUIRED: " + path.name)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent, prefix="source-per-part-", suffix=".zip",
            delete=False,
        ) as stream:
            tmp = Path(stream.name)
        with ZipFile(tmp, "w") as written:
            for entry in infos:
                written.writestr(entry, updated[entry.filename].encode("utf-8"))
        with ZipFile(tmp) as check:
            if check.testzip() or check.namelist() != names:
                raise ValueError("2D_KIT_ARCHIVE_CHANGED_STRUCTURE: " + path.name)
        os.replace(tmp, path)
        tmp = None
        return True
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    args = parser.parse_args()
    changed = 0
    for mode_name in MODES:
        for asset in ASSETS:
            changed += int(update_one(
                ROOT / (mode_name + "__" + asset + ".zip"),
                write=args.write,
            ))
    print(f"20 two-dimensional source-art ZIPs verified; changed={changed}; "
          "four 3D ZIPs untouched")


if __name__ == "__main__":
    main()
