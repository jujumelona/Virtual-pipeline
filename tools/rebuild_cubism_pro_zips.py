"""Rebuild existing Live2D instructional ZIPs for a Cubism PRO template-first workflow.

Source images are still drawn and approved before See-through separation. The
fourteen source instruction names stay stable for compatibility. Inochi/3D kits
are not changed. Running twice produces identical document content.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from zipfile import ZipFile, ZIP_STORED

ROOT = Path(__file__).resolve().parents[1] / "docs/image_ai_kits_v2/zips"
KIT_NAMES = ("face.zip",) + tuple(
    f"live2d_{frame}__{part}.zip"
    for frame in ("bust_up", "upper", "full")
    for part in ("hair", "outfit", "accessory")
)
OPEN = "\n\n<!-- CUBISM_PRO_TEMPLATE_FIRST_V1 -->\n"
CLOSE = "\n<!-- /CUBISM_PRO_TEMPLATE_FIRST_V1 -->\n\n"


def _category(filename: str) -> str:
    return "face" if filename == "face.zip" else filename.split("__", 1)[1][:-4]


def _specific(category: str) -> str:
    if category == "face":
        return """**FACE 템플릿 대응 (민트눈 RE:ARCHIVE 캐릭터):**
- face_base, face_underpaint, ear_L/R, neck_front/underpaint;
  eye_L/R_white, eye_L/R_iris, eye_L/R_pupil, eye_L/R_highlight,
  eyelash_upper_L/R, eyelid_L/R; brow_L/R; mouth_upper/lower/inside/tongue.
- 민트색 다층 홍채, 좌우 깜빡임, 입 열림/닫힘, ±30~45°에 필요한 가림 영역과
  얼굴-목 접합부를 참고 원화에 명확히 그린다. 마스킹용 피부는 얼굴 피부와 같은 색.
- FACE 자산은 얼굴·목 범위만 유지한다. 의상이나 머리카락을 끼워 넣지 않는다.
"""
    if category == "hair":
        return """**HAIR 템플릿 대응:**
- hair_back, hair_side_L/R, hair_front_L/R, hair_root_L/R, tail_L/R_root,
  tail_L/R_mid/tip, ribbon_L/R 등을 원화에서 시각적으로 읽히게 설계한다.
- 트윈테일·머리 끝 흔들림은 머리 회전 디포머의 자식이 되므로 뿌리,
  움직임 중 보이는 뒤통수, 교차 가림을 미리 설계한다.
- DNA 이중나선 머리장식은 헤어 실루엣에 아예 인쇄하지 말고,
  탈착 가능한 액세서리로 분리 가능한 구조로 묘사한다.
"""
    if category == "outfit":
        return """**OUTFIT 템플릿 대응:**
- collar, neck_seam, torso_front, sleeve_L/R, arm_L/R, cuff_L/R,
  bust/waist folds를 각각 읽을 수 있는 디자인으로 그린다.
- 큰 소매의 물리 흔들림, 어깨 회전, 가슴 장식이 겹치는 공간과
  몸통·목 연결을 디자인 단계부터 확보한다.
- DNA 이중나선 자수는 장식으로 유지하되, 흔들리는 캡슐·체인과
  의상 평면 문양을 혼동하지 않도록 분리 가능하게 설계한다.
"""
    return """**ACCESSORY 템플릿 대응:**
- DNA 보존 캡슐 본체, 내부 이중나선 가닥 2개, 연결 링, 케이블·체인,
  머리 장식 DNA 헬릭스, 의상 배지/고정구를 서로 구별해 그린다.
- 캡슐 몸체는 단단한 별도 회전/이동 디포머, 링과 연결선은
  독립 물리 디포머를 염두에 두고 애초에 그림 경계를 설계한다.
- 장식은 눈·목·어깨를 가리지 않으며, 매달린 지점과 흔들림 여유를
  캡슐 본체에 실제로 연결한다. 과장된 입자/점멸 이펙트 금지.
"""


def _block(category: str, section: str) -> str:
    base = """**최종 경로:** 승인된 마스터 원화 + 시점 참고 → 동일 캔버스 정합 →
