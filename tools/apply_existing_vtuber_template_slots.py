"""Apply verified existing VTuber templates as fillable slots to the 24 canonical 14-MD ZIP briefs.

No third-party sample artwork is packaged or fetched automatically.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1] / "docs/image_ai_kits_v2"
REGISTRY = ROOT / "source" / "EXISTING_TEMPLATE_SLOT_REGISTRY.json"
ASSETS = ("body", "hair", "outfit", "accessory")
MODES = ("live2d_bust_up", "live2d_upper", "live2d_full", "inochi2d_upper", "inochi2d_full", "3d")
DOCS = ("00_MASTER_FIRST.md", "00_READ_FIRST.md", "01_COMMON_RULES.md",
        "03_MODE_RULES.md", "08_PRACTICAL_TIPS.md")
MARKER = "## [EXISTING_VTUBER_TEMPLATE_SLOTS_V1]"
READ_FIRST_END = ("**GPT가 이 문서를 읽기 전에 이미지를 생성했다면 그 출력은 납품 실패다.**\n\n")


def load_registry() -> dict:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    expected = {f"{mode}__{asset}" for mode in MODES for asset in ASSETS}
    if registry.get("schema") != "image-ai/existing-template-slots-v1":
        raise ValueError("Unexpected template registry schema")
    if set(registry["templates"]) != expected:
        raise ValueError("Template registry must cover precisely the 24 mode-asset pairs")
    for key, t in registry["templates"].items():
        if f'{t["mode"]}__{t["asset"]}' != key or not t["source_ids"] or not t["required_slots"]:
            raise ValueError(f"Broken slot contract {key}")
        if len(set(t["required_slots"])) != len(t["required_slots"]):
            raise ValueError(f"Duplicate template slots for {key}")
        for source_id in t["source_ids"]:
            source = registry["sources"].get(source_id)
            if not source or not source["url"].startswith("https://"):
                raise ValueError(f"Unverified template resource metadata {key}: {source_id}")
    return registry


def guidance(registry: dict, key: str) -> str:
    t = registry["templates"][key]
    urls = "\n".join(
        f'- {i+1}. **{registry["sources"][source_id]["title"]}** — '
        f'{registry["sources"][source_id]["url"]}\n'
        f'   - 기존 자료 형식: {registry["sources"][source_id]["asset_format"]}\n'
        f'   - 실제 활용: {registry["sources"][source_id]["role"]}\n'
        f'   - 권리 확인: {registry["sources"][source_id]["permission"]}'
        for i, source_id in enumerate(t["source_ids"])
    )
    slots = ", ".join(f"`{slot}`" for slot in t["required_slots"])
    if t["mode"] == "3d":
        no_input = ("참고 프리셋/공식 실제 그림을 확인한 뒤 새로운 캐릭터 전후좌우 원화를 만든다. "
                    "3D 이미지 AI 지시 ZIP은 PSD나 VRM 내보내기를 약속하지 않고 "
                    "턴어라운드 참조 PNG와 시각 검증을 납품한다.")
    else:
        no_input = ("참조 PSD의 존재는 도움이 되지만 납품 필수 사용자 첨부물이 아니다. "
                    "공개 샘플 캐릭터의 실제 픽셀을 재사용하지 않고 원본 애니 캐릭터를 직접 디자인하며 "
                    "완성 마스터에서 편집 가능한 다층 PSD·파츠 PNG·마스크를 만든다. "
                    "일러스트 생성/PSD 쓰기 도구가 없으면 그 도구의 한계를 보고한다.")
    return f"""{MARKER}

**실제 참고 이미지·레이어 구조를 먼저 확인한 다음 제작한다. 사용자 PSD가 없는 신규 캐릭터라면 기존 샘플을 복제하지 말고 요청된 자산의 독창적인 원화를 새로 제작한다. 회색 신체 도형 프록시는 금지한다.**
이 ZIP은 **{t["mode"]} / {t["asset"]}** 전용이다. 아래 원본 파일은 이 ZIP에 동봉되지 않은 제3자 자료다.
출처·이용 약관·파일 유형·다운로드/로컬 열림을 확인해야 실제 템플릿 사용 완료다.

### 적용 가능한 기존 템플릿
{urls}

### 채울 슬롯
{slots}

