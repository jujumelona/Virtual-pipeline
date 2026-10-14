"""Demand an actual high-quality image-generation pass in all 24 canonical AI briefs.

These ZIPs are instructions for large image AIs, not Colab runtimes. The
rules refuse crude SVG/Pillow shape-drawing substitutes and require artwork
quality *before* PSD assembly. Static gates cannot judge the actual pixels.
"""
from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path
from zipfile import ZipFile

from tools.apply_image_ai_multiview_briefs import (
    ROOT, MODES, ASSETS, EXPECTED, COVER_MARKER, COVER_MARKER_END,
)

START = "## [IMAGE_AI_NATIVE_ART_FIRST_QUALITY_V1]"
END = "## [/IMAGE_AI_NATIVE_ART_FIRST_QUALITY_V1]"
READ_FIRST_END = "**GPT가 이 문서를 읽기 전에 이미지를 생성했다면 그 출력은 납품 실패다.**\n\n"
DOCS = frozenset((
    "00_MASTER_FIRST.md", "00_DELIVERY_AND_RECHECK.md", "00_READ_FIRST.md",
    "02_ADVANCED_PARTS.md", "04_OUTPUT_FILES.md", "07_REVIEW_BEFORE_FINAL_ZIP.md",
    "09_VISUAL_ART_QUALITY.md", "10_ANIME_STYLE.md",
))

MODALITY = {
    "live2d_bust_up": (
        "방송용 바스트업. 얼굴·눈을 화면의 주인공으로, 큰 두상과 짧고 넓은 "
        "U형 하관을 그린다. 머리·얼굴·눈이 작게 보이는 멀리서 찍은 전체 몸통 "
        "및 양팔을 수평으로 활짝 펼친 T/A 포즈는 불합격. "
        "팔꿈치·손목·손가락은 보이게 그리되 양손은 몸통 양옆·하단에 "
        "자연스럽게 배치해 캐릭터 얼굴보다 시선을 빼앗지 않게 한다. "
        "민머리 BODY 원화라도 납작한 계란 얼굴·이마만 큰 도형은 금지. "
        "헤어는 HAIR ZIP의 자산이므로 BODY 레이어에 합치지 않는다. "
        "실제 입과 눈을 중심으로 방송 축소 크기에서도 눈매·표정이 읽히게 한다."
    ),
    "live2d_upper": (
        "정수리~허리의 애니풍 상반신. 큰 얼굴/눈 중심, 짧고 넓은 얼굴과 "
        "정확히 연결된 목·어깨·자연스러운 팔과 양손을 그린다. "
        "가로로 뻗은 팔·작은 머리·길쭉한 실사 비율·납작한 밴드형 캐릭터는 거절한다."
    ),
    "live2d_full": (
        "6등신 전신 애니 원화. 큰 눈과 부드러운 얼굴·균형 잡힌 팔다리, "
        "손가락·관절·발까지 모두 고품질로 그린다. "
        "얼굴 확대 별도 이미지로 눈매 디테일을 보존하고 비례를 재검토한다."
    ),
    "inochi2d_upper": (
        "Inochi2D 상반신. 얼굴과 큰 눈 중심의 손그림 애니풍 세밀함, "
        "자연스러운 어깨·양팔·양손, 턱 뒤 목과 가림 표면을 유지한다."
    ),
    "inochi2d_full": (
        "Inochi2D 6등신 전신. 얼굴 표정·양손·발과 독립 관절의 "
        "2D 원화를 숙련된 애니 일러스트 수준으로 표현한다."
    ),
    "3d": (
        "3D 모델 생성 참고 9방향 원화. 정면/좌우 3/4/측면/후면/숨은 면을 "
        "실제로 독립 제작하고 색·재질·실루엣과 6등신을 일치시킨다. "
        "저해상 마네킹·도형·기하학 더미 모델 이미지로 대체하지 않는다. "
        "3D ZIP 자체는 PSD/2D 리깅 파일을 요구하지 않는다."
    ),
}

