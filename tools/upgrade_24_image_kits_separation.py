"""Migrate all 24 original art instruction ZIPs to master-first, specialist-separation flow."""
from pathlib import Path
from zipfile import ZipFile, ZIP_STORED
import argparse, re

ROOT=Path(__file__).resolve().parents[1]/"docs/image_ai_kits_v2/zips"
MODES=("live2d_bust_up","live2d_upper","live2d_full","inochi2d_upper","inochi2d_full","3d")
ASSETS=("body","hair","outfit","accessory")
EXPECTED={"00_MASTER_FIRST.md","00_DELIVERY_AND_RECHECK.md","00_READ_FIRST.md",
"01_COMMON_RULES.md","02_ADVANCED_PARTS.md","03_MODE_RULES.md","04_OUTPUT_FILES.md",
"05_OFFICIAL_REFERENCES.md","06_ADVANCED_OFFICIAL_COMMUNITY.md",
"07_REVIEW_BEFORE_FINAL_ZIP.md","08_PRACTICAL_TIPS.md","09_VISUAL_ART_QUALITY.md",
"10_ANIME_STYLE.md","11_OFFICIAL_IMAGE_EXAMPLES.md"}
SCOPE={
"live2d_bust_up":"바스트업은 얼굴과 큰 눈이 화면 중심, 머리부터 상복부, 양어깨·상완·전완·양손 끝까지. 골반·다리 금지.",
"live2d_upper":"상반신은 머리부터 허리 부근, 양팔·양손 끝까지. 다리·발 금지.",
"live2d_full":"전신은 정수리에서 양발 발끝까지, 양팔·손·양다리·발 포함. 프로젝트 6등신 기준.",
"inochi2d_upper":"Inochi2D 상반신은 머리부터 허리, 양팔·손 포함. 다리 금지. Inochi2D 독립 노드 준비.",
"inochi2d_full":"Inochi2D 전신은 머리부터 발끝까지, 양팔·손·양다리·발 포함. Inochi2D 독립 노드 준비.",
"3d":"3D: 전/후/좌/우 및 네 대각, 동일 캐릭터 8방향 참조와 가림 세부. 2D PSD·파츠 PNG 요구 금지."
}
OWN={
"body":"신체 전용. 피부색을 얼굴·귀·목·몸통 무광 비해부학 외피·어깨·양팔·손 전체에서 같은 실제 HEX로 통일. 큰 애니 눈과 짧은 부드러운 턱. 헤어·패션 의상·액세서리 픽셀 금지. 전신에서만 다리·발 추가. 가슴·복근·배꼽 해부학적 강조 금지.",
"hair":"헤어 전용. 승인 BODY는 배치 참조만. 실제 납품 픽셀은 앞머리·뒷머리·좌우 옆머리·움직임 있는 긴 묶음과 잔머리뿐. 얼굴·눈·의복·장신구 픽셀 금지.",
"outfit":"의상 전용. 승인 BODY는 배치 참조만. 앞뒤 천·좌우 소매·옷깃·리본·밑단 및 실제 있는 치마만. 피부·눈·헤어·별도 액세서리 픽셀 금지.",
"accessory":"액세서리 전용. 실제 주문된 장신구 한 종류만. 고정부·좌우 부착점·움직이는 날개와 가려진 부분만. 헤어·옷·신체 픽셀과 임의 장신구 세트 금지."
}
CUT={
"body":"""BODY 필수: 얼굴 바탕(눈·입·귀를 구워 넣지 않음), 귀·눈썹 L/R, 코, 닫힌 입·열린 입안, 목·몸통·상완·전완·손 L/R. 전신만 다리와 발. 양쪽 눈은 각각 eye_L_white, eye_L_iris, eye_L_upper_lash 및 right 대응 세 독립 RGBA 레이어가 필수. 필요할 때 동공·하이라이트·눈꺼풀·아랫속눈썹 추가. eyes라는 한 장짜리 영역·눈 통째 추출·같은 텍스처를 세 파일명으로 복제한 결과는 실패. 홍채 뒤 가려진 흰자까지 실제 픽셀로 보완하고 시선 이동·눈 깜빡임·입 열고 닫기 상태를 각각 합성 검증한다. 실패 시 EYE_MICRO_SPLIT_UNRESOLVED로 차단 후 정밀 마스크 또는 수동 가공. 목 상단은 턱 뒤, 하단은 몸통 아래까지. 어깨·팔꿈치·손목 숨은 면 복원. 얼굴-목-몸통-손 피부색 통일.""",
"hair":"HAIR: 앞머리·뒷머리·좌우 옆머리·독립으로 흔들리는 가닥과 묶음머리만 필요한 만큼 분리. 숨은 뿌리/뒷모발을 보완. 전체 머리카락 한 장 coarse 마스크는 파츠 분리 성공이 아니다.",
"outfit":"OUTFIT: 앞뒤 몸판·좌우 소매·독립 이동하는 칼라/리본/밑단·치맛자락을 필요한 경우 나눈다. 봉제선·무늬는 본래 천에 유지. 감춰진 겹침면 색 복원, 피부·헤어 픽셀 혼입 금지.",
"accessory":"ACCESSORY: 실제 요청된 한 장신구의 운동/가림 단위로 분리. 고정 머리핀은 한 레이어 허용, 좌우 귀걸이·안경 다리·움직이는 리본 날개는 별도. 붙어 있는 신체·헤어·옷 픽셀 혼입 금지."
}
def contract(mode,asset):
    h=f"## [ART_SOURCE_AND_SEPARATION_V3]\n### {mode} / {asset} — 자산·모드·담당 단계 잠금\n- 자산 경계: {OWN[asset]}\n- 구도 경계: {SCOPE[mode]}\n"
    if mode=="3d":
        return h+"""- 이미지 생성 AI는 실제 8방향 원화 및 가림 참조만 생성. 정면 복사/미러링으로 방향을 위조하지 않는다.
- 3D 메시/UV/텍스처 분해/리깅은 후속 모델링 단계다. 2D 눈·머리카락 RGBA 분리나 PSD2Live를 3D 제작 조건으로 넣지 않는다.
## [/ART_SOURCE_AND_SEPARATION_V3]"""
    return h+f"""종전 ONE_PART_PER_GENERATION_V1 직접 파츠 생성 지시는 폐기. 생성 AI와 분리 AI는 서로 다른 작업이다.

A. 이미지 생성 AI: 승인된 캐릭터의 고품질 해당 자산 원화 outputs/master.png를 먼저 그린다. 일관된 정면/좌우 3/4/측면 및 필요한 가림·표정 reference_views/ 와 expression_refs/를 그림으로 만든다. 참조용 다른 자산 픽셀은 실제 master에 넣지 않는다. 캐릭터 시트/콜라주/레이어명이 붙은 눈 그림을 독립 파츠로 위장 금지. 눈·모발·옷의 한 조각씩 재생성하지 않는다. 이 단계에서는 part_art/*.png, part_art/_order.txt, PSD, 실제 리깅 성공을 주장하지 않는다.

B. 전문 분리·원화 가공 단계: 기존 계층형 PSD가 있으면 원본 레이어 우선. 단일 원화면 See-through/LayerDiff 및 SemanticSam 19개 클래스는 큰 영역 후보일 뿐이다. SemanticSam의 eyes는 좌우·흰자·홍채·속눈썹 개별 레이어가 **아니다**. 고해상도 해당 부위 crop을 이용하고 박스/클릭/거친 마스크 안내로 SAM2류 정밀 분리 또는 별도 전용 소재 분리 가공과 수동 수정이 필요하다. 무검수 완전 자동 가능하다고 주장하지 않는다. 눈을 새 그림으로 재생성하지 말고 보이는 RGB 픽셀을 마스터에서 정확히 복사한다. 숨겨진 부분만 참고 원화에 맞춰 연장 작화·인페인팅한다. 같은 전체 캔버스 좌표·원점/좌우/레이어 순서로 보정하고, 분리 검증 후에만 part_art/*.png와 part_art/_order.txt를 납품한다.

C. {asset} 실제 세분화 판단: {CUT[asset]}

D. 검사/실패 처분: 합성한 중립 이미지가 마스터와 일치하는지, 눈 흰자·홍채를 단독 표시했을 때 중복 눈이 아닌지, 투명 구멍·접합선·가림 뒤 색 누락이 없는지 확인. 레이어 이름/PNG 숫자/SAM 마스크 출력만으로 성공 처리하지 않는다. 미완료는 EYE_MICRO_SPLIT_UNRESOLVED, UNDERPAINT_MISSING, SOURCE_PIXEL_MISMATCH, PART_ALPHA_INVALID 중 해당 원인으로 보류하고 같은 생성 AI에 다시 파츠 시트를 그리라고 보내지 않는다. PSD/Live2D/Inochi2D 리깅과 측면 키폼 성공은 후속 단계에서 따로 검증한다.
- 근거: https://docs.live2d.com/ko/cubism-editor-tutorials/psd/ ; https://docs.live2d.com/ko/cubism-editor-manual/divide-the-material/ ; https://github.com/shitagaki-lab/see-through ; https://ai.meta.com/research/sam2/
## [/ART_SOURCE_AND_SEPARATION_V3]"""
def edit(data,mode,asset,name):
    t=data.decode("utf-8-sig")
    t=re.sub(r"## \[ART_SOURCE_AND_SEPARATION_V3\].*?## \[/ART_SOURCE_AND_SEPARATION_V3\]\s*","",t,flags=re.S)
    if mode!="3d":
        p=r"## \[IMAGE_AI_SOURCE_ONLY_V2\].*?## \[/IMAGE_AI_SOURCE_ONLY_V2\]"
        if len(re.findall(p,t,flags=re.S))!=1:raise ValueError(("V2 block",mode,asset,name))
        v="""## [IMAGE_AI_SOURCE_ONLY_V2]
예전 ONE_PART_PER_GENERATION_V1 단일 파츠 그림 직접 생성 규칙은 폐기한다. ART_SOURCE_AND_SEPARATION_V3를 적용한다. 이미지 생성 AI는 outputs/master.png + reference_views를 납품한다. part_art/_order.txt는 전문 분리 단계에서만 작성.
## [/IMAGE_AI_SOURCE_ONLY_V2]"""
        t=re.sub(p,lambda m:v,t,flags=re.S)
        t=re.sub(r"실제 템플릿의 해당 슬롯과 마스터·직전 승인 파츠를 비교하면서.*?PSD·마스크·리깅은 후속 Colab이 담당한다\.",
            "생성 AI는 마스터와 각도/표정/가림 참고 원화를 완성하고 눈·모발·옷의 실제 RGBA 분리는 전용 후속 분리 담당이 한다.",t,flags=re.S)
        t=t.replace("**한 번의 이미지 생성/수정 요청 = 한 개의 실제 파츠 원화.**",
                    "**이미지 생성 AI는 완성 기준 원화 또는 가림 참조 한 장씩 작업; 실제 파츠는 별도 분리 단계 담당.**")
        t=t.replace("이미지 AI는 해당 부위를 포함한 독립 파츠 이미지를 한 번에 하나씩 편집하며",
                    "분리 전문가는 해당 부위의 원본 픽셀 마스크를 하나씩 보정하며")
        t=t.replace("04 — 이미지 생성 AI 개별 파츠 원화 납품",
                    "04 — 이미지 AI 마스터 및 전문 분리 AI 파츠 납품")
        t=t.replace("**양손 전체 필수:**","**양손 원화 필수(분리 PNG는 후속):**")
    return (contract(mode,asset)+"\n\n"+t.strip()+"\n").encode("utf8")
