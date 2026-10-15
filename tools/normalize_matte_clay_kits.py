"""Canonical matte-clay artwork contract across 24 published image-AI kits.

This is a *drawing direction* for safe, non-anatomical VTuber character
bases. It does not generate nude/undressed reference art, disable moderation,
or replace the downstream editable PSD/PNG production requirements.

The 6 BODY kits generate a high-quality anime head with a flat matte-clay
covered torso and simplified non-anatomical limb silhouettes. The remaining
18 kits respect that BODY anchor but generate only their own asset.

Write/check are idempotent; existing 14 MD filenames and all engine-specific
paths and view contracts stay unchanged.
"""
from __future__ import annotations

import argparse
import os
import re
import tempfile
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1] / "docs/image_ai_kits_v2/zips"
MODES = ("live2d_bust_up", "live2d_upper", "live2d_full",
         "inochi2d_upper", "inochi2d_full", "3d")
ASSETS = ("body", "hair", "outfit", "accessory")
START = "## [MATTE_CLAY_BODY_V1]"
END = "## [/MATTE_CLAY_BODY_V1]"
OLD_COVER_START = "## [BODY_DEFAULT_OPAQUE_SWIMWEAR_V1]"
OLD_COVER_END = "## [/BODY_DEFAULT_OPAQUE_SWIMWEAR_V1]"
OLD_SHOULDER_START = "## [NECK_SHOULDER_OPEN_V2]"
OLD_SHOULDER_END = "## [/NECK_SHOULDER_OPEN_V2]"