DETAIL = {
    "body": (
        "성인(20세 이상)의 비성적이고 귀여운 애니풍 캐릭터. "
        "불투명한 스포츠형 비키니 수영복 상의와 하이웨이스트 쇼츠 하의를 "
        "정면·측면·뒷면·합성 미리보기·마스터에서 일관되게 착용한다. "
        "고급 애니 선화의 자연스러운 굵기 변화, 정교한 세부 음영과 색 통일, "
        "깊이 있는 홍채·동공·하이라이트·흰자·속눈썹·윗아랫눈꺼풀, "
        "작은 코·하나의 정확한 입, 입안·혈색, 단순하지만 매력적인 애니 귀를 완성한다. "
        "눈·얼굴·목·손은 필요 수만큼 나누고 24개 파츠로 강제 축소하지 않는다. "
        "좌우 각각의 눈 뜸/반감김/감김 및 말하는 입/입 다묾/입 벌림의 "
        "실제 별도 애니 그림을 생성한다. 상태 이름만 다르고 눈 그림이 "
        "똑같거나 겹쳐 두 입이 보이면 불합격. "
        "눈/입을 도형 몇 개로 대신하거나 목을 단색 막대처럼 그리지 않는다. "
        "정면·좌우 3/4·좌우 프로필·상하 시점을 새로운 원화로 그려 "
        "먼 눈·코·귀·턱과 목의 깊이를 자연스럽게 바꾸고, "
        "턱/귀 뒤 숨은 목·어깨·팔 접합부를 실제 선화/채색으로 만든다. "
        "헤어/교체 의상/액세서리 파츠는 BODY 납품에 포함하지 않는다."
    ),
    "hair": (
        "HAIR 전용. 요청된 머리 스타일의 뿌리·앞머리·옆머리·뒷머리·"
        "가닥의 크기 차·겹침·광택·그림자를 실제 세밀한 애니 선화로 그린다. "
        "한 장의 투구/헬멧 같은 둥근 면과 삼각형 복제 가닥, "
        "정면의 단순 반전 측면은 불합격. 얼굴·신체·옷은 원화 파츠에 넣지 않는다."
    ),
    "outfit": (
        "OUTFIT 전용. 지정 의상의 재질/두께/봉제선/주름/안감/깃/소매와 "
        "입체 겹침을 숙련된 애니풍으로 새로 그린다. "
        "무늬 없는 직사각형·단색 윤곽 면을 의상으로 가장하지 않고 "
        "BODY 피부·눈·얼굴은 납품 파츠에 넣지 않는다."
    ),
    "accessory": (
        "ACCESSORY 전용. 지정 소품의 소재·윤곽·입체 두께·"
        "부착점·그림자·가려진 뒷면을 세련된 애니 원화로 그린다. "
        "원/사각형·SVG 선만으로 구성한 임시 표시물을 완성품으로 제출하지 않으며 "
        "신체·의상·헤어를 중복 제작하지 않는다."
    ),
}


def quality_text(mode: str, asset: str) -> str:
    mode_brief = MODALITY[mode]
    details = DETAIL[asset]
    mode_output = (
        "지정한 9방향 각각의 실제 원화 PNG·일관성 검토표를 납품한다. "
        "2D PNG 레이어·PSD·VRM이 이 단계의 납품 필수는 아니다."
        if mode == "3d"
        else (
            "완성 마스터는 outputs/master.png, 독립 RGBA 파츠는 "
            "isolated_parts/*.png, 실제 가림 순서는 layer_order.txt, "
            "고품질 다각도 원화는 reference_views/에 저장한다. "
            "실제 생성한 원화에서 레이어를 분리하고 세부를 손상시키지 않는다. "
            "편집 가능한 PSD는 고품질 기준 원화와 파츠 분리를 마친 후에 제작한다."
        )
    )
    return f"""{START}

### 실제 대형 이미지 AI 생성 → 고품질 원화 승인 → 다각도 → 분리 (최상위 품질 규칙)
- **작업 순서 강제:** 기존 14개 MD/이미지 참고 실제 열람 → 대상 자산·구도 확정 → 이미지 생성 AI 기능으로 고품질 기준 마스터 원화 직접 생성 → 마스터를 눈으로 보고 합격/재생성 결정 → 해당 캐릭터의 다각도/표정/숨은 면 실제 이미지 추가 생성 → 개별 파츠 채색 보존 분리·PSD/ZIP 조립 → 실제 완성본 시각 검증. 첫 번째 이미지 품질 통과 전에 PSD·파츠 개수 맞추기부터 하지 않는다.
- **이미지 생성 방식:** 마스터와 시점 원화의 **그림 자체를 생성형 이미지 모델로 그린다**. Python/Pillow/cairoSVG/SVG path/ellipse/rectangle/polygon/HTML Canvas/Matplotlib 좌표로 캐릭터의 얼굴·팔·손·헤어·옷을 조합하여 이미지로 출력한 것, 벡터 아이콘/교재용 도형/프록시는 **불합격**이다. 기존 벡터 도형 그림에 그림자·그라데이션만 더해도 불합격이다. 코드·스크립트는 완성도 높은 **실제 생성 원화**를 PSD·마스크·레이어로 가공/검증할 때만 사용한다. 이미지 생성 기능을 못 썼다면 코드로 대체하여 성공이라고 주장하지 않는다.
- **선화/채색 목표:** 숙련된 애니 원화가의 방송용 Live2D/VTuber 스타일. 일관된 실루엣·강약 있는 섬세한 선화·풍부한 표정·세련된 셀 그림자/미묘한 색 변주·눈/소재별 충분한 내부 디테일. 평면 SVG 인형·클립아트·초등 교재 그림·아이콘·스틱 피겨는 거절한다. 단색 타원으로만 된 눈/귀/입/손은 원화가 아니다.
- **모드별 실제 구도:** {mode_brief}
- **해당 자산의 고품질 제작 조건:** {details}
- **반드시 실제로 비교:** 마스터 원본과 다각도/표정 PNG를 열어 동일 인물·눈매·선 굵기·명암·가림·관절 이음의 일관성을 확인한다. 옆모습은 정면의 미러링/눌러 늘이기가 아니어야 하며, 정면의 분할 이미지를 다른 각도 파일에 복제하는 것은 실패다.
- **결과물:** {mode_output}
- **반려 기준:** 임시 벡터 도형 사람/투박한 몸통/손가락 없는 손/정면을 압축한 프로필/눈 감김과 입 벌림 원화 누락, 리깅용 목 연결 빈 공간, 이상한 이중 파츠, 낮은 미술 품질, 참조 이미지와 크게 다른 얼굴. 파츠 24개·PNG 9장·PSD 합성 오차 0·ZIP CRC 성공만으로 절대 승인하지 않는다.
- **도구 불가 시:** 실제 이미지 생성기가 사용 불가능하거나 거절하면 성인·완전 착의·비성적 디자인 조건을 유지해 적절히 고치고, 그래도 불가능하면 해당 생성 단계를 미완료로 정확히 보고한다. 생성 기능 없이 낮은 수준의 프로그래밍 그림을 만들어 완료라고 제출하지 않는다.
- **최종 시각 검수:** 선화·얼굴·눈·원화 해상도/세부 수준·해당 자산만 제작됐는지 시각 확인한 증거가 없으면 ART_QUALITY_UNVERIFIED로 표기하고 납품하지 않는다.

{END}
"""


