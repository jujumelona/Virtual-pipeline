"""Read-first gate for every published 14-MD image-AI instruction ZIP.

Do not mistake a link, checksum, or generated acknowledgement for actual
image observation. External image generators must honor the embedded workflow;
a Python gate can only check supplied evidence, not intercept external tools.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import tempfile
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1] / "docs/image_ai_kits_v2/zips"
MODES = ("live2d_bust_up", "live2d_upper", "live2d_full",
         "inochi2d_upper", "inochi2d_full", "3d")
ASSETS = ("body", "hair", "outfit", "accessory")
DOC_NAMES = ("00_MASTER_FIRST.md", "00_DELIVERY_AND_RECHECK.md",
             "00_READ_FIRST.md", "01_COMMON_RULES.md", "02_ADVANCED_PARTS.md",
             "03_MODE_RULES.md", "04_OUTPUT_FILES.md", "05_OFFICIAL_REFERENCES.md",
             "06_ADVANCED_OFFICIAL_COMMUNITY.md", "07_REVIEW_BEFORE_FINAL_ZIP.md",
             "08_PRACTICAL_TIPS.md", "09_VISUAL_ART_QUALITY.md",
             "10_ANIME_STYLE.md", "11_OFFICIAL_IMAGE_EXAMPLES.md")
PRIORITY = ("00_MASTER_FIRST.md", "00_DELIVERY_AND_RECHECK.md",
            "00_READ_FIRST.md", "07_REVIEW_BEFORE_FINAL_ZIP.md",
            "11_OFFICIAL_IMAGE_EXAMPLES.md")
REFERENCES = ("05_OFFICIAL_REFERENCES.md",
              "06_ADVANCED_OFFICIAL_COMMUNITY.md", "11_OFFICIAL_IMAGE_EXAMPLES.md")
MARKER = "[READ_ALL_BEFORE_IMAGE_GENERATION_V1]"
URL = re.compile(r"https?://[^\s<>\]\)\"']+")
IMAGE = re.compile(r"!\[[^\]]*\]\((https?://[^\s\)]+)\)")


def banner(mode: str, asset: str) -> str:
    return f"""# {MARKER} — 모든 지침/참고 이미지 확인 전 생성 절대 금지

**최상위 순서 계약: 여기까지 끝나기 전에는 이미지 생성·수정 도구를 호출하지 않는다.**
이 ZIP에서 제작할 자산은 {mode}/{asset} 한 종류뿐이다.

1. ZIP을 전부 열어 **14개 MD를 파일명만이 아니라 본문 마지막 줄까지 전부 읽는다.**
   00/01/02/03/04/05/06/07/08/09/10/11의 우선순위·금지사항·자산 범위를 대조한다.
2. 사용자 첨부 원화·BODY 기준 이미지·예시와 참고 이미지를 **모두 실제 비전으로 연다.**
   05_OFFICIAL_REFERENCES.md, 06_ADVANCED_OFFICIAL_COMMUNITY.md,
   11_OFFICIAL_IMAGE_EXAMPLES.md 및 다른 MD에 링크된 그림·작품 페이지도 확인한다.
   작품 페이지는 제목/HTML을 읽는 데서 멈추지 말고 **보이는 이미지까지 열어** 확인한다.
3. 이미지마다 URL/원본 파일, 실제 열람 상태, 얼굴·눈·목·어깨·상체 구도·선화 등
   **직접 관찰한 해당 자산의 특징**을 간단히 기록한다. URL만 알고 있는 것은 열람이 아니다.
4. 구형 FACE-FIRST 극단적 크롭, 회색 도형 몸체 등 문서 간 충돌을 찾아
   사용자 요구를 최우선으로 정리하고 최종 프레이밍·레이어 범위를 확정한다.
5. **생성 이전 첫 응답은 이미지가 아니라** 14개 MD 확인 내역,
   참고 이미지 전체 열람 내역, 실제 관찰과 충돌 해결 기록·제작 계획으로 작성한다.
   전부 확인 전에는 image_gen, OpenArt, Adobe, Canva 등 **모든 생성/수정 호출 금지**.
6. 자료 접근이 안 되거나 참고 그림이 보이지 않으면 **생성 중단** 후
   확인할 수 없는 항목을 구체적으로 보고하고 원본 이미지 첨부를 요청한다.
   허위 열람 완료나 임의 참고 그림 대체 금지.
7. 모든 자료가 실제 확인되고 충돌이 해결된 뒤에만 완성 원화 한 장 제작.
   그 원화의 품질 확인 후 파츠 분리/PSD 제작/합성·최종 ZIP 검수로 진행한다.

**기존 문서의 '즉시/먼저 원화 생성'은 이 열람 게이트 완료 이후만 뜻한다.**
**GPT가 이 문서를 읽기 전에 이미지를 생성했다면 그 출력은 납품 실패다.**

