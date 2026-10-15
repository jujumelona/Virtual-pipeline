"""Audit every published image-generating kit's actual 14 markdown files.

This scans all 336 UTF-8 documents, including older actionable instructions
outside the newest appended [SOURCE_ONLY] block. A PASS is textual consistency,
not actual image/PSD template observation or rig QA.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1] / "docs/image_ai_kits_v2/zips"
MODES = ("live2d_bust_up", "live2d_upper", "live2d_full",
         "inochi2d_upper", "inochi2d_full", "3d")
ASSETS = ("body", "hair", "outfit", "accessory")
EXPECTED = {
    "00_MASTER_FIRST.md", "00_DELIVERY_AND_RECHECK.md", "00_READ_FIRST.md",
    "01_COMMON_RULES.md", "02_ADVANCED_PARTS.md", "03_MODE_RULES.md",
    "04_OUTPUT_FILES.md", "05_OFFICIAL_REFERENCES.md",
    "06_ADVANCED_OFFICIAL_COMMUNITY.md", "07_REVIEW_BEFORE_FINAL_ZIP.md",
    "08_PRACTICAL_TIPS.md", "09_VISUAL_ART_QUALITY.md",
    "10_ANIME_STYLE.md", "11_OFFICIAL_IMAGE_EXAMPLES.md",
}
# Terms that definitely demand outputs in the wrong production stage.
BAD_2D = {
    "old_multiview_contract": re.compile(r"\[IMAGE_ART_MULTIVIEW_SOURCE_ONLY_V1\]"),
    "old_split_png_paths": re.compile(r"isolated_parts/|underpaint_parts/"),
    "old_order_file": re.compile(r"(?:^|[^a-z_])layer_order\.txt"),
    "old_mask_delivery": re.compile(r"(?:PNG.{0,30})?(?:알파\s*마스크|마스크\s*(?:PNG|파일|이미지|납품)|마스크/레이어)"),
    "old_psd_must_deliver": re.compile(r"(?:PSD.{0,12}(?:필수|납품|만들|생성|저장|제출|완성|편집|작성)|다층 PSD|레이어 PSD|PSD 레이어|PSD·투명|PSD·PNG)"),
    "master_only_no_parts": re.compile(r"파츠(?:별|를|는|의)?.{0,25}(?:생성|그리|제작).{0,20}(?:금지|맡기지\s*않|하지\s*않)|개별\s*(?:PNG|파츠).{0,12}(?:금지|만들지\s*않)"),
    "legacy_2d_delivery": re.compile(r"(?:최종 ZIP|결과 ZIP|납품).{0,40}(?:PSD|isolated_parts|layer_order)"),
}
BAD_3D = {
    "legacy_2d_rig_output": re.compile(r"(?:PSD|ArtMesh|moc3|Cubism).{0,20}(?:필수|생성|제작|납품)"),
    "old_split_png_paths": re.compile(r"isolated_parts/|underpaint_parts/|layer_order\.txt"),
}
SHOULD_2D = ("ONE_PART_PER_GENERATION_V1", "part_art/_order.txt",
             "outputs/master.png")
SHOULD_3D = ("views/", "3D", "MATTE_CLAY_BODY_V1")
# Matching bibliographies explains methods; output instructions there are still
# suspect but links or negative sentences need separate interpretation.
MUST_IGNORE_LINE = re.compile(
    r"(?:https?://|과거|구버전|이전|금지|요구하지|생성하지|제작하지|납품하지|"
    r"가정하지|참고만|링크|출처|권한|라이선스|예제에|예시.*(?:PSD|레이어))"
)


def scan() -> dict:
    issues, inventory, highlights = [], [], defaultdict(list)
    for mode in MODES:
        for asset in ASSETS:
            key = mode + "__" + asset
            path = ROOT / (key + ".zip")
            if not path.is_file():
                issues.append(dict(kit=key, document="", code="missing_zip"))
                continue
            with ZipFile(path) as z:
                names = z.namelist()
                if (len(names) != 14 or set(names) != EXPECTED or
                        len(set(names)) != len(names) or z.testzip() is not None):
                    issues.append(dict(kit=key, document="", code="bad_zip_structure"))
                    continue
                for name in sorted(names):
                    doc = z.read(name).decode("utf-8-sig")
                    lines = doc.splitlines()
                    inventory.append(dict(kit=key, document=name, bytes=len(doc.encode()),
                                          lines=len(lines)))
                    if mode != "3d":
                        expected = SHOULD_2D
                        patterns = BAD_2D
                    else:
                        expected = SHOULD_3D
                        patterns = BAD_3D
                    for missing in expected:
                        if missing not in doc and (mode != "3d" or name == "04_OUTPUT_FILES.md"):
                            issues.append(dict(kit=key, document=name,
                                               code="required_marker_missing", excerpt=missing))
                    for mark in ("[IMAGE_AI_SOURCE_ONLY_V2]", "[/IMAGE_AI_SOURCE_ONLY_V2]"):
                        if mode != "3d" and doc.count(mark) != 1:
                            issues.append(dict(kit=key, document=name, code="source_marker_count",
                                               excerpt=mark + "=" + str(doc.count(mark))))
                    if mode != "3d" and name == "04_OUTPUT_FILES.md":
                        if not ("part_art/_order.txt" in doc and
                                "part_art/" in doc):
                            issues.append(dict(kit=key, document=name,
                                               code="old_output_contract"))
                    if mode != "3d" and asset != "body" and "part_art/mouth." in doc:
                        issues.append(dict(kit=key, document=name,
                                           code="body_part_example_in_non_body"))
                    for i, line in enumerate(lines, 1):
                        if line.strip().startswith("#") and line.strip().endswith("]"):
                            pass
                        for code, rx in patterns.items():
                            if not rx.search(line):
                                continue
                            if MUST_IGNORE_LINE.search(line) and not line.lstrip().startswith("- **"):
                                # Keep suspicious occurrences visible as review,
                                # but don't claim an instruction violation.
                                severity = "review"
                            else:
                                severity = "blocker"
                            issue = dict(kit=key, document=name, line=i,
                                         code=code, severity=severity, excerpt=line.strip()[:240])
                            issues.append(issue)
                            if len(highlights[code]) < 8:
                                highlights[code].append(issue)
    blockers = [x for x in issues if x.get("severity", "blocker") == "blocker"]
    reviews = [x for x in issues if x.get("severity") == "review"]
    return {
        "schema": "vtuber/all-24-image-kits-semantic-audit-v1",
        "kits": len({x["kit"] for x in inventory}),
        "documents": len(inventory),
        "counts_by_code": dict(Counter(x["code"] for x in issues)),
        "blockers": len(blockers), "reviews": len(reviews),
        "matrix": [
            {"kit": mode + "__" + asset,
             "blockers": sum(x["kit"] == mode + "__" + asset for x in blockers),
             "reviews": sum(x["kit"] == mode + "__" + asset for x in reviews)}
            for mode in MODES for asset in ASSETS
        ],
        "sample_issues": dict(highlights),
        "issues": issues,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = scan()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    summary = {k: v for k, v in report.items() if k not in ("issues",)}
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if args.strict and (report["blockers"] or report["documents"] != 336):
        raise SystemExit("CONTRADICTORY_KIT_CONTENT")

if __name__ == "__main__":
    main()
