"""Turn 24 image-model instruction ZIPs into source-art-only deliverables.

Do not ask the image model to cut sprites or author PSD/alpha masks. Keep the
published 14 document names and official visual-artwork references.
"""
from __future__ import annotations
import re

BEGIN = "## [IMAGE_AI_SOURCE_ONLY_V2]"
END = "## [/IMAGE_AI_SOURCE_ONLY_V2]"
VIEWS_2D = {
    "body": ("body_front", "head_three_quarter_L", "head_three_quarter_R",
             "head_profile_L", "head_profile_R", "head_pitch_up",
             "head_pitch_down", "neck_underpaint", "body_joint_overlaps"),
    "hair": ("hair_front", "hair_three_quarter_L", "hair_three_quarter_R",
             "hair_profile_L", "hair_profile_R", "hair_back",
             "hair_underlayers", "hair_motion_clearance"),
    "outfit": ("outfit_front", "outfit_three_quarter_L", "outfit_three_quarter_R",
               "outfit_profile_L", "outfit_profile_R", "outfit_back",
               "outfit_inside_seams", "outfit_joint_clearance"),
    "accessory": ("accessory_front", "accessory_three_quarter_L",
                  "accessory_three_quarter_R", "accessory_profile_L",
                  "accessory_profile_R", "accessory_back",
                  "accessory_attachment_anchor", "accessory_occlusion"),
}
VIEWS_3D = ("front", "front_three_quarter_L", "left", "back_three_quarter_L",
            "back", "back_three_quarter_R", "right", "front_three_quarter_R",
            "detail_occlusion")
AUTHORING_OUTPUT = re.compile(
    r"파츠|독립\s*(?:PNG|레이어|부위)|분리|분할|PSD|"
    r"마스크|마스킹|리깅|메쉬|레이어(?:\s*순서|\s*구조|\s*작성|\s*이름)|"
    r"isolated_parts|layer_order|underpaint_parts|ArtMesh|Cubism|MOC3|"
    r"알파\s*(?:마스크|PNG|채널)|See-through(?:\s*분리|\s*실행)",
    re.IGNORECASE,
)

