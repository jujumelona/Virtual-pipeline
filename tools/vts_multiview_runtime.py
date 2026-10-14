"""Multi-view artwork validation and external open-source 2D integration.

This module belongs to the Colab *runtime*, never the 24 image-AI instruction ZIPs.
It does not claim that supplementary angle drawings have been transferred into
Cubism deformers; those need true keyform authoring and native pose rendering.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
from zipfile import ZipFile

REPO_URL = "https://github.com/Wzhang3912/image2live2d.git"
# Resolved public main on 2026-10-14. Do not silently float to a new upstream.
REPO_COMMIT = "714e7cc9191f1ef6c9a1732c80e8b566ec127d6b"

VIEW_SETS = {
    "body": ("head_three_quarter_L", "head_three_quarter_R",
             "head_profile_L", "head_profile_R", "neck_underpaint"),
    "hair": ("hair_three_quarter_L", "hair_three_quarter_R",
             "hair_profile_L", "hair_profile_R", "hair_back", "hair_underlayers"),
    "outfit": ("outfit_three_quarter_L", "outfit_three_quarter_R",
               "outfit_profile_L", "outfit_profile_R", "outfit_back",
               "outfit_inside_seams"),
    "accessory": ("accessory_three_quarter_L", "accessory_three_quarter_R",
                  "accessory_profile_L", "accessory_profile_R",
                  "accessory_back", "accessory_attachment_anchor"),
}
VIEWS_FOR_3D = ("front", "front_three_quarter_L", "left", "back_three_quarter_L",
                "back", "back_three_quarter_R", "right", "front_three_quarter_R")
PART_FAMILIES = {
    "body": {"face", "head", "eyes", "eye", "brow", "eyebrow", "nose", "mouth",
             "neck", "torso", "body", "arm", "hand", "ear", "pelvis", "leg", "foot"},
    "hair": {"hair"},
    "outfit": {"outfit", "cloth", "sleeve", "clothing", "garment"},
    "accessory": {"accessory", "ornament", "object", "prop"},
}

def _write_json(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
    return path

def _safe_view_name(name: str) -> tuple[str, str] | None:
    p = PurePosixPath(name)
    if (p.is_absolute() or ".." in p.parts or "\\" in name
            or len(p.parts) > 4 or p.suffix.lower() != ".png"):
        return None
    if len(p.parts) >= 2 and p.parts[-2] in ("reference_views", "views"):
        return p.parts[-2], p.stem
    return None

def _difference_hash(image) -> int:
    from PIL import Image
    im = image.convert("RGBA")
    # Transparent artwork is compared against gray, not an RGB black fill.
    bg = Image.new("RGBA", im.size, (238, 238, 238, 255))
    bg.alpha_composite(im)
    gray = bg.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    data = list(gray.getdata())
    bits = 0
    for y in range(8):
        for x in range(8):
            bits = (bits << 1) | int(data[y * 9 + x] > data[y * 9 + x + 1])
    return bits

def _check_view_members(source: Path, *, asset: str, output: Path,
                        required: bool = True) -> dict:
    """Extract useful *artwork* views, verify real PNGs, refuse duplicates.

    A reference is not a rig/keyform; downstream preview must use an actual
    model and must not mark source visual quality as validated.
    """
    if asset not in VIEW_SETS:
        raise ValueError("Invalid asset " + asset)
    from PIL import Image, ImageOps
    output.mkdir(parents=True, exist_ok=True)
    observed: dict[str, dict] = {}
    failures = []
    raw_max = 0
    with ZipFile(source) as archive:
        infos = [i for i in archive.infolist() if not i.is_dir()]
        if len(infos) > 600 or sum(i.file_size for i in infos) > 1024**3:
            raise ValueError("MULTIVIEW_ZIP_TOO_LARGE")
        for item in infos:
            pair = _safe_view_name(item.filename)
            if not pair:
                continue
            _, stem = pair
            if (stem in observed or item.file_size > 48_000_000 or
                    (item.external_attr >> 16) & 0o170000 == 0o120000):
                raise ValueError("MULTIVIEW_DUPLICATE_OR_UNSAFE_FILE: " + item.filename)
            data = archive.read(item)
            raw_max += len(data)
            if raw_max > 250_000_000:
                raise ValueError("MULTIVIEW_REFERENCE_BUDGET_EXCEEDED")
            try:
                with Image.open(io.BytesIO(data)) as image:
                    if (image.format != "PNG" or min(image.size) < 128
                            or max(image.size) > 16384):
                        raise ValueError("Invalid PNG dimensions or format")
                    image.load()
                    dhash = _difference_hash(image)
                    md5 = hashlib.sha256(image.convert("RGBA").tobytes()).hexdigest()
            except (OSError, ValueError) as error:
                raise ValueError("MULTIVIEW_REFERENCE_INVALID: " + item.filename) from error
            destination = output / (stem + ".png")
            destination.write_bytes(data)
            observed[stem] = {
                "source": item.filename, "file": str(destination),
                "sha256": hashlib.sha256(data).hexdigest(),
                "pixel_sha256": md5, "dhash": f"{dhash:016x}",
            }
    expected = VIEW_SETS[asset]
    missing = [name for name in expected if name not in observed]
    exact = {}
    for name, info in observed.items():
        exact.setdefault(info["pixel_sha256"], []).append(name)
    duplicates = [names for names in exact.values() if len(names) > 1]
    if duplicates:
        failures.append({"code": "MULTIVIEW_COPIED_FRAME", "groups": duplicates})
    # Close perceptual hashes are a review flag only: some valid reference
    # crops may look nearly identical. Never claim automatic identity PASS.
    similar = []
    candidates = [x for x in expected if x in observed]
    for i, left in enumerate(candidates):
        for right in candidates[i + 1:]:
            distance = (int(observed[left]["dhash"], 16)
                        ^ int(observed[right]["dhash"], 16)).bit_count()
            if distance <= 1:
                similar.append({"left": left, "right": right, "distance": distance})
    if missing and required:
        failures.append({"code": "MULTIVIEW_REQUIRED_ART_MISSING", "names": missing})
    if not observed and required:
        failures.append({"code": "MULTIVIEW_NO_REFERENCES"})
    report = {
        "schema": "vtuber/multiview-artwork-input-v1",
        "asset": asset, "observed": observed,
        "missing_required": missing, "near_duplicates_review": similar,
        "errors": failures, "valid": not failures,
        "character_identity_verified": False,
        "reference_angles_used_as_rig_keyforms": False,
        "note": "Auxiliary art; angle guidance alone cannot move a native rig.",
    }
    _write_json(output / "multiview_manifest.json", report)
    if failures:
        raise RuntimeError("MULTIVIEW_ARTWORK_NEEDS_REGENERATION: "
                           + json.dumps(failures, ensure_ascii=False)
                           + "; see " + str(output / "multiview_manifest.json"))
    return report

def validate_artwork_parts(parts: list[dict], canvas: tuple[int, int], *,
                           asset: str) -> dict:
    """Reject known semantic cross-contamination before model installation."""
    from PIL import Image
    if asset not in PART_FAMILIES:
        raise ValueError("Invalid asset")
    allowed = PART_FAMILIES[asset]
    ids = [str(p["id"]).casefold() for p in parts]
    if len(ids) != len(set(ids)):
        raise ValueError("PART_IDS_NOT_UNIQUE")
    families = [re.split(r"[._ -]+", name)[0] for name in ids]
    unexpected = [name for name, family in zip(ids, families)
                  if family not in allowed]
    if unexpected:
        raise RuntimeError("ARTWORK_PART_CROSS_ASSET_CONTAMINATION: " + str(unexpected[:16]))
    if asset == "body":
        must = {"neck", "face"}
        missing = sorted(f for f in must if not any(x == f or x.startswith(f + "_")
                                                    or x.startswith(f + ".") for x in ids))
        if missing:
            raise RuntimeError("BODY_MISSING_ANATOMICAL_PARTS: " + str(missing))
        if not any(f in {"torso", "body"} for f in families):
            raise RuntimeError("BODY_MISSING_TORSO_PART")
        for family in ("eye", "arm", "hand"):
            if not any(x == family or x.startswith(family + "_")
                       or x.startswith(family + ".") for x in ids):
                raise RuntimeError("BODY_MISSING_RIG_COMPONENT: " + family)
        from tools.vts_native_visual_quality import require_live2d_body_underpaint
        neck = require_live2d_body_underpaint(parts, canvas)
    else:
        neck = {"status": "NOT_BODY"}
    return {"status": "SEMANTIC_SOURCE_PREFLIGHT_PASS",
            "parts": len(ids), "neck": neck, "visual_quality_verified": False}

def prepare_multiview_input(source: Path, output: Path, *, asset: str, edition: str,
                            require_views: bool = True) -> dict:
    """Entry point for Colab before launching See-through or an auto-rigger."""
    source = Path(source).resolve(strict=True)
    from tools.vts_ai_pack_import import inspect_large_ai_pack
    info = inspect_large_ai_pack(source, edition=edition)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    view = _check_view_members(source, asset=asset, output=output / "reference_views",
                               required=require_views)
    part = validate_artwork_parts(info["parts"], info["canvas"], asset=asset)
    report = {"schema": "vtuber/colab-art-to-rig-preflight-v1",
              "source": str(source), "asset": asset, "edition": edition,
              "views": view, "parts": part, "state": "SOURCE_ART_VALIDATED_NOT_RIGGED"}
    _write_json(output / "artwork_preflight.json", report)
    return report

def ensure_image2live2d(*, home: Path | None = None, python: str | None = None,
                         timeout_seconds: int = 1200) -> Path:
    """Install a pinned independent QA/secondary-rig implementation.

    External Apache-2.0 source is kept outside our repository.
    """
    home = Path(home or os.environ.get("VTS_IMAGE2LIVE2D_HOME",
                "/content/vtuber_builder/third_party/image2live2d")).resolve()
    py = str(python or sys.executable)
    if not (home / "src/image2live2d/preview.py").is_file():
        if home.exists() and any(home.iterdir()):
            raise RuntimeError("IMAGE2LIVE2D_UNRECOGNIZED_SOURCE: " + str(home))
        home.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "--filter=blob:none",
                        REPO_URL, str(home)], check=True, timeout=300)
        subprocess.run(["git", "-C", str(home), "checkout", "--detach", REPO_COMMIT],
                       check=True, timeout=120)
    if (home / ".git").is_dir():
        revision = subprocess.run(["git", "-C", str(home), "rev-parse", "HEAD"],
                                  capture_output=True, text=True, check=True, timeout=15).stdout.strip()
        if revision != REPO_COMMIT:
            raise RuntimeError("IMAGE2LIVE2D_REVISION_MISMATCH: " + revision)
    if not (home / ".vts_ready").is_file():
        subprocess.run([py, "-m", "pip", "install", "--disable-pip-version-check",
                        "-e", str(home) + "[decompose]"],
                       check=True, timeout=timeout_seconds)
        (home / ".vts_ready").write_text(REPO_COMMIT + "\n", encoding="utf-8")
    return home

def render_independent_pose_preview(psd: Path, output: Path, *, home: Path | None = None,
                                    timeout_seconds: int = 900) -> dict:
    """Render an *independent image2live2d rig*, NOT the PSD2Live MOC3.

    The images provide useful movement risk signals, but cannot certify the
    other backend. A missing/broken renderer fails explicitly, no fake views.
    """
    home = ensure_image2live2d(home=home)
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    log = output / "pose_preview.log"
    cmd = [sys.executable, "-u", "-m", "tools.vts_independent_pose_worker",
           "--psd", str(Path(psd).resolve(strict=True)),
           "--output", str(output)]
    with log.open("w", encoding="utf-8") as stream:
        process = subprocess.run(cmd, cwd=Path(__file__).resolve().parents[1],
                                 stdout=stream, stderr=subprocess.STDOUT,
                                 timeout=timeout_seconds, check=False)
    if process.returncode:
        raise RuntimeError("INDEPENDENT_POSE_PREVIEW_FAILED: " + str(log))
    report_file = output / "pose_review.json"
    if not report_file.is_file():
        raise RuntimeError("INDEPENDENT_POSE_REPORT_MISSING")
    report = json.loads(report_file.read_text(encoding="utf-8"))
    if report.get("source") != "image2live2d_independent_rig" or not report.get("frames"):
        raise RuntimeError("INDEPENDENT_POSE_REPORT_INVALID")
    return report

def write_handoff_verdict(output: Path, *, source_report: dict,
                          rig_result: dict, pose_report: dict | None = None) -> dict:
    """Never equate a structural MOC3 check or a second rig's pose to visual QA."""
    output = Path(output)
    report = {
        "schema": "vtuber/native-quality-verdict-v1",
        "artwork_source_ready": bool(source_report["parts"]["status"]),
        "native_rig_artifacts_created": bool(rig_result.get("moc3_generated")),
        "native_reference_files_valid": bool(
            (rig_result.get("psd2live") or {}).get("runtime_references_valid")),
        "independent_pose_reference": pose_report,
        "actual_native_pose_rendered": False,
        "vts_runtime_verified": False,
        "artistic_quality_verified": False,
        "state": "NATIVE_MODEL_CREATED_VISUAL_REVIEW_REQUIRED",
        "blockers": [
            "Real PSD2Live MOC3 parameter poses not rendered in Cubism Core",
            "VTube Studio live tracking not exercised",
            "Auxiliary multi-view drawings are not automatically keyed to deformers",
        ],
    }
    _write_json(output / "quality_verdict.json", report)
    return report