def main(root,check=False):
    count=0
    for mode in MODES:
      for asset in ASSETS:
        path=root/(mode+"__"+asset+".zip")
        with ZipFile(path) as z:
            infos=z.infolist()
            if len(infos)!=14 or {i.filename for i in infos}!=EXPECTED or z.testzip() is not None:raise ValueError(("bad ZIP",path))
            before={i.filename:z.read(i.filename) for i in infos}
        after=before if check else {n:edit(d,mode,asset,n) for n,d in before.items()}
        for n,d in after.items():
            s=d.decode("utf8")
            if not s.startswith("## [ART_SOURCE_AND_SEPARATION_V3]") or f"{mode} / {asset}" not in s[:180] or SCOPE[mode] not in s[:2000]:raise ValueError(("scope",path,n))
            if mode!="3d" and not all(w in s[:5000] for w in ("See-through","part_art/_order.txt","master.png","SemanticSam")):raise ValueError(("split handoff",path,n))
        if not check and before!=after:
            tmp=path.with_suffix(".tmp")
            with ZipFile(tmp,"w",compression=ZIP_STORED) as z:
                for i in infos:z.writestr(i.filename,after[i.filename])
            with ZipFile(tmp) as z:
                if z.testzip() is not None:raise ValueError(("write CRC",path))
            tmp.replace(path)
        count+=1
    print("PASS",count,"scoped ZIPs and",count*14,"MDs")
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--check",action="store_true");p.add_argument("--root",type=Path,default=ROOT);a=p.parse_args();main(a.root,a.check)
