"""Reconcile Live2D bustup BODY, PSD handoff and archived 14 MD."""
from pathlib import Path
from zipfile import ZipFile
import argparse, json, re, os, tempfile
ROOT=Path(__file__).resolve().parents[1]
KIT=ROOT/"docs/image_ai_kits_v2"
ASSETS=("body","hair","outfit","accessory")
MARK="## [BUSTUP_COMPLETE_BODY_FINAL_PSD_V4]"
BAD=re.compile(r"52\s*[~–-]\s*61\s*%|1[.]65\s*[~–-]\s*1[.]95\s*H|FACE-DOMINANT CLOSE BUST-UP|no elbows or hands|no waist and no elbows|허리·긴 몸통·팔꿈치·손은 그리지|팔꿈치·손은 그리지|단색 중립 BODY 실루엣|프록시 제작 코드 실행|프록시 윗부분만|코드로 만든.*단색|도형.*프록시로 조립|얼굴 중심 근접 바스트업|불투명 단색 실루엣|중립색 몸통 도형|도형 생성 코드를 정상 사용|도형.*정식 생성|목 아래.*도형 생성|회색.*마네킹.*정상",re.I)
DELIVERY=("실제 다층 PSD, 같은 캔버스 투명 RGBA PNG와 파츠별 알파 마스크, 원본 입력과 원본 PSD(있다면), "
          "원본-결과 및 PRO BODY 정합 미리보기, 레이어 좌표/순서·검증·분할 JSON, 사용자 제작·시각검수·Cubism 안내 MD는 최종 필수. "
          "PSD와 마스크가 없으면 중간 PNG 검사 PASS여도 최종 납품 불가. "
          "BODY 최종 납품에 --final-live2d-body를 사용한다. HAIR/OUTFIT/ACCESSORY도 PSD·마스크 필수. "
          "실제 이미지/Editor 확인 없이 미술·리깅 품질 PASS 금지.")

def scrub(value,name):
    if name=="04_OUTPUT_FILES.md":return value
    out=[]
    for line in value.splitlines():
        if not BAD.search(line):out.append(line)
    return "\n".join(out).rstrip()+"\n"

def rewrite_zip(asset,spec,geo,craft,write):
    path=KIT/"zips"/f"live2d_bust_up__{asset}.zip"
    with ZipFile(path) as archive:
        infos=archive.infolist()
        if len(infos)!=14 or len(set(i.filename for i in infos))!=14 or archive.testzip():
            raise ValueError("Invalid 14 MD ZIP: "+path.name)
        original={i.filename:archive.read(i.filename).decode("utf-8") for i in infos}
    changed={}
    for name,content in original.items():
        if asset=="body" and name=="02_ADVANCED_PARTS.md" and MARK not in content:
            content=re.sub(r"### 중립 몸체 프록시 실행 예시.*?(?=\n(?:##|###) |\Z)","",content,flags=re.S)
            content=re.sub(r"\x60\x60\x60python[^\x60]*from PIL import Image, ImageDraw[^\x60]*\x60\x60\x60","",content,flags=re.S)
        if name=="05_OFFICIAL_REFERENCES.md":
            changed[name]=content  # exact engine-specific official reference; never append to it
            continue
        required=spec["short_scope"][asset]+"\n"+DELIVERY
        if asset=="body":required+="\n"+spec["body_visual_qa"]
        if name=="02_ADVANCED_PARTS.md" and asset=="body":
            required+="\n"+spec["body_face"]
        if name=="03_MODE_RULES.md":
            if asset!="body":required+="\n기준 신체 참조 — 해당 자산만 독립 제작한다."
            required+="\n"+geo["modes"]["live2d_bust_up"]+"\n"+craft["modes"]["live2d_bust_up"]
        if name=="10_ANIME_STYLE.md":
            required+="\n"+(spec["image_prompt_body"] if asset=="body" else spec["image_prompt_other"][asset])
        if content.count(MARK)==1:
            if required not in content:raise ValueError("Stale v4 "+path.name+"/"+name)
            changed[name]=content
        elif MARK in content:
            raise ValueError("Duplicate v4 marker")
        else:
            changed[name]=scrub(content,name).rstrip()+"\n\n"+MARK+"\n"+required+"\n"
        if "no elbows or hands" in changed[name]:raise ValueError("Old hand omission instruction")
    if changed==original:return False
    if not write:raise ValueError("Unreconciled "+path.name)
    temp=None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent,suffix=".zip",prefix="bustup-v4-",delete=False) as handle:
            temp=Path(handle.name)
        with ZipFile(temp,"w") as z:
            for i in infos:z.writestr(i,changed[i.filename].encode("utf-8"))
        with ZipFile(temp) as z:
            if z.testzip() or z.namelist()!=list(changed):raise ValueError("Rebuilt ZIP invalid")
        os.replace(temp,path);temp=None
    finally:
        if temp:temp.unlink(missing_ok=True)
    return True

def rewrite_sources(spec,geo,write):
    names=("BODY_2D.md","MODE_2D.md","QUALITY_STANDARD_2D.md","ANIME_VTUBER_STYLE_2D.md")
    snap=KIT/"builder_inputs/2D.json"
    values=json.loads(snap.read_text(encoding="utf-8"))
    for name in names:
        path=KIT/"source"/name
        original=path.read_text(encoding="utf-8")
        if MARK in original:changed=original
        else:
            changed=scrub(original,name)
            if name=="BODY_2D.md":
                changed=re.sub(r"## \[2026-10-13\] 사용자 승인 얼굴/몸체 제작 분리.*?(?=\n## |\Z)","",changed,flags=re.S)
            if name=="MODE_2D.md":
                changed=re.sub(r"## \[바스트업 얼굴 우선 프레이밍.*?(?=\n## |\Z)","",changed,flags=re.S)
            changed+="\n"+MARK+"\n"+geo["modes"]["live2d_bust_up"]+"\n"+spec["body_face"]+"\n"+spec["body_visual_qa"]+"\n"+spec["image_prompt_body"]+"\n"
        if changed!=original:
            if not write:raise ValueError("Unreconciled source "+name)
            path.write_text(changed,encoding="utf-8")
        if name in values:
            values[name]=changed
    data=json.dumps(values,ensure_ascii=False,indent=2)+"\n"
    if snap.read_text(encoding="utf-8")!=data:
        if not write:raise ValueError("Unreconciled builder snapshot")
        snap.write_text(data,encoding="utf-8")

def main():
    parser=argparse.ArgumentParser()
    exclusive=parser.add_mutually_exclusive_group(required=True)
    exclusive.add_argument("--write",action="store_true")
    exclusive.add_argument("--check",action="store_true")
    options=parser.parse_args()
    spec=json.loads((KIT/"source/BUST_UP_FACE_FIRST_CONTRACT.json").read_text())
    geo=json.loads((KIT/"source/FACE_NECK_GEOMETRY_GUIDANCE.json").read_text())
    craft=json.loads((KIT/"source/ADVANCED_ARTWORK_CRAFT_GUIDANCE.json").read_text())
    rewrite_sources(spec,geo,options.write)
    n=sum(rewrite_zip(a,spec,geo,craft,options.write) for a in ASSETS)
    print(f"PASS: 4 canonical 14-MD ZIPs, updated={n}, final PSD/masks contract")
if __name__=="__main__":main()