def source_contract(mode: str, asset: str) -> str:
    backtick = chr(96)
    if mode == "3d":
        deliver = (
            "- 결과 ZIP: views/" + asset + "_front.png, views/" + asset + "_front_three_quarter_L.png 등 "
            "8방향 개별 원화와 views/" + asset + "_detail_occlusion.png 총 9장. "
            "각도·캐릭터 동일성과 가림 실루엣을 지킨다."
        )
    else:
        deliver = (
            "- 결과 ZIP: outputs/master.png 한 장과 다음 실제 시점 그림: "
            + ", ".join("reference_views/" + v + ".png" for v in VIEWS_2D[asset])
            + ". 필요한 경우 expression_refs/에 완성된 표정 참고 PNG를 더한다."
        )
    if mode != "3d" and asset == "body":
        # Complete expression reference drawings are allowed; PSD/raster
        # segmentation and reusable oral overlays belong to Colab, not AI.
        deliver += (
            " - BODY의 입은 닫힘/벌림을 각각 실제로 그린 "
            "expression_refs/mouth_closed.png 및 "
            "expression_refs/mouth_open.png도 생성한다. 열린 입에는 "
            "입안의 어두운 공간·윗니·혀가 실제로 구별되게 보이고, "
            "다른 얼굴과 위치·선화·색조가 일치해야 한다. "
            "이 둘은 상태별 완성 참고 원화이며 PSD 레이어/마스크가 아니다."
        )
    joint = {
        "body": (
            "- 목·턱·좌우 어깨·상완·전완·손의 실루엣을 시점마다 정합되게 그린다. "
            "단색 무광 찰흙형 비해부학 BODY를 유지한다. neck_underpaint와 "
            "body_joint_overlaps는 **부품이 아니라 목·턱·몸통·어깨의 "
            "가림·연결을 설명하는 완성 참고 그림**이다. "
            "정면·좌우 3/4·측면에서 턱 아래 목과 귀 뒤, 목-어깨 접점을 보여준다. "
            "정면 그림을 늘이거나 머리만 좌우 이동해 옆모습으로 속이지 않는다."
        ),
        "hair": "- 모발의 뒷면·모근 및 두상 각도 관계를 참고 원화로 명확하게 그린다.",
        "outfit": "- 옷깃·소매·안감·등 뒤 겹침을 참고 시점 그림으로 보여준다.",
        "accessory": "- 소품 부착점과 가려진 뒷면을 참고 시점 그림으로 보여준다.",
    }[asset]
    handoff = ("3D 결과는 이후의 3D 제작 단계에서 처리한다."
               if mode == "3d" else
               "후속 Colab에서 실제 PNG 픽셀과 레이어 순서를 확인하여 PSD를 만들고 "
               "Live2D이면 PSD2Live에서 리깅한다. 이미지 AI는 코드를 실행하거나 "
               "리깅 성공을 주장하지 않는다.")
    if mode == "3d":
        if asset == "body":
            joint = ("- 8방향 시점과 가림 상세 1장에서 턱 뒤 목·귀 뒤·목-어깨·팔꿈치·"
                     "손목·전신 관절 연결을 **그림으로** 일관되게 보여준다. "
                     "2D 전용 neck_underpaint/body_joint_overlaps PNG를 3D 납품 파일로 만들지 않는다.")
        return f"""### 이미지 생성 AI 3D 형태 참고 전용
- 동일 자산의 8방향과 가림 참고 이미지를 직접 그려 제출한다.
{deliver}
{joint}
{handoff}
"""
    slot_reference = {
        "body": ("참조 플랫폼의 실제 샘플 PSD 레이어 계층과 앞뒤 가림, "
                 "눈-흰자/홍채/윗속눈썹, 입-닫힌선/입안/윗니/혀, "
                 "얼굴/귀/목, 좌우 상완/전완/손"),
        "hair": ("Live2D 원화 가공 예제의 앞머리·옆머리 좌우·뒷머리·"
                 "개별 흔들리는 긴 가닥과 가려진 모근"),
        "outfit": ("실제 입힌 옷의 앞/뒤, 소매 좌우, 옷깃, "
                   "따로 흔들리는 리본·밑단과 겨드랑이 안쪽"),
        "accessory": ("실제로 존재하는 장식의 개별 움직임, "
                      "좌우·앞뒤 레이어와 착용 부착점"),
    }[asset]
    template_url = ("https://docs.inochi2d.com/en/latest/creator/first-model/tutorial01.html"
                    if mode.startswith("inochi2d") else
                    "https://docs.live2d.com/en/cubism-editor-tutorials/template/")
    part_examples = {
        "body": (
            "face, ear.left, ear.right, eye.left.white, eye.left.iris, "
            "eye.left.upper.lash, eye.right.white, eye.right.iris, "
            "eye.right.upper.lash, eyebrow.left, eyebrow.right, nose, "
            "mouth.close, mouth.open, mouth.tooth.t, mouth.tongue, "
            "neck, torso, arm.left.upper, arm.left.forearm, hand.left, "
            "arm.right.upper, arm.right.forearm, hand.right"
            + (", pelvis, thigh.left, thigh.right, shin.left, shin.right, "
               "foot.left, foot.right" if mode.endswith("_full") else "")
        ),
        "hair": "hair.back, hair.front, hair.side.left, hair.side.right; 실제 움직이는 추가 가닥만",
        "outfit": "outfit.back, outfit.front, sleeve.left, sleeve.right; 실제 존재하는 칼라·리본·밑단만",
        "accessory": "accessory.back, accessory.front; 실제 개별 장식과 부착점만",
    }[asset]
    frame_info = {
        "live2d_bust_up": "얼굴 크게, 목·양어깨·양팔·양손·상복부까지",
        "live2d_upper": "두상부터 상반신·허리까지",
        "live2d_full": "정수리부터 두 발까지 일관된 6등신",
        "inochi2d_upper": "두상부터 상반신·양손까지",
        "inochi2d_full": "머리부터 두 발까지 일관된 6등신",
    }[mode]
    asset_master = {
        "body": "BODY 원화의 얼굴·눈·입·목·팔다리·기준 색상",
        "hair": "헤어만의 선화·머리방향·컬러와 원래 BODY 부착점",
        "outfit": "요청 의상의 재질·무늬·소매·옷깃과 BODY 앵커",
        "accessory": "요청한 소품만의 색상·디자인·부착점",
    }[asset]
    part_rule = {
        "body": "양눈은 흰자·홍채·윗속눈썹을 각자 그린다. 입은 닫힌 선·열린 안쪽·윗니·혀를 나누고, 팔은 상완·전완·손으로 독립 작화한다.",
        "hair": "앞·뒤·좌우 옆머리와 실제 흔들릴 가닥만 구분한다. 눈·입·피부와 의상은 그리거나 납품하지 않는다.",
        "outfit": "앞·뒤 옷판과 좌우 소매·옷깃·필요한 안감만 독립 작화한다. 눈·입·신체·헤어를 새로 제작하지 않는다.",
        "accessory": "실제 소품의 앞뒤 움직이는 부분과 고정 부착점만 독립 작화한다. 소품 이외 얼굴·눈·입·피부·의상은 새로 제작하지 않는다.",
    }[asset]
    neutral_rule = (
        "mouth.open, mouth.tooth.t, mouth.tongue는 실제 서로 다른 원화로 만들고, "
        "중립 합성 미리보기에서는 이 대체 표정 레이어만 숨긴다."
        if asset == "body" else
        "이 자산에 실제로 존재하지 않는 대체 표정이나 BODY 전용 입·눈 원화를 추가하지 않는다."
    )
    consistency = (
        "두 눈 좌우·턱·목·어깨·팔꿈치·손목과 가림/관절" if asset == "body"
        else "현재 자산의 실루엣·BODY 기준 부착점·앞뒤 가림 및 접합"
    )
    expression_delivery = (
        " BODY는 expression_refs/mouth_closed.png 와 "
        "expression_refs/mouth_open.png도 독립된 실제 표정 전체 참고 원화로 제출한다."
        if asset == "body" else
        " BODY 전용 expression_refs/mouth_closed.png 및 mouth_open.png를 새로 만들지 않는다."
    )
    if asset == "body":
        side_requirements = (
            "- [목 파츠 실물 제작] `part_art/neck.png`는 턱 아래에 딱 맞춰 자르지 않는다. "
            "정면에서 얼굴 레이어 아래로 목 피부를 입 높이 가까이까지 연장하고, "
            "목 밑은 몸통 상부(쇄골 외피 안쪽)와 겹치게 실제 같은 색의 픽셀로 그린다. "
            "단순한 검은 틈, 피부색 직사각형 또는 알파가 접하기만 한 선은 실패다. "
            "`part_art/face.png`의 턱 아래 실제 알파와 목, 목과 몸통 알파가 각각 겹쳐야 한다.\\n"
            "- [45°와 90° 구분] `head_three_quarter_L/R.png`는 각각 약 45° "
            "머리 돌림의 형태 가이드다. `head_profile_L/R.png`는 각각 진짜 90° "
            "측면 **형태 참고**이며 자동으로 MOC3 90° 키폼이 되지 않는다. "
            "모든 각도에는 코→입→턱 선, 귀의 실제 앞뒤 위치, "
            "턱 아래부터 목뿌리·양어깨 연결을 포함해 잘린 목이 없어야 한다. "
            "좌우 시점은 단순 좌우 반전/정면 왜곡으로 만들지 않는다.\\n"
            "- [상하 회전] `head_pitch_up/down.png`는 턱 아래 목 피부가 더 보이거나 "
            "가려지는 변화, 귀·턱 끝·목뿌리의 앞뒤 가림을 실제 새 그림으로 설명한다. "
            "`neck_underpaint.png`와 `body_joint_overlaps.png`는 "
            "참고 그림만으로 인정되며 실제 `part_art/neck.png`와 "
            "`part_art/torso.png`의 보이지 않는 픽셀을 대신하지 못한다.\\n"
        )
    else:
        side_requirements = (
            "- [자산별 옆/뒤 가림] 정면·좌우 3/4·좌우 측면·뒷면 참고에서 "
            "선택한 자산의 앞뒤 깊이와 BODY 실제 앵커를 명확히 한다. "
            "헤어는 귀 뒤 모근·목 뒤 가닥, 의상은 옷깃 아래 목·어깨·겨드랑이, "
            "소품은 귀·머리·옷 장착 부위를 각각 해당될 때만 보강한다. "
            "BODY 얼굴·눈·입·목을 이 자산 PNG에 복제하지 않는다.\\n"
        )
    native_limits = (
        "- [실제 리깅 기능] Live2D PSD2Live 기본 자동 머리 요 회전은 "
        "`ParamAngleX=-45..+45`, 피치는 `ParamAngleY=-30..+30`다. "
        "90° 정측면 참고는 별도 키폼·교체 원화/추가 구현 없이는 재현되지 않는다. "
        "다각도 참고 파일이 자동으로 변형 키폼에 적용됐다고 주장하지 않는다. "
        if mode.startswith("live2d") else
        "- [실제 리깅 기능] Inochi2D의 PNG·PSD 기반 원화는 "
        "Inochi Creator 파츠 노드/메시/뼈/변형을 별도로 설정해야 움직인다. "
        "참고 측면 그림은 실제 90° 키폼이 아니며 현재 파이프라인에서 "
        "자동 Inochi2D 리깅이 확인되지 않았다. "
    )
    return f"""### [ONE_PART_PER_GENERATION_V1] 실제 VTuber 파츠를 하나씩 그리는 작업 계약
**이 단계는 '완성 이미지 한 장만 그린 뒤 남에게 전부 잘라 달라'가 아니다.**
- 먼저 제공된 템플릿의 이미지와 실제 레이어/파츠 구조를 열어 눈으로 확인한다. 템플릿을 링크만 적어두고 미열람 상태로 생성하지 않는다. 참조: {template_url}
- [공식 Live2D 원화 분리 예제] https://docs.live2d.com/en/cubism-editor-tutorials/psd/ ; [자유 재사용 가능 예시 PSD] https://github.com/tsunehimatoi/psd2live-examples (CC0, 개별 샘플 표시 조건 검토).
- **참고 슬롯:** {slot_reference}. 공식 템플릿은 구성·앞뒤·숨은 영역의 예시다. 그 캐릭터 모습, 스타일, 인체 비율을 복사하지 않는다. Inochi Aka는 얼굴 구조 참고이지 전신 팔까지 있는 템플릿이 아니다.
- 자산과 프레이밍: {mode}/{asset}; {frame_info}. 다른 자산을 새로 제작하지 않는다.
- 1) 해당 자산의 디자인 마스터를 그려 정면 전체 실루엣과 {asset_master}을(를) 고정한다.
- 2) 다음부터는 **한 번의 생성/수정에서 정확히 한 파츠**만 그린다. 해당 파츠와 원래 마스터, 실제 공식 템플릿의 대응 슬롯, 직전 승인된 파츠를 함께 시각적으로 참고한다. 결과를 확인하고 다음 파츠로 넘어간다. 시트 한 장에 여러 작은 파츠를 한꺼번에 그리는 것으로 대체 금지.
- 3) 각 파츠는 **마스터와 동일한 전체 캔버스 좌표의 RGBA PNG**를 `part_art/<semantic_name>.png`에 저장한다. 한 파일에는 그 파츠와 **원래 가려졌지만 회전할 때 노출되는 연장 픽셀만** 그리고, 다른 얼굴/몸/옷을 같이 넣지 않는다. 배경·가이드·레이블·텍스트·캐릭터 실루엣 중복을 투명 영역에 남기지 않는다.
- 4) 권장 파츠 역할: {part_examples}. {part_rule} 해당 자산에 실제로 없는 부품을 억지로 만들거나 다른 자산의 파츠를 납품하지 않는다.
- 5) `part_art/_order.txt`에 **맨 앞에 보이는 파츠부터 맨 뒤 파츠 순서로** 각 경로를 한 줄씩 적는다. PNG 이름과 경로만 기록하며 PSD, 알파 마스크, 3D 메시, MOC3는 만들지 않는다. {neutral_rule}
- 6) 해당 자산의 {consistency}을(를) 좌우 3/4·측면 참조와 교차 확인한다. **중립 파츠 합성은 원래 `outputs/master.png`의 해당 자산과 색·위치·모양이 같아야 한다.** 중복·가림 구멍·부유 파츠·선화 소실은 실패다.
- 7) 필수 납품: `outputs/master.png`, `part_art/_order.txt`, 각 파츠의 개별 `part_art/*.png`, 다음 다각도 참조 PNG: {", ".join("reference_views/" + v + ".png" for v in VIEWS_2D[asset])}.{expression_delivery}
- 8) 신뢰할 수 있는 투명 배경을 이미지 생성기가 지원하지 못하면 **하얀 배경 PNG를 투명 파츠라고 이름만 바꿔 내지 말고** 별도 검수 실패로 표시한다. 원본 파츠를 보존한 채 Colab에 See-through 분리 경로를 요청할 수 있다.
- 9) 3/4·좌우 측면·상하 회전의 **기본 비교 참고 이미지**는 마스터와 같은 캔버스 크기·화면 기준축·캐릭터 척도를 유지한다. 눈·귀·턱·목 부착점 위치는 실제 회전에 따라 바뀌어도 재프레이밍·확대/축소해서 연결을 숨기지 않는다. 확대된 디테일 클로즈업은 별도 추가 그림으로만 제출한다.
{side_requirements}{native_limits}
{joint}
- **제작 단계 확정:** 이미지 AI는 위에 명시한 독립 파츠의 실제 그림과 다각도 참조를 하나씩 제작한다. PSD 인코딩·메시·키폼·리깅은 별도 단계다. {handoff}
- 기존 실제 템플릿을 열지 않았거나 파츠를 하나하나 생성하지 않은 결과는 완료라고 보고하지 않는다.
"""