- **실제 자료 열람:** PSD나 3D 프리셋을 실제 확보했다면 파일·레이어·형태를 열람한다. 공개 PSD에 접근할 수 없으면 확인한 그림 예제와 공개 레이어 제작 지침으로 새 원화를 제작한다. 열람하지 않은 파일을 열었다고 주장하지 않는다.
- **구도:** {t["frame"]}
- **입력 해결:** {t["required_source_before_generation"]}. 신규 캐릭터는 사용자 원본 PSD·승인 원화가 없어도 기본 설정과 실제 관찰 가능한 참고 이미지로 진행한다. 이미 존재하는 특정 캐릭터를 그대로 보존해야 할 때만 식별 가능한 기존 이미지/설정을 요청하며 PSD 확장자는 강제하지 않는다.
- **슬롯 채우기:** 템플릿에 있는 부위와 사용자 원화부터 선택·매핑하고, 빈 슬롯은 동일 정합을 유지하며 독립적으로 작화한다. 색상·눈·얼굴 윤곽·목·어깨는 사용자 캐릭터와 실제 원화가 우선이며 예제 캐릭터 외형을 복제하지 않는다.
- **동일 좌표:** {t["reference_canvas_rule"]}
- **절대 불합격:** {t["mandatory_visual_gate"]}
- **없는 부위:** {t["missing_slot_policy"]}
- **검증:** 슬롯별 출처·파일 실제 열람 여부·참고 그림 실제 관찰·외부 불가 URL/사유·저작권 구분·기준 캔버스 앵커·새 원화/기존 캐릭터 선택·시각 검수 기록을 남긴다. 명시적 사용자 승인이 없는 새로운 디자인은 자동 승인됐다고 쓰지 않는다.
- **제작 순서:** 14개 MD 전체 읽기 → 접근 가능한 복수의 실제 이미지 시각 확인 및 실패 출처 기록 → 저작권·계약 정리 → (사용자 기존 디자인이 있으면 그 이미지 참조, 없으면 원본 캐릭터 완성 원화 생성) → 슬롯 매핑 → 실제 원화 검수 → 투명 레이어 분리·숨은 픽셀 보완 → 실물 PSD·PNG·마스크·검증 JSON·완성 ZIP.
- **입력이 없는 신규 캐릭터:** {no_input}
- **독립 PRO 모드:** 기존 BODY가 없으면 새 캐릭터용 공통 캔버스·앵커 명세를 먼저 고정한다. 기존 BODY와의 합성 정합을 통과했다고 가장하지 않는다.
- **공식 샘플 권리:** 공개 다운로드가 개작/재배포 허락은 아니다. 공식 샘플의 개별 이용약관을 확인하고 원본 파츠/디자인을 사용자 원화로 복제하지 않는다.
- **중요:** 기존 템플릿 PSD는 자동 Cubism 리깅이 아니다. Inochi2D PSD도 Live2D 네이티브 모션 파일이 아니다. VRoid 프리셋은 2D PSD가 아니다. 이를 혼동하거나 가짜 CMO3/MOC3/VRM을 생성했다고 주장하지 않는다.

"""


def inject(document: str, section: str) -> str:
    if document.count(MARKER) == 1:
        if section in document:
            return document
        start = document.index(MARKER)
        terminal = "- **중요:** 기존 템플릿 PSD는 자동 Cubism 리깅이 아니다."
        end = document.find(terminal, start)
        if end < 0:
            raise ValueError("Existing template section stale/mismatched")
        end = document.find("\n\n", end)
        if end < 0:
            raise ValueError("Existing template section stale/mismatched")
        legacy = document[start:end + 2]
        required_labels = ("- **슬롯 채우기:**", "- **검증:**", "- **제작 순서:**")
        known_version = (
            ("- **입력 요구:**" in legacy and
             "실제 원본이 없는 경우 생성 중단 및 소스 제공 요청" in legacy)
            or ("- **입력 해결:**" in legacy and
                "- **입력이 없는 신규 캐릭터:**" in legacy)
        )
        if not all(label in legacy for label in required_labels) or not known_version:
            raise ValueError("Existing template section stale/mismatched")
        return document[:start] + section + document[end + 2:]
    if MARKER in document:
        raise ValueError("Duplicate template marker")
    if document.startswith("# [READ_ALL_BEFORE_IMAGE_GENERATION_V1]"):
        if document.count(READ_FIRST_END) != 1:
            raise ValueError("Cannot safely retain read-first gate location")
        return document.replace(READ_FIRST_END, READ_FIRST_END + section, 1)
    return section + document


def apply(path: Path, registry: dict, *, write: bool) -> bool:
    key = path.stem
    if key not in registry["templates"]:
        raise ValueError(f"Non-canonical ZIP {path.name}")
    section = guidance(registry, key)
    with ZipFile(path) as z:
        infos = z.infolist()
        names = [i.filename for i in infos]
        if len(names) != 14 or len(set(names)) != 14 or z.testzip() is not None:
            raise ValueError(f"Corrupt or incomplete 14-MD ZIP: {path.name}")
        content = {name: z.read(name).decode("utf-8") for name in names}
    target = content.copy()
    for name in DOCS:
        if name not in target:
            raise ValueError(f"{path.name} missing {name}")
        target[name] = inject(target[name], section)
    if target == content:
        return False
    if not write:
        raise ValueError(f"{path.name}: template slot guidance missing")
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(
                prefix="vtuber-templates-", suffix=".zip",
                dir=path.parent, delete=False) as f:
            tmp = Path(f.name)
        with ZipFile(tmp, "w") as dst:
            for info in infos:
                dst.writestr(info, target[info.filename].encode("utf-8"))
        with ZipFile(tmp) as rebuilt:
            assert rebuilt.testzip() is None
            assert rebuilt.namelist() == names
            assert all(rebuilt.read(n).decode("utf-8") == target[n] for n in names)
        os.replace(tmp, path)
        tmp = None
        return True
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    exclusive = parser.add_mutually_exclusive_group(required=True)
    exclusive.add_argument("--check", action="store_true")
    exclusive.add_argument("--write", action="store_true")
    args = parser.parse_args()
    registry = load_registry()
    for mode in MODES:
        for asset in ASSETS:
            path = ROOT / "zips" / f"{mode}__{asset}.zip"
            if not path.is_file():
                raise FileNotFoundError(f"Missing canonical ZIP: {path}")
            apply(path, registry, write=args.write)
    print(f"PASS: {len(registry['templates'])} original VTuber template-slot mappings, 24 ZIPs x 14 MD")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
