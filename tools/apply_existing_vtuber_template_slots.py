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
    return f"""{MARKER}

**가장 먼저 '이미 존재하는 실제 템플릿/프리셋'을 구한다. 빈 종이에서 캐릭터를 새로 그리거나 회색 신체 도형을 만들지 않는다.**
이 ZIP은 **{t["mode"]} / {t["asset"]}** 전용이다. 아래 원본 파일은 이 ZIP에 동봉되지 않은 제3자 자료다.
출처·이용 약관·파일 유형·다운로드/로컬 열림을 확인해야 실제 템플릿 사용 완료다.

### 적용 가능한 기존 템플릿
{urls}

### 채울 슬롯
{slots}

- **템플릿 원본 열람 필수:** PSD라면 실제 레이어 패널과 그림을 열어 눈/머리·목/팔/손/의상 가림을 확인한다. 3D는 VRoid Studio에서 실제 해당 프리셋을 열어 형태와 텍스처를 확인한다. 페이지 URL만 확인하고 실제 PSD/프리셋 열람 완료라 하지 않는다.
- **구도:** {t["frame"]}
- **입력 요구:** {t["required_source_before_generation"]}. 실제 원본이 없는 경우 생성 중단 및 소스 제공 요청.
- **슬롯 채우기:** 템플릿에 있는 부위와 사용자 원화부터 선택·매핑하고, 빈 슬롯은 동일 정합을 유지하며 독립적으로 작화한다. 색상·눈·얼굴 윤곽·목·어깨는 사용자 캐릭터와 실제 원화가 우선이며 예제 캐릭터 외형을 복제하지 않는다.
- **동일 좌표:** {t["reference_canvas_rule"]}
- **절대 불합격:** {t["mandatory_visual_gate"]}
- **없는 부위:** {t["missing_slot_policy"]}
- **검증:** 슬롯별 source/template-id, 외부 파일 로컬 접근 여부, 원본 파일 종류, 실제 레이어/프리셋 시각 관찰 여부, 기준 캔버스 앵커, 라이선스 확인과 사용자 승인 기록을 남긴다.
- **제작 순서:** 14개 MD 전체 읽기 → 실제 참고 이미지·위 템플릿 전부 열람 → 요구사항 충돌 해결 → 승인된 템플릿과 슬롯 매핑 → 빈 부위만 원화 제작 → 실제 원화 검수 → 분할 PSD·마스크·완성 ZIP.
- **중요:** 기존 템플릿 PSD는 자동 Cubism 리깅이 아니다. Inochi2D PSD도 Live2D 네이티브 모션 파일이 아니다. VRoid 프리셋은 2D PSD가 아니다. 이를 혼동하거나 가짜 CMO3/MOC3/VRM을 생성했다고 주장하지 않는다.

"""


def inject(document: str, section: str) -> str:
    if document.count(MARKER) == 1:
        if section not in document:
            raise ValueError("Existing template section stale/mismatched")
        return document
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