원본 RGBA 파츠가 존재하면 보존하고, 없으면 완성 정면 합성본을
See-through + SemanticSAM으로 분리 → PSD → Cubism Editor PRO에서
**실제 권한이 있는 고급 모델 템플릿**을 부분 적용 → 키폼/물리 보정 →
공식 에디터에서 CMO3 저장 및 MOC3 export → VTube Studio 실기 검증.

**가장 중요한 제작 조건:** 신규 원화는 사용 가능한 템플릿의 얼굴 폭,
눈·입의 상대 위치, 목/어깨 앵커, 머리카락 시작점, 팔·소매의 관절,
장식 부착 위치와 비슷하게 설계해 변형/물리를 재활용하기 쉽게 한다.
원본 모델을 무단 복제하는 게 아니라 기존 리깅 **구조와 비율**을 참고한다.
고품질 애니 일러스트를 먼저 승인하고, 그다음 파츠를 분리한다.
아티스트 또는 이미지 생성 모델이 원화를 먼저 합격시키지 못하면
단순 도형·가짜 레이어로 때우지 말 것.

**제작 단계 분리:** 이 지침 ZIP을 받은 이미지 생성 AI는 리깅 완료를
허위 주장하지 않으며, 기존 master/reference PNG 의무 출력은 유지한다.
실제 아트 레이어/PSD는 후속 도구 또는 원화 담당자가 만들어야 한다.
원본부터 독립 RGBA 레이어가 실제로 그려져 있으면 part_art와 순서를
후속 Colab에 전달해 See-through **재분리 없이 보존**할 수 있다.
단순 크롭·복사로 만든 가짜 눈/머리카락 레이어는 불합격이다.

**모델 템플릿의 한계:** Cubism Editor PRO의 공식 모델 템플릿 적용은
선택된 ArtMesh, 위치/형상/이름에 따라 매핑한다. 원본에 없는 가닥,
DNA 캡슐·이중나선 메쉬와 물리는 자동 생성되는 것으로 가정하지 않는다.
프로젝트 내 원본 CMO3/PSD가 있어야 재사용 가능성이 높으며,
MOC3 런타임만으로 편집 리깅을 복원하지 않는다.
"""
    section_specific = _specific(category)
    if section == "00_MASTER_FIRST.md":
        return "# CUBISM PRO — 최우선 디자인/제작 경로\n\n" + base + "\n" + section_specific
    if section == "02_ADVANCED_PARTS.md":
        return "# 고급 리깅 재사용을 위한 디자인 분해 기준\n\n" + section_specific + """
**후속 PSD 규칙:** 모든 독립 PNG는 같은 원점·캔버스·알파를 갖고,
가려지는 피부/머리카락/소매 안쪽을 실제로 더 그린다.
Cubism 템플릿에서 같은 이름 우선 매핑을 활용하도록
위 파츠 명칭을 PSD 레이어명으로 권장한다. 신규 90도 시점 원화는
자동으로 90도 키폼이 되는 것이 아니므로 수동 모델링 검증이 필요하다.
"""
    if section == "04_OUTPUT_FILES.md":
        return "# 납품과 PRO 핸드오프\n\n" + """
이 이미지 생성 ZIP은 기존 필수 outputs/master.png 및 reference_views/
expression_refs PNG를 그대로 납품한다. 원화 ZIP 자체에 허위 CMO3,
MOC3 또는 미생성 PSD를 넣지 않는다. 실제 파츠를 제공하는 경우에만
등록 캔버스가 같은 실제 독립 RGBA 파츠와 순서 정보를 별도로
정확히 제공한다. PSD 단계에서는 반드시 원화 픽셀을 보존한다.

