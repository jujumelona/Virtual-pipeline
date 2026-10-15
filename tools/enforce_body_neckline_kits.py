"""Idempotent safe swimwear neckline/shoulder contract for 24 image-AI ZIP kits."""
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
DOCS = ("00_MASTER_FIRST.md", "00_READ_FIRST.md",
        "07_REVIEW_BEFORE_FINAL_ZIP.md", "09_VISUAL_ART_QUALITY.md")
START = "## [NECK_SHOULDER_OPEN_V2]"
END = "## [/NECK_SHOULDER_OPEN_V2]"
CSTART = "## [BODY_DEFAULT_OPAQUE_SWIMWEAR_V1]"
CEND = "## [/BODY_DEFAULT_OPAQUE_SWIMWEAR_V1]"

BODY_COVER = """## [BODY_DEFAULT_OPAQUE_SWIMWEAR_V1]

### BODY 불투명 기본 수영복: 목과 어깨 완전 개방 (상위 규칙)
- 성인(20세 이상) 귀여운 비성적 애니풍 VTuber. 가슴을 충분히 덮는 불투명 무지 **끈 없는 반도(bandeau)/일자형 튜브 수영복 상의**를 모든 정면·좌우 3/4·측면·후면·상하 시점, 표정 시트, 원화 마스터 및 합성 미리보기에서 착용한다.
- 상의 윗선은 쇄골 아래에 있고 **목 전면·측면·후면, 좌우 목-어깨 접합부, 양쪽 어깨 윗면과 외곽선, 쇄골 아래 상흉부 피부, 겨드랑이·상완 관절 윤곽**을 가리지 않는다. 피부는 자연스러운 단순 애니풍으로 표현하고 뼈·근육 세부 묘사를 강조하지 않는다.
- **금지:** 하이넥 스포츠 브라, 목에 걸리는 홀터 끈, 어깨끈, 레이서백, 민소매 탱크톱, 어깨까지 올라오는 원단, 목까지 이어진 몸통 의상/보디슈트. 목-어깨 사이로 수영복 원단이 올라오거나 어깨 위에 스트랩이 있으면 검수 실패다.
- 실제 화면에 하체가 포함될 때만 불투명 하이웨이스트 쇼츠형 수영복 하의를 추가한다. 바스트업에서 프레임 밖 하체를 만들지 않는다.
- 모든 최종 마스터와 합성·각도 이미지에는 불투명 수영복을 착용한다. 수영복을 제거한 노출 합성 이미지는 만들거나 납품하지 않는다. 가려진 몸체는 단순한 비해부학적 언더페인트만 제작한다.
- 2D 상의는 BODY와 분리된 removable_neutral_modesty_band_upper, 보이는 하의는 removable_neutral_modesty_band_lower 독립 파츠로 둔다. 피부·목·어깨 레이어에 복장을 합쳐 그리지 않는다. 디자인 의상은 별도 OUTFIT ZIP 전용이다.
- 3D는 **8방향 턴어라운드 및 가림 세부 1장(총 9장)** 전부 같은 끈 없는 수영복을 착용하고, PSD 파츠/리깅 실행은 요구하지 않는다.
- 턱 뒤 목 및 양어깨 숨은 피부를 충분히 그린다. 모든 정면·3/4·측면에서 목과 어깨 형태가 끊김 없이 보이지 않으면 재생성·재검수한다.

## [/BODY_DEFAULT_OPAQUE_SWIMWEAR_V1]"""