CONTRACT = {
 "body": """### BODY — 불투명 단색 무광 찰흙형 베이스 (필수)
- 20세 이상 성인의 비성적이고 귀여운 애니 VTuber 디자인. 얼굴은 짧고 넓으며 부드러운 U형 턱, 큰 눈·홍채, 간결한 코·하나의 입을 선명한 완성 애니 원화로 그린다. 머리카락은 HAIR에서 만든다.
- **몸통은 해부학적 피부 원화가 아니라 불투명한 단색의 매끈한 무광 찰흙·마네킹형 가림 외피**로 그린다. 회색/살구색/중립 파스텔색 등의 균일한 불투명 색 면을 허용한다. 피부 조직, 가슴 형태, 흉근·복근·갈비뼈·배꼽·속옷/옷 주름, 인체 음영과 사실적인 골격 묘사는 추가하지 않는다. 실사 나체나 정교한 미해부 모델을 생성하지 않는다.
- **목과 양쪽 어깨 상단·목-어깨 접합부·팔의 회전 시작점은 가리지 않는다.** 쇄골/근육을 자세히 그리지는 않되 목·어깨·팔·손의 외곽과 자연스러운 연결을 유지한다. 팔·손과 전신 모드의 다리·발도 무광 단색의 단순한 비해부학적 실루엣으로 표현하며, 관절은 움직임용으로 분리한다.
- 상체 중심부는 형태가 강조되지 않는 평평하고 불투명한 무광 표면이다. 선명한 인체 굴곡·가슴 모양·실사 피부 셰이딩이 생기면 **몸통 영역만** 단색으로 수정한다. 얼굴·눈·손과 연결부의 필요한 선화 품질은 낮추지 않는다.
- 기본 마스터·참고 시점·합성 미리보기는 모두 **가려진 중성형 모델**로 유지한다. 무광 외피를 벗긴 노출 신체 참고 이미지나 세부 해부학 언더페인트를 생성하지 않는다. 가린 부분의 교차 면은 단색 비해부학적 픽셀로만 연장한다.
- 2D에서 기존 호환 파일명 removable_neutral_modesty_band_upper, 화면에 실제 하체가 보이는 경우 removable_neutral_modesty_band_lower를 그대로 사용한다. 이 명칭은 예전 입력 계약 이름일 뿐 시각적으로 수영복이나 브라를 그리라는 지시가 **아니다**. 가림용 레이어는 합성에서 ON, 숨은 면/표정 대체 레이어는 필요 상태에서만 ON이다.
- **원화 먼저, 파츠 분리 나중.** 2D는 원화·독립 알파 PNG·마스크·레이어 순서·편집 가능한 다층 PSD, 목/턱/어깨 관절의 단색 underpaint를 남긴다. 회전 시점의 실제 신규 참고 그림도 만든다. 3D는 8방향 + 가림 상세 1장(총 9장)의 같은 단색 캐릭터 참조를 만든다. 3D ZIP은 PSD·Cubism 파츠나 네이티브 VRM을 요구하지 않는다.
- 신체 비례·표정과 엔진/모드별 필수 시점 및 파츠 계약은 유지한다. 몸통을 단색으로 그렸다는 이유만으로 FAIL로 판정하지 않는다. 얼굴/눈/관절의 미완성, 목 잘림, 가림 누락, 잘못된 알파 및 합성 실패는 FAIL이다.
""",
 "hair": """### HAIR — 찰흙형 BODY 위에 헤어만 제작
- BODY는 가슴·복부 해부학 상세 없이 **불투명 무광 단색 찰흙형 상체 베이스**를 사용한다. HAIR은 이미 존재하는 몸체/목/어깨/얼굴 비율을 변경하거나 재생성하지 않는다.
- 실제 생성·PSD 파츠·PNG에는 요청받은 머리카락만 포함한다. 필요하면 모발이 목/어깨 위로 드리워져도 되지만, BODY의 숨은 피부/모델 실루엣은 별도로 보존한다. 마네킹형 몸체를 HAIR 출력으로 납품하지 않는다.
- 헤어의 선·가닥·음영 품질은 사용자 디자인과 애니 원화 기준을 그대로 지킨다. BODY의 단색 정책을 머리카락까지 단색 도형으로 강제하지 않는다.
""",
 "outfit": """### OUTFIT — 찰흙형 BODY와 독립된 실제 의상
- 정렬 기준 BODY는 **불투명 무광 단색 찰흙형 몸통**이다. 사용자 주문 의상만 실제로 제작하고, BODY의 얼굴·목·어깨·팔·몸체나 숨은 면을 새로 그리거나 지우지 않는다.
- OUTFIT에는 사용자가 지정한 의상 고유의 재질·봉제선·주름·안감 및 원하는 넥라인(하이넥·어깨끈 포함)을 그릴 수 있다. 그 묘사를 BODY의 해부학적 원화로 역전파하거나 BODY 기본 가림으로 재정의하지 않는다.
- 동일 캔버스·앵커에 맞춘 독립 의상 파츠·가림 후면·마스크·PSD를 납품한다. 합성 미리보기의 BODY는 언제나 불투명 단색 베이스 상태다.
""",
 "accessory": """### ACCESSORY — 찰흙형 BODY의 비변경 원칙
- 정렬 기준 BODY는 **불투명 무광 단색 찰흙형 몸통**이다. 사용자 요청 액세서리 한 종류만 만들며 목·어깨·팔·몸체의 인체/피부 묘사를 새로 그리지 않는다.
- 요청된 목걸이/장식 등이 어깨·목과 겹쳐도, 원본 BODY의 목·어깨 연결 실루엣·회전용 숨은 면은 반드시 유지한다. 자동으로 복장이나 다른 액세서리를 추가하지 않는다.
- 별도 PNG/PSD 파츠와 부착점·가림 깊이·참고 시점·합성 품질을 검증한다.
"""
}