def patched_text(content: str, *, mode: str, asset: str, name: str) -> str:
    if content.count(START) != content.count(END) or content.count(START) > 1:
        raise ValueError("Partial/duplicate art-first gate: " + mode + "/" + asset + "/" + name)
    if START in content:
        start = content.index(START)
        end = content.index(END, start) + len(END)
        content = content[:start] + content[end:].lstrip("\r\n")
    if name not in DOCS:
        return content
    quality = quality_text(mode, asset)
    # Keep 14-MD-read-first at byte 0; BODY clothing comes before art.
    if content.startswith("# [READ_ALL_BEFORE_IMAGE_GENERATION_V1]"):
        boundary = content.find(READ_FIRST_END)
        if boundary < 0:
            raise ValueError("Read-first banner incomplete: " + name)
        boundary += len(READ_FIRST_END)
        content = content[:boundary].rstrip("\r\n") + "\n\n" + quality + "\n\n" + content[boundary:].lstrip("\r\n")
    elif COVER_MARKER in content:
        boundary = content.find(COVER_MARKER_END)
        if boundary < 0:
            raise ValueError("Clothing gate incomplete: " + name)
        boundary += len(COVER_MARKER_END)
        content = content[:boundary].rstrip("\r\n") + "\n\n" + quality + "\n\n" + content[boundary:].lstrip("\r\n")
    else:
        content = quality + "\n\n" + content.lstrip("\r\n")
    return content


def patch(path: Path, *, write: bool) -> bool:
    mode, asset = path.stem.rsplit("__", 1)
    if mode not in MODES or asset not in ASSETS:
        raise ValueError("Unknown mode/asset: " + str(path))
    with ZipFile(path) as z:
        infos = z.infolist()
        names = [i.filename for i in infos]
        if len(infos) != 14 or set(names) != set(EXPECTED) or z.testzip() is not None:
            raise ValueError("Corrupt/cross-contaminated instruction ZIP: " + str(path))
        old = {name: z.read(name).decode("utf-8") for name in names}
    new = {name: patched_text(old[name], mode=mode, asset=asset, name=name)
           for name in names}
    if new == old:
        return False
    if not write:
        raise ValueError("Art-first quality brief missing: " + path.name)
    tmp: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".zip", delete=False) as handle:
            tmp = Path(handle.name)
        with ZipFile(tmp, "w") as z:
            for info in infos:
                z.writestr(info, new[info.filename].encode("utf-8"))
        with ZipFile(tmp) as z:
            if z.testzip() is not None or z.namelist() != names:
                raise ValueError("Repacked instruction ZIP failed verification")
            if any(z.read(n).decode("utf-8") != new[n] for n in names):
                raise ValueError("Repacked MD bytes do not match")
        os.replace(tmp, path)
        tmp = None
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)
    return True


def main() -> int:
    cli = argparse.ArgumentParser()
    flags = cli.add_mutually_exclusive_group(required=True)
    flags.add_argument("--check", action="store_true")
    flags.add_argument("--write", action="store_true")
    args = cli.parse_args()
    changed = 0
    for mode in MODES:
        for asset in ASSETS:
            changed += patch(ROOT / f"{mode}__{asset}.zip", write=args.write)
    print(f"PASS: 24 asset/mode-specific image-model-first quality briefs; changed={changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
