"""Apply image-generation-only multi-view art briefs to the 24 canonical ZIPs.

These archives are prompts for an image-capable AI, NOT Colab notebooks.
No See-through, PSD2Live, image2live2d or application executable is bundled.
The existing 14 Markdown files and their published paths are preserved.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import tempfile
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1] / "docs" / "image_ai_kits_v2" / "zips"
MODES = (
    "live2d_bust_up", "live2d_upper", "live2d_full",
    "inochi2d_upper", "inochi2d_full", "3d",
)
ASSETS = ("body", "hair", "outfit", "accessory")
DOCS = (
    "00_MASTER_FIRST.md", "00_DELIVERY_AND_RECHECK.md", "00_READ_FIRST.md",
    "01_COMMON_RULES.md", "02_ADVANCED_PARTS.md", "03_MODE_RULES.md",
    "04_OUTPUT_FILES.md", "07_REVIEW_BEFORE_FINAL_ZIP.md",
    "08_PRACTICAL_TIPS.md", "09_VISUAL_ART_QUALITY.md",
)
MARKER = "## [IMAGE_ART_MULTIVIEW_SOURCE_ONLY_V1]"
MARKER_END = "## [/IMAGE_ART_MULTIVIEW_SOURCE_ONLY_V1]"


COVER_MARKER = "## [BODY_DEFAULT_OPAQUE_SWIMWEAR_V1]"
COVER_MARKER_END = "## [/BODY_DEFAULT_OPAQUE_SWIMWEAR_V1]"
COVER_PRIORITIES = frozenset((
    "00_MASTER_FIRST.md", "00_READ_FIRST.md", "03_MODE_RULES.md",
    "07_REVIEW_BEFORE_FINAL_ZIP.md", "09_VISUAL_ART_QUALITY.md",
    "10_ANIME_STYLE.md",
))
from tools.normalize_matte_clay_kits import CONTRACT as MATTE_CLAY_CONTRACT
COVER_INSTRUCTIONS = COVER_MARKER + "\n\n" + MATTE_CLAY_CONTRACT["body"] + COVER_MARKER_END

BODY_UNSAFE_REPLACEMENTS = (
    ("터틀넥·민소매 상의·보디슈트·드레스 금지. 가려야 할 부분은 가장 작은 단색 무지 밴드형 이너만 별도 교체 가능한 가림 레이어로 사용한다.",
     "디자인 의상은 OUTFIT 전용이며 BODY에는 위 기본 불투명 스포츠 수영복을 착용한다."),
    ("터틀넥·민소매 상의·보디슈트·드레스 금지. 가려야 할 부분은 가장 작은 단색 무지 밴드형 이너만 별도 교체 가림 레이어로 사용한다.",
     "디자인 의상은 OUTFIT 전용이며 BODY에는 위 기본 불투명 스포츠 수영복을 착용한다."),
    ("목 덮는 상의·터틀넥·보디슈트 금지. 최소 면적 무지 가림만 별도 파츠.",
     "목 회전을 방해하는 패션 의상은 제외하며, 기본 불투명 스포츠 수영복을 안전한 독립 파츠로."),
    ("가림은 별도 최소 무지 파츠이며 상의는 OUTFIT에서만 제작한다.",
     "BODY의 불투명 스포츠 수영복 상의·하의는 안전 가림 파츠이며 교체용 패션 의상은 OUTFIT만 제작한다."),
    ("몸통에 속옷·튜브탑·상의 선·겨드랑이 살접힘·가슴/쇄골 해부학 음영을 추가하지 않는다.",
     "몸통에 위 기본 스포츠 수영복 상의·하의를 입히고 해부학적 굴곡은 강조하지 않는다."),
    ("필요 최소 가림은 독립 파츠로 분리하고 다른 의상은 만들지 않는다.",
     "기본 스포츠 수영복 상·하의만 안전 복장으로 제작하며 다른 디자인 의상은 만들지 않는다."),
    ("최소 단색 가림 커버/마스크", "불투명 스포츠 수영복"),
    ("불투명 중립색 실루엣/마스킹", "불투명 스포츠 수영복"),
    ("최소 면적 무지 가림", "불투명 스포츠 수영복"),
    ("최소 무지 가림", "불투명 스포츠 수영복"),
    ("속옷·후드·리본·안경 등 다른 카테고리",
     "후드·리본·안경 등 다른 카테고리"),
    ("복장 없는 상태를 먼저", "수영복을 착용한 상태를 먼저"),
    ("젖꼭지", "과도한 해부학 표현"),
)


def normalize_body_swimwear(text: str, *, mode: str, name: str) -> str:
    """Normalize old contradictory undressed-body instructions, source-only."""
    if text.count(COVER_MARKER) > 1 or text.count(COVER_MARKER_END) > 1:
        raise ValueError("Duplicate safety wardrobe marker")
    if text.count(COVER_MARKER) != text.count(COVER_MARKER_END):
        raise ValueError("Partial safety wardrobe marker")
    if COVER_MARKER in text:
        start = text.index(COVER_MARKER)
        end = text.index(COVER_MARKER_END, start) + len(COVER_MARKER_END)
        text = text[:start] + text[end:].lstrip("\r\n")
    for old, new in BODY_UNSAFE_REPLACEMENTS:
        text = text.replace(old, new)
    # The references may contain old negative examples. Keep the visual data
    # unchanged but explicitly scope wardrobe priority for every generation doc.
    if name in COVER_PRIORITIES:
        # The read-first banner MUST stay at byte zero. Insert the wardrobe
        # brief immediately after that validated banner, never before it.
        if text.startswith("# [READ_ALL_BEFORE_IMAGE_GENERATION_V1]"):
            boundary = "**GPT가 이 문서를 읽기 전에 이미지를 생성했다면 그 출력은 납품 실패다.**\n\n"
            idx = text.find(boundary)
            if idx < 0:
                raise ValueError("Read-first boundary missing: " + name)
            idx += len(boundary)
            text = text[:idx] + COVER_INSTRUCTIONS + "\n\n" + text[idx:]
        else:
            text = COVER_INSTRUCTIONS + "\n\n" + text.lstrip()
    return text

EXPECTED = (
    "00_MASTER_FIRST.md", "00_DELIVERY_AND_RECHECK.md", "00_READ_FIRST.md",
    "01_COMMON_RULES.md", "02_ADVANCED_PARTS.md", "03_MODE_RULES.md",
    "04_OUTPUT_FILES.md", "05_OFFICIAL_REFERENCES.md",
    "06_ADVANCED_OFFICIAL_COMMUNITY.md", "07_REVIEW_BEFORE_FINAL_ZIP.md",
    "08_PRACTICAL_TIPS.md", "09_VISUAL_ART_QUALITY.md",
    "10_ANIME_STYLE.md", "11_OFFICIAL_IMAGE_EXAMPLES.md",
)

ASSET = {
    "body": {
        "subject": "BODY — 눈·얼굴·귀·입·목·어깨·관절·손, 전신이면 다리와 발",
        "views": ("body_front.png", "head_three_quarter_L.png", "head_three_quarter_R.png",
                  "head_profile_L.png", "head_profile_R.png",
                  "head_pitch_up.png", "head_pitch_down.png",
                  "neck_underpaint.png", "body_joint_overlaps.png"),
        "internal": "눈 흰자/홍채/윗아랫눈꺼풀과 속눈썹·눈썹·시선 상태, 정확히 한 개의 입의 열림/닫힘, 턱 뒤에서 입 높이 부근까지 숨겨진 목 피부, 목 아래 몸통, 어깨/팔꿈치/손목의 접합부와 실제 손가락을 필요 수만큼 별도로 그린다. 3/4 먼 눈·코·턱·귀는 정면을 눌러 만든 것이 아닌 새로운 형태로 작화한다.",
        "forbidden": "HAIR·교체 OUTFIT·ACCESSORY를 BODY 완성 자산에 섞지 않는다. 회색 도형, 실사 인체, 길고 좁은 얼굴, 끊긴 목, 두 입, 손 없는 바스트업은 실패다.",
    },
    "hair": {
        "subject": "HAIR — 요청받은 헤어스타일 한 종류의 가닥·후두부·머리뿌리·그림자",
        "views": ("hair_front.png", "hair_three_quarter_L.png", "hair_three_quarter_R.png",
                  "hair_profile_L.png", "hair_profile_R.png", "hair_back.png",
                  "hair_underlayers.png", "hair_motion_clearance.png"),
        "internal": "앞머리/옆머리/뒷머리/아호게 등 독립적으로 움직일 실제 묶음만 생성한다. 앞머리 아래 이마를 머리카락으로 새로 그리면 안 되며, 귀 앞뒤와 정수리·후두부의 숨은 가닥·뿌리·끝의 실제 픽셀을 추가한다. 좌우 프로필 및 후면에서 머리카락 질량·뿌리 방향·가닥 겹침을 정합시킨다.",
        "forbidden": "BODY의 눈·피부·목·손, OUTFIT, ACCESSORY를 새 완성 자산으로 그리거나 PSD 파츠에 혼입하지 않는다.",
    },
    "outfit": {
        "subject": "OUTFIT — 요청받은 의상 한 종류와 의상에 종속된 단추·프릴·리본",
        "views": ("outfit_front.png", "outfit_three_quarter_L.png", "outfit_three_quarter_R.png",
                  "outfit_profile_L.png", "outfit_profile_R.png", "outfit_back.png",
                  "outfit_inside_seams.png", "outfit_joint_clearance.png"),
        "internal": "앞/뒤 판·옷깃·목둘레·소매·어깨·팔꿈치·손목·옷 아래 가려진 원단과 안감, 필요한 경우 허리·치맛단·무릎 주변의 실제 천을 작화한다. 가동 부위와 가려지는 속면, 천의 두께·주름 방향이 다각도에서 이어져야 한다. 의상 고유 장식만 의상 파츠로 포함한다.",
        "forbidden": "신체 피부와 눈·목 등 BODY 원화를 의상 속에 합성한 독립 부품으로 납품하지 않는다. 별도 착용 소품은 ACCESSORY의 몫이다.",
    },
    "accessory": {
        "subject": "ACCESSORY — 지정된 부착 소품 한 종류",
        "views": ("accessory_front.png", "accessory_three_quarter_L.png",
                  "accessory_three_quarter_R.png", "accessory_profile_L.png",
                  "accessory_profile_R.png", "accessory_back.png",
                  "accessory_attachment_anchor.png", "accessory_occlusion.png"),
        "internal": "부착점과 접촉 방향·앞뒤 깊이·고정부·가려지는 뒷면을 실제 원화로 만든다. 좌우 회전시 소품 두께와 고정점이 유지되어야 한다. 필요한 경우 서로 다른 깊이에서 움직이는 소품의 부위만 분리한다. 사용자가 요청한 종류가 머리 장식이 아닐 수 있으므로 실제 소품 형태에 맞춰 뷰를 조정한다.",
        "forbidden": "신체·헤어·의상을 다시 제작하거나 종합 액세서리 세트를 강제로 만들지 않는다.",
    },
}

def frame(mode: str) -> str:
    return {
        "live2d_bust_up": "방송용 바스트업: 얼굴·목·양어깨·양팔·양손·상복부가 빠지지 않게. 전신·하체 이미지 생성은 납품 필수 아님.",
        "live2d_upper": "상반신: 두상부터 허리/상반신 지정 끝까지. 하체를 강제로 만들지 않는다.",
        "live2d_full": "전신: 6등신 스타일의 정수리~발끝, 손·무릎·발목·발 모두 일관성 유지.",
        "inochi2d_upper": "Inochi2D 상반신: 동일 캐릭터의 머리·목·양팔·손·상반신. Cubism 네이티브 파일은 요구하지 않는다.",
        "inochi2d_full": "Inochi2D 전신: 6등신 애니풍 전신과 사지의 연결. Cubism 네이티브 파일은 요구하지 않는다.",
        "3d": "3D용 원화 참고: 앞·좌우 3/4·좌우 옆·좌우 뒤 3/4·후면(최소 8개 방향)의 동일 자산 턴어라운드. 2D PSD 파츠가 아닌 형태·재질·뒷면·앵커 참고 그림.",
    }[mode]

def guidance(mode: str, asset: str) -> str:
    a = ASSET[asset]
    if mode == "3d":
        names = (
            f"{asset}_front.png", f"{asset}_front_three_quarter_L.png",
            f"{asset}_left.png", f"{asset}_back_three_quarter_L.png",
            f"{asset}_back.png", f"{asset}_back_three_quarter_R.png",
            f"{asset}_right.png", f"{asset}_front_three_quarter_R.png",
            f"{asset}_detail_occlusion.png",
        )
        views = ", ".join("views/" + name for name in names)
    else:
        views = ", ".join("reference_views/" + name for name in a["views"])
    details = a["internal"]
    if mode == "3d" and asset == "body":
        details = ("두상·눈·코·입·귀·목·어깨·팔·손과 전신인 경우 다리·발을 "
                   "모든 시점에서 일관된 3D 형태·실루엣·구조로 그린다. "
                   "눈 뒤·턱 밑·목 뒤·관절 뒤의 보이지 않는 면을 실제 측면/후면 참고로 그린다. "
                   "2D 레이어별 눈 흰자/속눈썹 PNG 분리나 PSD 리깅용 파츠는 만들지 않는다.")
    if mode == "3d":
        output = (
            "3D ZIP의 실제 납품은 동일 캐릭터/자산의 다각도 PNG 턴어라운드, "
            "실루엣·재질·부착 앵커 참조, 상세 클로즈업 및 검수표다. "
            "PSD 층, 2D 눈 리깅 파츠, VRM 바이너리, Blender 실행 결과를 요구하거나 성공했다고 주장하지 않는다."
        )
    else:
        output = (
            "2D ZIP의 실제 납품은 해당 자산의 기준 마스터 원화, 추가 참고 시점 그림, "
            "독립 RGBA 원화 파츠와 마스크, 합성 미리보기, 편집 가능한 레이어 PSD 및 검수표다. "
            "참고 시점 PNG가 자동으로 모션 키폼·메시가 되지는 않는다."
        )
    angle = ("3D 턴어라운드의 실제 형태를 새로 묘사하며," if mode == "3d"
             else "정면 PNG의 단순 확대/축소/미러링/기하 왜곡으로 측면을 대신하지 않고,")
    if mode == "3d":
        part_ids = ("3D ZIP은 2D용 개별 PNG 파츠 명세나 2D 전용 레이어 순서표를 요구하지 않는다. "
                    "views/ 폴더에 명시한 9개 필수 실제 PNG를 저장한다.")
    elif asset == "body":
        part_ids = ("2D 독립 파츠 이름은 계층/해부학 기준으로 face 또는 head, neck, "
                    "torso 또는 body, eye_L/eye_R, arm_L/arm_R, hand_L/hand_R "
                    "등을 실제 부위별로 부여한다. 기본 수영복의 상·하의는 "
                    "removable_neutral_modesty_band_upper 및 "
                    "removable_neutral_modesty_band_lower로 각각 분리하고 "
                    "실제 화면에 보이는 상·하의 레이어를 켠 채 마스터와 미리보기를 만든다. "
                    "isolated_parts/*.png와 layer_order.txt는 모두 실제 파일로 맞춘다. "
                    "눈 감김·반감김·입 벌림은 expression_refs/ 참조 PNG로 따로 보관한다. "
                    "중립 합성 layer_order.txt에 배타적 표정 파츠를 동시에 넣어 "
                    "두 눈·두 입이 중복되는 결과를 만들지 않는다.")
    else:
        part_ids = (
            f"{asset.upper()}의 isolated_parts/ 파츠 ID는 "
            + {"hair": "hair", "outfit": "outfit/cloth", "accessory": "accessory/ornament"}[asset]
            + " 계열로 시작하도록 적고, 한 파츠의 좌우·깊이 정보를 이름에 명확히 표시한다. "
              "다른 자산의 이름이나 픽셀은 독립 파츠로 포함하지 않는다. "
              "layer_order.txt의 경로는 실제 isolated_parts/ PNG와 1:1 매칭한다."
        )
    view_requirement = (
        "3D의 필수 8방향 원화와 가림 세부 1장은 모두 views/ 폴더의 명시된 정확한 파일명으로 납품한다. "
        "reference_views/ 안의 비율·표정 보조 가이드는 필수 턴어라운드를 대체하지 않는다."
        if mode == "3d" else
        "2D의 필수 reference_views/ 시점 PNG는 선택사항이 아니다. "
        "정확한 파일명과 경로를 지키고 다각도 원화를 완성한 뒤 파츠를 분리한다."
    )
    return f"""{MARKER}