Colab 기본 최종 출력은 Cubism PRO 입력 번들:
avatar.psd + cubism_pro/rig_transfer_plan.json +
cubism_pro/START_HERE.md + 원본 PSD ZIP의 비-PSD 자료.
기존 PSD2Live/MOC3 자동 생성은 별도로 선택할 때만 실행한다.
Cubism Editor의 템플릿 적용/물리 수정/CMO3 저장은 Windows/Mac
에디터 작업이며 Colab에서 수행했다고 표시하지 않는다.
"""
    if section == "07_REVIEW_BEFORE_FINAL_ZIP.md":
        return "# Cubism PRO 제작 적합성 최종 검수\n\n" + """
[ ] 실제 템플릿 기준과 얼굴/목/어깨/소매의 고정점이 일치하는가?
[ ] 눈/입/얼굴, 머리/뒤통수, 소매/어깨의 숨은 영역을 참조할 수 있는가?
[ ] 머리카락/의상/캡슐의 가림 순서와 물리 연결이 가능한가?
[ ] DNA 헬릭스가 단순 형광 무늬가 아니라 독립된 실물 장식인가?
[ ] PSD 원화와 장치에 실제 분리 가능한 경계가 있는가?
[ ] 템플릿으로 재활용 가능한 부분과 추가 리깅 부위를 구분했는가?
"""
    return "# PRO 납품 순서\n\n" + base


def _update_text(text: str, category: str, name: str) -> str:
    if category == "face":
        text = (text.replace("amber-orange", "mint-green")
                    .replace("golden-orange", "mint-green")
                    .replace("주황색", "민트색")
                    .replace("주황", "민트"))
    new = OPEN + _block(category, name) + CLOSE
    if OPEN.strip() in text:
        first = text.index(OPEN.strip())
        last = text.find(CLOSE.strip(), first)
        if last < 0:
            raise ValueError("existing marker not closed")
        return text[:first] + new.strip("\n") + text[last + len(CLOSE.strip()):]
    first_line_end = text.index("\n") if "\n" in text else len(text)
    return text[:first_line_end] + new + text[first_line_end:]


def transform_zip(path: Path) -> bool:
    category = _category(path.name)
    with ZipFile(path) as src:
        infos = src.infolist()
        if len(infos) != 14 or any(i.is_dir() for i in infos):
            raise ValueError("expected exactly 14 original instructional files")
        payload = [(i.filename, src.read(i.filename)) for i in infos]
    result = []
    for name, body in payload:
        if name in {
            "00_MASTER_FIRST.md", "00_DELIVERY_AND_RECHECK.md",
            "02_ADVANCED_PARTS.md", "04_OUTPUT_FILES.md", "07_REVIEW_BEFORE_FINAL_ZIP.md"
        }:
            original = body.decode("utf-8")
            body = _update_text(original, category, name).encode("utf-8")
        elif category == "face":
            original = body.decode("utf-8")
            body = (original.replace("amber-orange", "mint-green")
                            .replace("golden-orange", "mint-green")
                            .replace("주황색", "민트색")
                            .replace("주황", "민트")).encode("utf-8")
        result.append((name, body))
    out = path.with_suffix(".cubism-pro.tmp")
    with ZipFile(out, "w", compression=ZIP_STORED) as dst:
        for name, body in result:
            dst.writestr(name, body)
    with ZipFile(out) as dst:
        if dst.testzip() is not None or len(dst.namelist()) != len(result):
            raise ValueError("generated instructional ZIP failed validation")
    changed = path.read_bytes() != out.read_bytes()
    out.replace(path)
    return changed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--check", action="store_true",
                        help="Verify every ZIP is already the reproducible PRO version")
    args = parser.parse_args()
    for filename in KIT_NAMES:
        dest = args.root / filename
        if not dest.is_file():
            raise FileNotFoundError(dest)
        if args.check:
            import shutil
            import tempfile
            with tempfile.TemporaryDirectory() as scratch:
                copy = Path(scratch) / filename
                shutil.copyfile(dest, copy)
                changed = transform_zip(copy)
                if changed or copy.read_bytes() != dest.read_bytes():
                    raise SystemExit("CUBISM_PRO_INSTRUCTION_ZIP_STALE: " + filename)
            print(filename, "PASS reproducible")
        else:
            print(filename, "updated" if transform_zip(dest) else "unchanged")


if __name__ == "__main__":
    main()
