"""Resolve legacy contradictions inside the 24 *published image-AI prompts*.

Replaces obsolete requirements in their original MD paragraphs; never hides
incompatible orders under another 'higher priority' banner. Re-runnable and
lossless apart from specifically enumerated legacy wording edits.
This tool changes art-instruction ZIPs only, not the Colab execution backend.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import tempfile
from zipfile import ZipFile

from tools.apply_image_ai_multiview_briefs import (
    ROOT, MODES, ASSETS, EXPECTED,
)

# These exact phrases were found in existing published MD, not hypothetical.
ALL_REPLACEMENTS = (
    ("고정된 얼굴 초근접 구도와 단색 몸통 프록시를 금지한다.",
     "얼굴만 잘린 과도한 크롭과 단색 몸통 프록시를 금지하며 큰 얼굴·눈 중심으로 어깨·양팔·손까지 자연스럽게 그린다."),
    ("사용자가 요구한 고유 애니풍 얼굴형과 큰 눈·좌우 홍채 정합을 유지한다. 턱 뒤 목 언더페인트, 양어깨·상완·전완·양손·복부를 실제 일러스트로 그린다. 귀·입·코는 간결한 애니풍으로 유지하고 하나의 U형 턱으로 고정하지 않는다.",
     "사용자가 요구한 큰 눈·좌우 홍채와 짧고 넓은 부드러운 U형 턱의 귀여운 얼굴 인상을 유지한다. 각도별로 턱의 투영 실루엣은 자연스럽게 변화시킨다. 턱 뒤 목 언더페인트, 양어깨·상완·전완·양손·복부를 실제 애니 일러스트로 그린다."),
)

BODY_3D_REPLACEMENTS = (
    ("신체만 만든다. 의복·실사 신체 표현 없는 실제 애니풍으로 채색된 매끈한 BODY 피부 베이스를 유지한다.",
     "신체만 만든다. 디자인 의상이나 실사 골격은 제외하고 기본 불투명 스포츠 수영복을 입은 성인 애니풍 캐릭터를 유지한다."),
    ("실제 애니풍으로 채색된 매끈한 BODY 피부 베이스으로 가린 애니풍",
     "불투명 스포츠 수영복을 착용한 성인 애니풍"),
    ("안전한 실제 애니풍으로 채색된 매끈한 BODY 피부 베이스을 착용한 애니풍",
     "불투명 스포츠 수영복을 착용한 성인 애니풍"),
    ("실제 애니풍으로 채색된 매끈한 BODY 피부 베이스과 신체만",
     "실제 애니풍 피부 표현과 기본 불투명 스포츠 수영복만"),
    ("실제 애니풍으로 채색된 매끈한 BODY 피부 베이스",
     "기본 불투명 스포츠 수영복을 착용한 성인 애니풍 피부"),
    ("단순 도형 프록시 자체는 BODY에 허용하지만",
     "단순 도형 프록시는 BODY 최종 원화에 허용하지 않으며"),
)

# Different phrases that independently direct artists to create only four 3D
# views despite the agreed 8-direction + 1 occlusion-detail runtime contract.
REPLACE_3D = (
    ("전후좌우 4면도만", "실제 8방향 턴어라운드와 가림 세부 1장만"),
    ("정면·후면·좌·우 네 시점", "정면·후면·좌·우·대각을 포함한 8방향"),
    ("정면·후면·좌측·우측 신체 4면도", "정면·후면·좌측·우측 및 대각 시점 신체 8방향 턴어라운드"),
    ("정면·후면·좌측·우측 헤어 4면도", "정면·후면·좌측·우측 및 대각 시점 헤어 8방향 턴어라운드"),
    ("정면·후면·좌측·우측 의상 4면도", "정면·후면·좌측·우측 및 대각 시점 의상 8방향 턴어라운드"),
    ("정면·후면·좌측·우측 4면도", "정면·후면·좌측·우측 및 대각 시점을 모두 포함한 8방향 턴어라운드"),
    ("정·후·좌·우 4면도", "정·후·좌·우 및 대각 시점을 포함한 8방향 턴어라운드"),
    ("4면도", "8방향 턴어라운드"),
    ("네 시점", "8방향"),
    ("네 방향", "8방향"),
    ("네 장의 그림", "8방향 그림"),
    ("실제 네 장의 그림", "실제 8방향 그림"),
    ("모든 4방향", "모든 8방향"),
    ("4방향의", "8방향의"),
    ("4방향에서", "8방향에서"),
    ("4방향", "8방향"),
    ("9방향 턴어라운드", "8방향 턴어라운드+가림 세부 1장"),
)

BUSTUP_OLD_ORDER = (
    "완성된 방송용 상반신은 배 위~허리 위까지, 양쪽 어깨·상완·전완·손을 포함한다. "
    "사용자가 요청하지 않은 고정된 얼굴 초근접 구도와 회색 프록시는 금지."
)

def rewrite(text: str, *, mode: str, asset: str, name: str) -> str:
    for old, new in ALL_REPLACEMENTS:
        text = text.replace(old, new)
    if mode == "live2d_bust_up" and BUSTUP_OLD_ORDER in text:
        if asset == "body":
            new = (
                "방송용 바스트업 BODY는 큰 머리·얼굴·눈을 화면의 중심에 "
                "두고 양어깨·양팔·양손과 상복부가 모두 보이게 자연스럽게 배치한다. "
                "얼굴만 잘라낸 크롭, 팔을 수평으로 뻗어 얼굴이 작아 보이는 구도, "
                "회색 도형 프록시는 불합격."
            )
        else:
            label = {"hair": "HAIR", "outfit": "OUTFIT", "accessory": "ACCESSORY"}[asset]
            new = (
                f"방송용 바스트업의 얼굴 중심·양어깨·양팔·양손 위치는 "
                f"기존 BODY 참조에서만 확인한다. 이 ZIP은 {label} 원화만 "
                "만들며 BODY 얼굴·손·피부를 새 납품 파츠로 포함하지 않는다. "
                "프록시 도형과 부적절한 얼굴 크롭으로 자산 품질을 대신하지 않는다."
            )
        text = text.replace(BUSTUP_OLD_ORDER, new)
    if mode == "3d":
        for old, new in REPLACE_3D:
            text = text.replace(old, new)
        if asset == "body":
            for old, new in BODY_3D_REPLACEMENTS:
                text = text.replace(old, new)
        # The 8 angles and one hide/occlusion detail are NINE IMAGES,
        # not nine independent viewpoints; assert one canonical contract.
        if name == "04_OUTPUT_FILES.md":
            if "views/" not in text:
                raise ValueError("3D ZIP missing views/ folder contract")
    return text


def patch(path: Path, *, write: bool) -> bool:
    mode, asset = path.stem.rsplit("__", 1)
    if mode not in MODES or asset not in ASSETS:
        raise ValueError("Unexpected mode/asset " + path.name)
    with ZipFile(path) as archive:
        infos = archive.infolist()
        names = [x.filename for x in infos]
        if len(infos) != 14 or len(set(names)) != 14 or set(names) != set(EXPECTED):
            raise ValueError("Missing canonical 14 MD files")
        if archive.testzip() is not None:
            raise ValueError("Invalid ZIP CRC " + path.name)
        old = {name: archive.read(name).decode("utf-8") for name in names}
    new = {name: rewrite(value, mode=mode, asset=asset, name=name)
           for name, value in old.items()}
    if new == old:
        return False
    if not write:
        raise ValueError("Legacy instruction conflict in " + path.name + ": "
                         + ", ".join(name for name in names if new[name] != old[name]))
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".zip",
                                         prefix="legacy-conflict-", delete=False) as stream:
            tmp = Path(stream.name)
        with ZipFile(tmp, "w") as archive:
            for info in infos:
                archive.writestr(info, new[info.filename].encode("utf-8"))
        with ZipFile(tmp) as check:
            if check.testzip() is not None or check.namelist() != names:
                raise ValueError("Corrupt rewritten ZIP")
            if any(check.read(k).decode("utf-8") != new[k] for k in names):
                raise ValueError("Rewritten MD mismatch")
        os.replace(tmp, path)
        tmp = None
        return True
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    flags = ap.add_mutually_exclusive_group(required=True)
    flags.add_argument("--write", action="store_true")
    flags.add_argument("--check", action="store_true")
    args = ap.parse_args()
    changed = []
    for mode in MODES:
        for asset in ASSETS:
            name = f"{mode}__{asset}.zip"
            if patch(ROOT / name, write=args.write):
                changed.append(name)
    print(f"PASS: reviewed all 24 × 14 MD; remaining normalized conflicts=0; "
          f"changed={len(changed)} {', '.join(changed[:24])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