**이 ZIP의 유일한 역할은 이미지 AI가 완성 원화와 참고도 및 필요한 원화 레이어를 충분히 생성하는 것이다.** Colab/노트북의 See-through·PSD2Live·image2live2d 설치, 실행, 명령어, 스크립트, 모델 변환 및 리깅은 이 ZIP에 넣지 않는다. 포토샵/PRO 유료 라이선스를 전제하지 않는다.
**작업 구분 잠금:** {mode} / {asset}; {a["subject"]}. 기존 14개 MD와 제공된 실제 시각 참고 자료를 모두 확인한 뒤 생성한다.

### 해당 ZIP에서 생성할 다각도·세부 원화
- 모드 구도: {frame(mode)}
- 최종 결과 ZIP에 **반드시 포함할 필수 참조 시점 PNG** (동일 이미지 재사용/미러링 금지): {views}.\n- 최소 참고 파일 후보: {views}.
- 위 PNG 목록은 **납품 필수**이고 파츠 개수 상한이 아니다. 실제 가림·회전·변형의 불일치가 발견되면 필요한 시점·표정·파츠 그림을 추가 생성한다. 반대로 의미 없는 정면 복제본으로 장수만 늘리지 않는다. 같은 캐릭터·같은 소재·같은 색과 조명·같은 앵커를 유지한다.
- {angle} 3/4/프로필의 앞뒤 관계·실루엣·두께·그림자 방향을 실제로 다르게 그린다.
- 자산별 상세: {details}\n- Colab 입력 파츠·경로 계약: {part_ids}
- 자산 소유권 금지: {a["forbidden"]}
- {output}
- {view_requirement}.
- 기존 문서의 '완성 원화 한 장을 먼저 만든다'는 **첫 번째 기준 마스터 제작 순서**이지 '한 장만 생성해 납품한다'는 뜻이 아니다. 기준 마스터가 합격한 다음 다각도 원화·숨은 면·표정/가동 참고를 더 생성하고 동일성 검수 후 부위 분리를 진행한다. 자료가 부족하면 파츠를 기계적으로 잘라서 채우지 않고 부족한 원화를 다시 그린다.
- **최종 이미지 품질 게이트:** 각 참고 시점의 식별 가능한 실제 시각 차이, 해당 자산의 비율·선화·그림자 통일, 움직일 가림 부위의 완성 픽셀, 올바른 깊이·레イヤ 소유권, 정면/측면 교차대조를 확인한다. 틀리면 이미지를 수정/재생성한다. PSD 레이어 수·ZIP CRC 통과만으로 시각 품질 PASS 금지.
- **후속 단계 구분:** See-through는 노트북에서 분리 후보를 내는 도구일 뿐이다. PSD2Live/image2live2d 등은 노트북의 후속 리깅 후보일 뿐이다. 이 ZIP의 이미지 AI는 그 프로그램을 설치/실행/인증하거나 실제 Cubism/Inochi/VRM 동작 결과가 있다고 주장하지 않는다.