# These are *specific contradictory directives* discovered in the published
# 14-document BODY ZIPs. Retain other important clauses on their lines.
BODY_REPLACEMENTS = (
 ("얼굴만 잘린 과도한 크롭과 단색 몸통 프록시를 금지하며",
  "얼굴만 잘린 과도한 크롭은 금지하며 무광 단색 찰흙형 몸통을 허용하되"),
 ("회색 단색 몸통, 프록시 도형, 끊긴 목, 누락된 팔/손, 짧은 상체는 최종 FAIL.",
  "세밀한 몸통 해부학 표현, 끊긴 목, 누락된 팔/손, 짧은 상체는 최종 FAIL. 불투명 무광 단색 몸통은 정상."),
 ("회색 찰흙/기하 프록시가 아닌 실제 애니풍 채색 원화로 만든다.",
  "비해부학적 불투명 무광 찰흙형 몸통 베이스로 표현한다. 얼굴과 눈의 애니풍 원화 품질은 유지한다."),
 ("체형은 회색 찰흙/기하 프록시가 아닌 실제 애니풍 채색 원화.",
  "몸통은 불투명 무광 단색 찰흙형 베이스. 얼굴과 눈은 높은 품질의 애니풍 원화."),
 ("회색 도형 프록시로 대체하지 않는다.",
  "몸통에 불투명 단색 무광 찰흙 베이스를 사용하되, 얼굴·눈·손은 완성 애니풍 원화로 만든다."),
 ("BODY는 의상 교체용 공통 신체이지만 실제로 완성된 애니풍 피부 원화여야 한다.",
  "BODY는 의상 교체용 공통 베이스로서 몸통은 불투명한 비해부학적 무광 단색 찰흙 외피로 제작한다."),
 ("회색 몸통 프록시를 금지", "실사형 몸통 해부학 묘사를 금지"),
 ("단색 몸통 프록시 금지", "단색 무광 찰흙형 몸통 허용"),
 ("단색 몸통 프록시를 금지", "단색 무광 찰흙형 몸통을 허용"),
 ("단색 2D 도형 프록시는 미술 완성품으로 금지",
  "몸통의 불투명 단색 무광 찰흙형 표현은 허용하며 얼굴/눈/손은 완성 원화로 제작"),
 ("불투명한 어깨끈 없는 반도형 수영복 상의",
  "불투명 무광 단색 찰흙형 상체 가림 외피"),
 ("불투명한 스포츠형 수영복 상의",
  "불투명 무광 단색 찰흙형 상체 가림 외피"),
 ("불투명한 스포츠 수영복 상의",
  "불투명 무광 단색 찰흙형 상체 가림 외피"),
 ("불투명 스포츠 수영복 상의",
  "불투명 무광 단색 찰흙형 상체 가림 외피"),
 ("불투명 스포츠 수영복", "불투명 무광 단색 찰흙형 가림 베이스"),
 ("불투명 수영복", "불투명 무광 단색 찰흙형 가림 베이스"),
 ("기본 수영복의 상·하의는", "기본 단색 모델 가림용 상·하부는"),
 ("수영복의 상·하의는", "단색 가림 베이스의 상·하부는"),
 ("수영복 아래의 신체", "단색 가림 외피 아래의 신체"),
 ("수영복을 착용한", "불투명 단색 외피로 덮인"),
 ("수영복 상의·하의", "단색 가림 상·하부"),
 ("수영복 상·하의", "단색 가림 상·하부"),
 ("기본 수영복", "기본 단색 가림 외피"),
 ("스포츠 수영복", "단색 가림 외피"),
 ("수영복", "단색 가림 외피"),
)

CONFLICT = (
 "단색 몸통 프록시를 금지",
 "단색 몸통 프록시 금지",
 "회색 단색 몸통, 프록시 도형",
 "회색 찰흙/기하 프록시가 아닌",
 "회색 도형 프록시로 대체하지 않는다",
 "비키니형 스포츠",
 "스포츠형 수영복",
 "반도형 수영복",
)

def replace_marked(s: str, begin: str, end: str, replacement: str) -> str:
    if s.count(begin) != s.count(end) or s.count(begin) > 1:
        raise ValueError("Partial or duplicated named contract: " + begin)
    if begin not in s:
        return s
    pattern = re.escape(begin) + r".*?" + re.escape(end)
    return re.sub(pattern, lambda _: replacement, s, flags=re.S)

