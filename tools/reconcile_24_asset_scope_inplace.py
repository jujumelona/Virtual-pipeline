"""Repair actual active drawing commands inside ALL 336 existing ZIP documents.

Preserve original art references and non-conflicting advice. Do not replace real
content with a front-page priority notice. This is deliberately idempotent.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path
from zipfile import ZipFile, ZIP_STORED

ROOT = Path(__file__).resolve().parents[1] / "docs/image_ai_kits_v2/zips"
MODES = ("live2d_bust_up", "live2d_upper", "live2d_full",
         "inochi2d_upper", "inochi2d_full", "3d")
ASSETS = ("body", "hair", "outfit", "accessory")
DOC_COUNT = 14
MODE_SOURCE = {
    "live2d_bust_up": "방송용 바스트업: 머리·얼굴을 크게, 아래쪽은 상복부와 양손 손가락 끝까지만. 골반·허벅지·무릎·발·전신 그림 생성 금지",
    "live2d_upper": "Live2D 상반신: 머리부터 허리 부근까지, 양어깨·양팔·양손 포함. 골반 아래 다리·발·전신 생성 금지",
    "live2d_full": "Live2D 전신: 정수리부터 양발 끝까지, 양팔·손·양다리 포함. 프로젝트 6등신 디자인",
    "inochi2d_upper": "Inochi2D 상반신: 머리부터 허리 부근까지, 양팔·양손. 골반 아래 다리·발·전신 생성 금지",
    "inochi2d_full": "Inochi2D 전신: 머리부터 양발 끝까지. 양팔·손·양다리 포함",
    "3d": "3D 자산별 참조: 전/후/좌/우 및 네 대각 총 8방향의 일관된 원화. 메시·스키닝·2D PSD 납품 아님",
}
ASSET_TARGET = {
    "body": "BODY: 민머리 두상·얼굴 피부·양눈·입·코·귀·목·어깨·몸통 무광 외피·양팔·양손만. 머리카락·패션 의상·장신구 픽셀 0개",
    "hair": "HAIR: 앞머리·좌우 옆머리·뒷머리 및 필요한 독립 모발만. BODY·얼굴·눈·손·의상·액세서리 그림은 기준 참조이며 출력에는 0개",
    "outfit": "OUTFIT: 실제 옷감·소매·옷깃·밑단·의상에 붙은 디자인 요소만. BODY·얼굴·눈·피부·헤어·독립 장신구 픽셀은 0개",
    "accessory": "ACCESSORY: 지정된 단일 장신구만. BODY·얼굴·눈·피부·헤어·의복 픽셀과 요청하지 않은 다른 장신구는 0개",
}
# Explicit include/exclude directions repeated in every member, including the
# instructions actually read by the generating AI. These are OUTPUT rules,
# not merely high-priority precedence declarations or reference annotations.
ASSET_EXCLUDE = {
    "body": (
        "BODY에서 머리카락 전부 제외: 앞머리·옆머리·뒷머리·잔머리·묶음머리·"
        "포니테일·헤어 장식·머리핀·리본·귀걸이·안경·목걸이·독립 액세서리·"
        "패션 의상·옷깃·소매·의복 주름 생성 금지. 민머리 신체 베이스만 만든다. "
        "참조 캐릭터에 머리카락/의상이 보여도 BODY 마스터나 각도·표정 참고 그림에 복사하지 않는다"
    ),
    "hair": (
        "HAIR에서는 머리카락만. 얼굴 피부·눈·홍채·흰자·속눈썹·코·입·귀·"
        "목·어깨·팔·손·몸통·의상·헤어 장식/액세서리 픽셀 생성 금지. "
        "기준 BODY는 참조이고 헤어 PNG에 합치지 않는다"
    ),
    "outfit": (
        "OUTFIT에서는 옷감과 의복 일체형 부속만. 머리카락·얼굴·눈·입·"
        "몸통 피부·양팔·양손·다리 피부·장신구 독립 파츠 생성 금지. "
        "기준 BODY/HAIR는 참조이고 의상 이미지에 합치지 않는다"
    ),
    "accessory": (
        "ACCESSORY에서는 요청된 한 종류의 장신구만. 머리카락·얼굴·눈·"
        "피부·몸통·손·의상·요청되지 않은 기타 장식 생성 금지. "
        "장착 위치의 기준 BODY/HAIR/OUTFIT 원화는 참조일 뿐 픽셀 납품 금지"
    ),
}
ASSET_REJECT = {
    "body": (
        "BODY master 및 정면·3/4·측면·후면 참조에서 머리카락 한 가닥, "
        "헤어핀, 의상 디자인, 독립 장신구가 보이면 CROSS_ASSET_CONTAMINATION: FAIL. "
        "참고 합성본은 별도 previews/로 격리하고 실제 BODY 납품에 섞지 않는다. "
        "실제 눈으로 확인하기 전 PASS 선언 금지; 위반 시 BODY 원화를 수정·재검수"
    ),
    "hair": (
        "HAIR master/납품 PNG에 눈·얼굴·피부·의복·머리장식이 있으면 "
        "CROSS_ASSET_CONTAMINATION: FAIL. 기준 캐릭터 합성은 별도 previews/에서만 허용"
    ),
    "outfit": (
        "OUTFIT master/납품 PNG에 피부·얼굴·눈·머리카락·독립 장신구가 있으면 "
        "CROSS_ASSET_CONTAMINATION: FAIL. 기준 캐릭터 합성은 별도 previews/에서만 허용"
    ),
    "accessory": (
        "ACCESSORY master/납품 PNG에 머리카락·피부·얼굴·의상 또는 요청되지 않은 "
        "추가 소품이 있으면 CROSS_ASSET_CONTAMINATION: FAIL. "
        "기준 캐릭터 합성은 별도 previews/에서만 허용"
    ),
}

REFERENCE_ONLY = {
    "hair": "승인된 얼굴·눈·몸통은 위치/크기 참조일 뿐 새로 그리지 않는다. 두피 경계와 모근만 정합시킨다",
    "outfit": "승인된 얼굴·눈·팔·몸통은 위치와 가림 참조다. 옷감만 독립 원화로 그리며 피부를 함께 칠하지 않는다",
    "accessory": "승인된 두상·귀·머리·몸체는 부착 위치 참조다. 오직 지정된 장신구만 원화로 그린다",
}
RENDER_QUALITY = {
    "body": "얼굴·눈·피부·무광 몸통·팔·손의 선화·채색·연결·구도, 다른 자산 혼입 여부를 실제 시각 확인",
    "hair": "모근·앞옆뒷머리·묶음·흔들릴 가닥의 선폭·채색·연결과 다른 자산 픽셀 혼입을 실제 시각 확인",
    "outfit": "옷감·주름·봉제선·몸판·소매·옷깃·가려진 원단과 다른 자산 픽셀 혼입을 실제 시각 확인",
    "accessory": "선택 장신구의 형태·재질·부착점·후면·크기와 다른 자산 픽셀 혼입을 실제 시각 확인",
}
INSPECTION_LOCK = {
    "body": "BODY 제작 도중 완성 캐릭터 참고 이미지에 보이는 HAIR·OUTFIT·ACCESSORY를 복제하지 않는다. 민머리 완성 BODY만 납품",
    "hair": "HAIR 납품물에는 눈·얼굴·신체 색을 복사하지 않는다. 전체 캐릭터 합성은 previews에서만 가능",
    "outfit": "OUTFIT 납품물에는 피부·눈·얼굴·머리카락을 복사하지 않는다. 합성은 previews에서만 가능",
    "accessory": "ACCESSORY 납품물에는 피부·헤어·의복을 복사하지 않는다. 요청 소품 한 종류만",
}
# Commands are repaired at their real location, across ALL fourteen members.
ACTIVE_PREFIXES = (
    "- **모드별 실제 구도:**",
    "- **최종 시각 검수:**",
    "- **선화/채색 목표:**",
    "- 프레임:",
    "- 눈·얼굴:",
    "- 정면 얼굴 높이",
)

def is_full(mode: str) -> bool:
    return mode in {"live2d_full", "inochi2d_full", "3d"}


def line_replacement(line: str, mode: str, asset: str) -> str:
    if line.startswith("- **모드별 실제 구도:**"):
        return "- **모드별 실제 구도:** " + MODE_SOURCE[mode] + ". " + ASSET_TARGET[asset] + "."
    if line.startswith("- **최종 시각 검수:**"):
        return "- **최종 시각 검수:** " + RENDER_QUALITY[asset] + ". 증거 없으면 ART_QUALITY_UNVERIFIED."
    if line.startswith("- **선화/채색 목표:**") and asset != "body":
        return "- **선화/채색 목표:** " + RENDER_QUALITY[asset] + ". 예시의 완성 캐릭터 눈·몸을 그대로 복사하지 않는다."
    if line.startswith("- 프레임:"):
        return "- 프레임: " + MODE_SOURCE[mode] + ". " + ASSET_TARGET[asset] + "."
    if line.startswith("- 눈·얼굴:") and asset != "body":
        return "- 기준 얼굴 정합(참조만): " + REFERENCE_ONLY[asset] + ". 얼굴·눈 자체는 이 ZIP의 제작 항목이 아니다."
    if line.startswith("- 정면 얼굴 높이") and asset != "body":
        return "- 기준 얼굴 비율(참조만): " + REFERENCE_ONLY[asset] + ". 신체 6등신/머리 크기는 해당 자산 그림의 생성 명령이 아니다."
    if "전신 6등신 유지, 바스트업·상반신은" in line and not is_full(mode):
        return line.replace("전신 6등신 유지, 바스트업·상반신은", "전신 원화 신규 제작 금지, 바스트업·상반신은")
    if (asset != "body" and not is_full(mode)
            and "전신 캐릭터" in line and "6등신" in line
            and "금지" not in line):
        return re.sub(r"전신 캐릭터.{0,110}?6등신.{0,55}?(?=[.。]|$)", "기준 BODY의 기존 비율을 참조하고 전신 캐릭터를 새로 만들지 않는다", line)
    return line


def repair(text: str, mode: str, asset: str) -> tuple[str, int]:
    lines = text.splitlines(keepends=True)
    count = 0
    new = []
    for line in lines:
        content = line.rstrip("\r\n")
        ending = line[len(content):]
        # Remove other asset's actionable checklists from every ZIP.
        checklist = re.match(r"^-\s*\[\s*[xX ]?\s*\]\s*(BODY|HAIR|OUTFIT|ACCESSORY)\s*:", content)
        if checklist and checklist.group(1).lower() != asset:
            count += 1
            continue
        # A bustup/upper BODY must not include the full-body part-card row
        # at all: conditional wording still causes unintended legs in image AI.
        if (asset == "body" and not is_full(mode)
                and content.lstrip().startswith("| pelvis / thigh.left/right")):
            count += 1
            continue
        ending = line[len(content):]
        updated = line_replacement(content, mode, asset)
        if updated != content:
            count += 1
        new.append(updated + ending)
    result = "".join(new)
    # The source-only contract is already first. Tighten its active asset
    # declaration WITHOUT stacking another global override paragraph.
    marker = "- 자산 경계: "
    # Stable two-line gate is inserted next to the REAL asset definition
    # in every one of the 14 ZIP documents. No accumulating appendages.
    entries = [line for line in result.splitlines(keepends=True)
               if not line.startswith(("- 명시적 생성 제외:", "- 실물 납품 차단:"))]
    for i, line in enumerate(entries):
        if line.startswith(marker) and i < 10:
            old = line.rstrip("\r\n")
            expected = "- 자산 경계: " + ASSET_TARGET[asset] + ". " + INSPECTION_LOCK[asset] + "."
            if old != expected:
                entries[i] = expected + line[len(old):]
                count += 1
            entries[i+1:i+1] = [
                "- 명시적 생성 제외: " + ASSET_EXCLUDE[asset] + ".\n",
                "- 실물 납품 차단: " + ASSET_REJECT[asset] + ".\n",
            ]
            break
    else:
        raise ValueError("asset boundary not in first section")
    updated = "".join(entries)
    if updated != result:
        count += 1
    result = updated
    # Ref/reference descriptions are not new layers: this exact confusion
    # made the completed-character illustration contaminate BODY output.
    if mode == "live2d_bust_up" and asset == "body":
        bad = "머리부터 발끝까지 전신을 생성한다"
        if bad in result:
            result = result.replace(bad, "머리부터 상복부와 양손 끝까지만 생성한다")
            count += 1
    return result, count


def validate_member(s: str, mode: str, asset: str, name: str) -> None:
    header = s.split("## [/ART_SOURCE_AND_SEPARATION_V3]", 1)[0]
    if s.count("## [ART_SOURCE_AND_SEPARATION_V3]") != 1:
        raise ValueError((mode, asset, name, "stage count"))
    if "- 자산 경계: " + ASSET_TARGET[asset] not in header:
        raise ValueError((mode, asset, name, "asset boundary not fixed"))
    if (header.count("- 명시적 생성 제외: " + ASSET_EXCLUDE[asset]) != 1
            or header.count("- 실물 납품 차단: " + ASSET_REJECT[asset]) != 1):
        raise ValueError((mode, asset, name, "missing explicit negative output contract"))
    if mode != "3d" and s.count("## [IMAGE_AI_SOURCE_ONLY_V2]") != 1:
        raise ValueError((mode, asset, name, "image stage marker"))
    for line in s.splitlines():
        other_check = re.match(r"^-\s*\[\s*[xX ]?\s*\]\s*(BODY|HAIR|OUTFIT|ACCESSORY)\s*:", line)
        if other_check and other_check.group(1).lower() != asset:
            raise ValueError((mode, asset, name, "other asset acceptance checklist"))
        if (asset == "body" and not is_full(mode)
                and line.lstrip().startswith("| pelvis / thigh.left/right")):
            raise ValueError((mode, asset, name, "full-body part row inside upper scope"))
        if line.startswith("- **모드별 실제 구도:**") and (
            MODE_SOURCE[mode] not in line or ASSET_TARGET[asset] not in line
        ):
            raise ValueError((mode, asset, name, "shared human pose in another asset"))
        if line.startswith("- **최종 시각 검수:**") and RENDER_QUALITY[asset] not in line:
            raise ValueError((mode, asset, name, "shared face inspection in another asset"))
        if line.startswith("- 프레임:") and ASSET_TARGET[asset] not in line:
            raise ValueError((mode, asset, name, "frame reintroduces other asset"))
        if asset != "body" and line.startswith("- 눈·얼굴:"):
            raise ValueError((mode, asset, name, "face drawing text in nonbody"))
        if asset != "body" and line.startswith("- 정면 얼굴 높이"):
            raise ValueError((mode, asset, name, "face generation ratio in nonbody"))
    if mode == "live2d_bust_up" and asset == "body" and (
        "골반·다리 금지" not in header
    ):
        raise ValueError((mode, asset, name, "bustup range not locked"))


def run(root: Path, *, check: bool, report: Path | None):
    results = []
    for mode in MODES:
        for asset in ASSETS:
            path = root / (mode + "__" + asset + ".zip")
            with ZipFile(path) as z:
                infos = z.infolist()
                if len(infos) != DOC_COUNT or len({i.filename for i in infos}) != DOC_COUNT or z.testzip():
                    raise ValueError(("invalid zip", path))
                before = {i.filename:z.read(i.filename) for i in infos}
            new = {}
            edits = {}
            for info in infos:
                data = before[info.filename]
                s = data.decode("utf-8")
                if check:
                    fixed, changes = repair(s, mode, asset)
                    if fixed != s:
                        raise ValueError(("uncommitted asset scope repair",path,info.filename,changes))
                else:
                    s, changes = repair(s, mode, asset)
                validate_member(s, mode, asset, info.filename)
                edits[info.filename] = changes
                new[info.filename] = s.encode("utf-8")
            if not check and before != new:
                tmp = path.with_suffix(".new")
                with ZipFile(tmp, "w", ZIP_STORED) as dst:
                    for info in infos:
                        dst.writestr(info, new[info.filename])
                with ZipFile(tmp) as z:
                    if z.testzip() is not None:
                        raise ValueError(("CRC failure", path))
                tmp.replace(path)
            results.append({"kit":mode+"__"+asset,"mode":mode,"asset":asset,
                            "members":len(new),"changed_lines":sum(edits.values()),
                            "edits_by_doc":edits,
                            "asset_boundary":ASSET_TARGET[asset],
                            "allowed_scope":MODE_SOURCE[mode]})
            print("PASS",mode+"__"+asset,"14 docs","modified lines",sum(edits.values()))
    total=sum(x["changed_lines"] for x in results)
    print("AUDIT PASS: 24 ZIP / 336 MD; updated lines",total)
    if report:
        report.parent.mkdir(parents=True,exist_ok=True)
        report.write_text(json.dumps({"kits":results,"total":24,"documents":336,"changes":total},
                          ensure_ascii=False,indent=2),encoding="utf-8")


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",type=Path,default=ROOT)
    p.add_argument("--check",action="store_true")
    p.add_argument("--report",type=Path)
    a=p.parse_args()
    run(a.root,check=a.check,report=a.report)

if __name__ == "__main__":
    main()