{MARKER_END}
"""

def updated_text(original: str, section: str) -> str:
    a, b = original.count(MARKER), original.count(MARKER_END)
    if a != b or a > 1:
        raise ValueError("Partial/duplicate multi-view section; refusing corrupt patch")
    if a:
        start = original.index(MARKER)
        stop = original.index(MARKER_END, start) + len(MARKER_END)
        return original[:start] + section.strip() + original[stop:]
    return original.rstrip() + "\n\n" + section

def apply(path: Path, *, write: bool) -> bool:
    mode, asset = path.stem.rsplit("__", 1)
    if mode not in MODES or asset not in ASSETS:
        raise ValueError("Unexpected ZIP: " + path.name)
    with ZipFile(path, "r") as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if len(names) != 14 or len(set(names)) != 14 or set(names) != set(EXPECTED):
            raise ValueError("Not the canonical 14-MD ZIP: " + path.name)
        if archive.testzip() is not None:
            raise ValueError("Invalid CRC: " + path.name)
        old = {name: archive.read(name).decode("utf-8") for name in names}
    if mode != "3d":
        # Obsolete 2D multi-view output blocks requested image AI-written
        # PSD, isolated_parts and masks. Current image AI creates one
        # correctly anchored part_art/*.png per call instead. This legacy
        # generator must not restore those old instructions on any rebuild.
        if all(
            doc.count("## [IMAGE_AI_SOURCE_ONLY_V2]") == 1
            and doc.count("## [/IMAGE_AI_SOURCE_ONLY_V2]") == 1
            and "## [IMAGE_ART_MULTIVIEW_SOURCE_ONLY_V1]" not in doc
            for doc in old.values()
        ):
            return False
        raise ValueError("OBSOLETE_2D_MULTIVIEW_GENERATOR: "
                         "regenerate using python -m tools.update_source_only_body_kits")
    new = old.copy()
    section = guidance(mode, asset)
    for name in EXPECTED:
        source_text = old[name]
        if asset == "body":
            source_text = normalize_body_swimwear(
                source_text, mode=mode, name=name)
        if name in DOCS:
            if name == "04_OUTPUT_FILES.md" and mode != "3d":
                source_text = source_text.replace(
                    "reference_views/ — 회전 보조(필요한 경우만)",
                    "reference_views/ — 위에 나열한 해당 자산별 필수 다각도 PNG 납품")
            new[name] = updated_text(source_text, section)
        else:
            new[name] = source_text
    for name in EXPECTED:
        if name in DOCS:
            if new[name].count(MARKER) != 1 or new[name].count(MARKER_END) != 1:
                raise ValueError("Missing multi-view guidance: " + path.name + ":" + name)
        elif asset != "body" and new[name] != old[name]:
            raise ValueError("Out-of-scope reference changed: " + name)
    if new == old:
        return False
    if not write:
        raise ValueError("ZIP needs multi-view update: " + path.name)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix="multiview-",
                                         suffix=".zip", delete=False) as stream:
            tmp = Path(stream.name)
        with ZipFile(tmp, "w") as archive:
            for info in infos:
                archive.writestr(info, new[info.filename].encode("utf-8"))
        with ZipFile(tmp, "r") as archive:
            if archive.testzip() is not None or archive.namelist() != names:
                raise ValueError("Post-write archive verification failed")
        os.replace(tmp, path)
        tmp = None
        return True
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)

def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args()
    updated = 0
    for mode in MODES:
        for asset in ASSETS:
            path = ROOT / f"{mode}__{asset}.zip"
            if not path.is_file():
                raise FileNotFoundError(path)
            updated += apply(path, write=args.write)
    print(f"PASS: 24 canonical image-instruction ZIPs / 14 MD each; changed={updated}; no runtime bridges bundled")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