def normalize(s: str, asset: str, mode: str, name: str) -> str:
    # Remove previous high-priority copy before replacing actionable original
    # paragraphs. Preserve the read-all-first banner at byte zero.
    s = replace_marked(s, START, END, "")
    s = replace_marked(s, OLD_SHOULDER_START, OLD_SHOULDER_END, "")
    if asset == "body":
        # The old swimwear marker is reused by older tooling, but its actual
        # *contents* now describe matte non-anatomical full-coverage art.
        for old, new in BODY_REPLACEMENTS:
            s = s.replace(old, new)
        # Replace the legacy block *after* normalizing old prose; never
        # mutate the final canonical brief (or break old generator parity).
        cover = OLD_COVER_START + "\n\n" + CONTRACT["body"] + OLD_COVER_END
        s = replace_marked(s, OLD_COVER_START, OLD_COVER_END, cover)
        if any(word in s for word in CONFLICT):
            matches = [word for word in CONFLICT if word in s]
            raise ValueError("Conflicting BODY instruction in " + mode + "/" + name
                             + ": " + repr(matches))
    # Do not inherit BODY-wardrobe wording in non-BODY products.
    if asset != "body":
        s = s.replace("기본 BODY의 수영복", "기본 BODY의 단색 무광 찰흙 외피")
        s = s.replace("기본 가림 수영복", "기본 단색 무광 찰흙 외피")
    s = s.rstrip() + "\n\n" + START + "\n" + CONTRACT[asset] + END + "\n"
    # Final single source of truth: these are image-generating AI kits,
    # not part-splitting/PSD authoring instructions. Keep all 14 original
    # reference documents but remove old division/rigging deliverables.
    from tools.image_ai_source_only_contract import normalize_source_only
    return normalize_source_only(s, mode, asset, name)

def update(path: Path, asset: str, mode: str, write: bool) -> bool:
    if not path.is_file():
        raise FileNotFoundError(path)
    with ZipFile(path) as z:
        infos = z.infolist()
        if len(infos) != 14 or len({i.filename for i in infos}) != 14 or z.testzip():
            raise ValueError("Corrupt or wrong 14-document kit: " + str(path))
        if any(not i.filename.endswith(".md") for i in infos):
            raise ValueError("Unexpected ZIP member in " + str(path))
        original = {i.filename: z.read(i.filename).decode("utf-8") for i in infos}
    updated = {name: normalize(s, asset, mode, name) for name, s in original.items()}
    for name, text in updated.items():
        if text.count(START) != 1 or text.count(END) != 1:
            raise ValueError("Missing matte-clay scope: " + path.name + "/" + name)
        if asset == "body" and "불투명 단색 무광 찰흙형" not in text:
            raise ValueError("BODY must direct matte shape: " + path.name + "/" + name)
        if asset != "body" and OLD_COVER_START in text:
            raise ValueError("BODY wardrobe contaminated " + path.name + "/" + name)
    changed = updated != original
    if changed and write:
        tmp = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".zip",
                                             prefix=".matte-", delete=False) as f:
                tmp = Path(f.name)
            with ZipFile(tmp, "w") as out:
                for member in infos:
                    out.writestr(member, updated[member.filename].encode("utf-8"))
            with ZipFile(tmp) as check:
                if check.namelist() != [i.filename for i in infos] or check.testzip():
                    raise ValueError("Rebuilt ZIP failed integrity check " + path.name)
            os.replace(tmp, path)
            tmp = None
        finally:
            if tmp:
                tmp.unlink(missing_ok=True)
    return changed

def main() -> None:
    parser = argparse.ArgumentParser()
    opt = parser.add_mutually_exclusive_group(required=True)
    opt.add_argument("--write", action="store_true")
    opt.add_argument("--check", action="store_true")
    args = parser.parse_args()
    modified = []
    for mode in MODES:
        for asset in ASSETS:
            path = ROOT / (mode + "__" + asset + ".zip")
            if update(path, asset, mode, args.write):
                modified.append(path.name)
    if args.check and modified:
        raise SystemExit("FAIL: matte-clay directions not published in: "
                         + ", ".join(modified))
    print("24 ZIPs / 336 MD / 4 asset roles OK; updated=" + str(len(modified)))
    if modified:
        print(", ".join(modified))

if __name__ == "__main__":
    main()