"""


def references(docs: dict[str, str]) -> list[str]:
    links = set()
    for name, text in docs.items():
        if name in REFERENCES:
            links.update(v.rstrip(".,;:!") for v in URL.findall(text))
        links.update(v.rstrip(".,;:!") for v in IMAGE.findall(text))
    return sorted(links)


def read_zip(path: Path):
    with ZipFile(path) as z:
        infos = z.infolist()
        names = [i.filename for i in infos]
        if (len(names) != 14 or len(set(names)) != 14 or
                set(names) != set(DOC_NAMES) or z.testzip() is not None):
            raise ValueError("Invalid 14-MD ZIP/CRC: " + path.name)
        return infos, {n: z.read(n).decode("utf-8") for n in names}


def patch(path: Path, *, write: bool) -> bool:
    infos, docs = read_zip(path)
    mode, asset = path.stem.rsplit("__", 1)
    if mode not in MODES or asset not in ASSETS:
        raise ValueError("Unknown mode/asset: " + path.name)
    header = banner(mode, asset)
    done = [n for n in PRIORITY if docs[n].startswith(header)]
    if 0 < len(done) < len(PRIORITY):
        raise ValueError("Partially applied read-first gate: " + path.name)
    if len(done) == len(PRIORITY):
        return False
    if not write:
        raise ValueError("Missing read-first gate: " + path.name)
    modified = {n: (header + value if n in PRIORITY else value)
                for n, value in docs.items()}
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(prefix="image-ai-read-first-", suffix=".zip",
                                         dir=path.parent, delete=False) as handle:
            tmp = Path(handle.name)
        with ZipFile(tmp, "w") as z:
            for info in infos:
                z.writestr(info, modified[info.filename].encode("utf-8"))
        _, checked = read_zip(tmp)
        if checked != modified:
            raise ValueError("Repacked ZIP content differs: " + path.name)
        os.replace(tmp, path)
        tmp = None
        return True
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)


def manifest(path: Path) -> dict:
    _, docs = read_zip(path)
    mode, asset = path.stem.rsplit("__", 1)
    if any(not docs[n].startswith(banner(mode, asset)) for n in PRIORITY):
        raise ValueError("Published read-first gate missing")
    return {"schema": "image-ai/read-first-v1", "zip_name": path.name,
            "documents": {n: sha256(docs[n].encode()).hexdigest() for n in DOC_NAMES},
            "reference_urls": references(docs)}


def verify_evidence(path: Path, evidence: dict) -> dict:
    """Evidence validation, not proof the external AI actually saw pixels."""
    expected = manifest(path)
    if evidence.get("schema") != expected["schema"] or evidence.get("zip_name") != path.name:
        raise ValueError("Read-first evidence ZIP identity mismatch")
    if evidence.get("documents") != expected["documents"]:
        raise ValueError("All 14 MD checksums must match the reviewed ZIP")
    observations = evidence.get("references")
    if not isinstance(observations, dict) or set(observations) != set(expected["reference_urls"]):
        raise ValueError("Reference observations incomplete")
    for url, observation in observations.items():
        if (not isinstance(observation, dict) or
                observation.get("status") != "visually_reviewed" or
                len(str(observation.get("observed_details", "")).strip()) < 30):
            raise ValueError("Reference image unreviewed: " + url)
    if evidence.get("conflicts_resolved") is not True:
        raise ValueError("Instruction conflicts unresolved")
    if not str(evidence.get("art_direction", "")).strip():
        raise ValueError("Art direction not recorded")
    return {"status": "EVIDENCE_RECORD_COMPLETE_NOT_PIXEL_PROOF",
            "documents": 14, "reference_urls": len(observations)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    one = parser.add_mutually_exclusive_group(required=True)
    one.add_argument("--check", action="store_true")
    one.add_argument("--write", action="store_true")
    one.add_argument("--manifest", type=Path)
    one.add_argument("--verify-evidence", nargs=2, metavar=("ZIP", "JSON"))
    args = parser.parse_args()
    if args.manifest:
        print(json.dumps(manifest(args.manifest), indent=2, ensure_ascii=False))
        return 0
    if args.verify_evidence:
        file, evidence = map(Path, args.verify_evidence)
        print(json.dumps(verify_evidence(file, json.loads(evidence.read_text(encoding="utf-8")))))
        return 0
    expected = {f"{m}__{a}.zip" for m in MODES for a in ASSETS}
    actual = {p.name for p in ROOT.glob("*.zip")}
    if actual != expected:
        raise ValueError(f"ZIP set differs: missing={expected-actual}, extra={actual-expected}")
    changes = sum(patch(ROOT / filename, write=args.write) for filename in sorted(expected))
    print(f"PASS: 24 ZIPs x 14 MD, patched={changes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