def source_only_output_file(mode: str, asset: str) -> str:
    matte = ("불투명 단색 무광 찰흙형 BODY" if asset == "body"
             else "BODY 기준 무광 찰흙형 정렬; 해당 자산만 제작")
    return (
        "# 04 — 이미지 생성 AI 개별 파츠 원화 납품\n\n"
        "## [MATTE_CLAY_BODY_V1]\n" + matte + "\n## [/MATTE_CLAY_BODY_V1]\n\n" +
        BEGIN + "\n" + source_contract(mode, asset) + END + "\n" +
        "\n## 납품 검사\n\n"
        "완성 마스터와 각 파츠 PNG를 실제 열어 동일한 캐릭터·색·좌표·투명도·가림을 확인한다. "
        "파츠별 원화를 하나씩 생성하되 PSD 인코딩·메시·리깅은 여기서 하지 않는다.\n"
    )

def normalize_source_only(text: str, mode: str, asset: str, filename: str) -> str:
    if filename == "04_OUTPUT_FILES.md":
        return source_only_output_file(mode, asset)
    # Remove prior copy to ensure repeated writes do not accumulate instructions.
    text = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END), "",
                  text, flags=re.S)
    bibliography = filename in {
        "05_OFFICIAL_REFERENCES.md", "06_ADVANCED_OFFICIAL_COMMUNITY.md",
        "11_OFFICIAL_IMAGE_EXAMPLES.md",
    }
    lines, fenced = [], False
    for line in text.splitlines():
        if line.strip().startswith(chr(96) * 3):
            fenced = not fenced
            if not bibliography:
                continue
        if fenced and not bibliography:
            continue
        if AUTHORING_OUTPUT.search(line):
            # Preserve actual reference URLs. They are not output instructions.
            if "http://" in line or "https://" in line:
                lines.append(line)
            continue
        lines.append(line)
    while lines and not lines[-1].strip():
        lines.pop()
    result = "\n".join(lines) + "\n\n" + BEGIN + "\n" + source_contract(mode, asset) + END + "\n"
    if result.count(BEGIN) != 1 or result.count(END) != 1:
        raise ValueError("SOURCE_ONLY_MARKER_DUPLICATE: " + filename)
    return result