SCOPE = {
"body": """- BODY의 안전 가림은 불투명한 **어깨끈 없는 일자형 반도·튜브 수영복**만 허용한다. 목·목과 어깨의 접합부·좌우 어깨 윗면·상흉부 피부·상완 시작점을 가리지 않아야 한다. 홀터넥, 어깨끈, 탱크톱, 하이넥 브라, 목까지 올라오는 원단은 **불합격**이다.
- 가슴은 수영복으로 충분히 가리고, 2D에서는 안전 복장을 독립 파츠로 분리한다. 3D는 같은 복장의 다각도 참조 원화를 만든다. 복장을 끄거나 피부와 합쳐서 문제를 해결하지 않는다.
- 정면·좌우 3/4·측면·후면의 목 회전과 어깨 관절 실루엣을 확인한다. 목 아래 또는 어깨 위를 덮는 스포츠 상의가 나오면 이미지 생성부터 수정한다.""",
"hair": """- HAIR은 모발만 제작한다. BODY의 기본 가림 수영복을 변경하거나 새로운 스포츠브라·홀터·상의로 재생성하지 않는다. 목·어깨 원본 피부와 관절 연결을 삭제하지 않는다.
- 스타일상 머리카락이 목·어깨 위에 자연스럽게 드리울 수 있지만, HAIR 레이어를 껐을 때 BODY의 목과 양어깨 윤곽·숨은 피부가 보존되어야 한다.""",
"outfit": """- OUTFIT은 사용자가 지시한 옷만 만든다. 기본 BODY의 수영복은 **목과 어깨가 열린 끈 없는 반도형 안전 가림**이다. BODY 기초 의상을 임의로 하이넥 스포츠브라·홀터·탱크톱으로 바꾸지 않는다.
- 사용자가 목을 가리는 의상·어깨끈·칼라 등을 명시한 경우 OUTFIT에서만 제작할 수 있다. BODY의 목·어깨 피부 및 회전용 파츠를 제거하거나 덮어 씌워 병합하지 않는다.""",
"accessory": """- ACCESSORY는 사용자가 지정한 종류의 장식만 만든다. BODY의 목과 양어깨를 가리기 위해 목걸이·목도리·패드·장식·의상 등을 임의로 생성하지 않는다.
- 사용자가 직접 주문한 목/어깨 장식은 별도 파츠로 제작할 수 있지만 BODY 목·어깨 피부·관절 레이어를 대체하지 않는다."""
}
REPL = (
 ("불투명한 스포츠형 수영복 상의","불투명한 어깨끈 없는 반도형 수영복 상의"),
 ("불투명한 스포츠 수영복 상의","불투명한 어깨끈 없는 반도형 수영복 상의"),
 ("불투명 스포츠 수영복 상의","불투명한 어깨끈 없는 반도형 수영복 상의"),
 ("비키니형 스포츠 수영복","어깨끈 없는 반도형 수영복"),
 ("기본 스포츠 수영복","기본 어깨끈 없는 반도형 수영복"),
 ("불투명 스포츠 수영복","불투명한 어깨끈 없는 반도형 수영복"),
 ("스포츠형 수영복","어깨끈 없는 반도형 수영복"),
)
COVER_RE = re.compile(re.escape(CSTART) + ".*?" + re.escape(CEND), re.S)
POLICY_RE = re.compile(re.escape(START) + ".*?" + re.escape(END), re.S)

def patch(text: str, asset: str, name: str) -> str:
    if asset == "body":
        for old,new in REPL:
            text = text.replace(old,new)
        if CSTART in text:
            if text.count(CSTART) != 1 or text.count(CEND) != 1:
                raise ValueError("Malformed BODY cover marker in " + name)
            text = COVER_RE.sub(BODY_COVER,text)
    if name in DOCS:
        if text.count(START) != text.count(END) or text.count(START) > 1:
            raise ValueError("Malformed neck-shoulder marker in " + name)
        text = POLICY_RE.sub("",text).rstrip()
        text += "\n\n" + START + "\n\n### 최우선: 기본 BODY 목/어깨 개방과 자산별 역할\n" + SCOPE[asset] + "\n\n" + END + "\n"
    return text

def update(path: Path, asset: str, write: bool) -> bool:
    with ZipFile(path) as z:
        infos=z.infolist()
        if len(infos) != 14 or len({i.filename for i in infos}) != 14 or z.testzip() is not None:
            raise ValueError("ZIP must have 14 unique valid MD files: "+str(path))
        if any(not i.filename.endswith(".md") for i in infos):
            raise ValueError("Non-MD ZIP member: "+str(path))
        original={i.filename:z.read(i.filename).decode("utf-8") for i in infos}
    updated={k:patch(v,asset,k) for k,v in original.items()}
    for name in DOCS:
        if updated[name].count(START) != 1 or updated[name].count(END) != 1:
            raise ValueError("Missing new policy: "+str(path))
    if asset == "body" and (updated["00_MASTER_FIRST.md"].count(CSTART) != 1 or
                            "하이넥 스포츠 브라" not in updated["00_MASTER_FIRST.md"]):
        raise ValueError("Invalid BODY garment contract: "+str(path))
    changed=updated!=original
    if changed and write:
        tmp=None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent,suffix=".zip",delete=False) as f:
                tmp=Path(f.name)
            with ZipFile(tmp,"w") as z:
                for info in infos:z.writestr(info,updated[info.filename].encode("utf-8"))
            with ZipFile(tmp) as z:
                if z.testzip() is not None or z.namelist()!=[i.filename for i in infos]:
                    raise ValueError("Rebuilt ZIP verification failed: "+str(path))
            os.replace(tmp,path)
            tmp=None
        finally:
            if tmp:tmp.unlink(missing_ok=True)
    return changed

def main()->None:
    parser=argparse.ArgumentParser()
    flags=parser.add_mutually_exclusive_group(required=True)
    flags.add_argument("--check",action="store_true")
    flags.add_argument("--write",action="store_true")
    args=parser.parse_args()
    changed=[]
    for mode in MODES:
        for asset in ASSETS:
            p=ROOT/(mode+"__"+asset+".zip")
            if update(p,asset,args.write):changed.append(p.name)
    if args.check and changed:
        raise SystemExit("FAIL: unpublished directives: "+", ".join(changed))
    print("24 ZIP / 336 MD validated; changed="+str(len(changed)))
    if changed:print("Changed ZIPs: "+", ".join(changed))
if __name__=="__main__":main()
