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
            "- 결과 ZIP: views/" + asset + "_front.png 등의 8방향 개별 원화와 "
            "views/" + asset + "_detail_occlusion.png 총 9장. "
            "각도·캐릭터 동일성과 가림 실루엣을 지킨다."
        )
    else:
        deliver = (
            "- 결과 ZIP: outputs/master.png 한 장과 다음 실제 시점 그림: "
            + ", ".join("reference_views/" + v + ".png" for v in VIEWS_2D[asset])
            + ". 필요한 경우 expression_refs/에 완성된 표정 참고 PNG를 더한다."
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
    return f"""### 이미지 생성 AI 업무: 완성 원화만
- 해당 자산의 완성 원화와 다각도 그림을 **이미지 생성 모델로 직접 그려 PNG ZIP을 전달**한다.
- **부위별 절단, 개별 파츠 PNG, 알파 마스크, 다층 PSD, 레이어 순서, 리깅/메쉬/키폼 제작은 맡지 않는다.** 후속 Colab에서 See-through가 파츠를 분리하고 리깅 단계가 사용한다.
- 원본 자료는 실제 열람하고, 사용자가 PSD 템플릿을 제공하지 않아도 신규 디자인 원화를 진행한다.
{deliver}
{joint}
- 참고 시점 이미지는 회전 키폼 자체가 아니다. See-through 분리 이후 리깅 시 실제 관절·가림·회전 연결을 별도로 검증해야 한다.
- 기존 14개 MD의 공식 PSD·파츠 기술 링크는 **작화 참고 문헌**이지 이미지 생성 AI의 파일 출력 요구가 아니다.
"""

def source_only_output_file(mode: str, asset: str) -> str:
    matte = ("불투명 단색 무광 찰흙형 BODY" if asset == "body"
             else "BODY 기준 무광 찰흙형 정렬; 해당 자산만 제작")
    return (
        "# 04 — 이미지 생성 AI 원화 납품만\n\n"
        "## [MATTE_CLAY_BODY_V1]\n" + matte + "\n## [/MATTE_CLAY_BODY_V1]\n\n" +
        BEGIN + "\n" + source_contract(mode, asset) + END + "\n" +
        "\n## 납품 검사\n\n"
        "완성 PNG를 실제 열어서 동일 캐릭터·색·실루엣·시점별 목·어깨 연결을 확인한다. "
        "파일명과 PNG 바이트를 확인한다. PSD·개별 파츠·마스크는 이 ZIP에서 만들지 않는다.\n"
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
