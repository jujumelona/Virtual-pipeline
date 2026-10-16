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
    # Exact image-AI source contracts authored by
    # tools/apply_image_ai_multiview_briefs.py (all 20 2D ZIPs).
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
VIEWS_FOR_3D = ("front", "front_three_quarter_L", "left", "back_three_quarter_L",
                "back", "back_three_quarter_R", "right", "front_three_quarter_R")
PART_FAMILIES = {
    "body": {"face", "head", "eyes", "eye", "brow", "eyebrow", "nose", "mouth",
             "eyewhite", "eyelash", "irides", "pupil", "blush",
             "neck", "torso", "body", "arm", "hand", "ear", "pelvis", "leg", "foot",
             "skin", "scalp", "jaw", "shoulder", "forearm"},
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
                        required: bool = True,
                        master_canvas: tuple[int, int] | None = None) -> dict:
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
                    canvas_of_view = image.size
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
                "size": list(canvas_of_view),
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
    if master_canvas is not None:
        # Face/neck/shoulder geometry cannot be registered to front art if
        # each rotation reference was generated on an unrelated crop/scale.
        # Detail-only occlusion drawings remain exempt from this rule.
        alignment_names = [
            name for name in expected if name in observed and
            (name.endswith(("front", "three_quarter_L", "three_quarter_R",
                            "profile_L", "profile_R", "pitch_up", "pitch_down"))
             or name == "body_front")
        ]
        mismatches = [
            {"name": n, "observed_size": observed[n]["size"],
             "master_size": list(master_canvas)}
            for n in alignment_names
            if tuple(observed[n]["size"]) != tuple(master_canvas)
        ]
        if mismatches:
            failures.append({"code": "MULTIVIEW_RIG_ALIGNMENT_CANVAS_MISMATCH",
                             "examples": mismatches})
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
        "side_profile_neck_connection_visually_verified": False,
        "side_profile_head_yaw_90_native_supported": False,
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
                           asset: str, underpaint_parts: list[dict] | None = None) -> dict:
    """Reject known semantic cross-contamination before model installation."""
    from PIL import Image
    if asset not in PART_FAMILIES:
        raise ValueError("Invalid asset")
    allowed = PART_FAMILIES[asset]
    ids = [str(p["id"]).casefold() for p in parts]
    if len(ids) != len(set(ids)):
        raise ValueError("PART_IDS_NOT_UNIQUE")
    # A compound anatomical name must be classified as one BODY component.
    # Splitting upper_arm_L at the first underscore yields the unrelated
    # family "upper" and incorrectly rejects valid VTuber shoulder/arm rigs.
    # Do NOT broadly allow any prefix "upper": e.g. upper_outfit is not BODY.
    def semantic_family(name: str) -> str:
        if re.match(r"^upper[._ -]+arm(?:[._ -]|$)", name):
            return "arm"
        return re.split(r"[._ -]+", name)[0]

    families = [semantic_family(name) for name in ids]
    # BODY can legitimately include a removable non-anatomical privacy
    # overlay. Do not accept arbitrary unrelated costumes or accessories.
    permitted_body_overlay = {
        "removable_neutral_modesty_band",  # Legacy single nontransparent cover.
        "removable_neutral_modesty_band_upper",
        "removable_neutral_modesty_band_lower",
    }
    unexpected = [name for name, family in zip(ids, families)
                  if family not in allowed and not (
                      asset == "body" and name in permitted_body_overlay)]
    if unexpected:
        raise RuntimeError("ARTWORK_PART_CROSS_ASSET_CONTAMINATION: " + str(unexpected[:16]))
    if asset == "body":
        # A bust-up need not fabricate an invisible lower garment. If a
        # lower garment is visible, its upper companion is still required.
        # Actual clothed artwork pixels need separate visual inspection.
        upper = "removable_neutral_modesty_band_upper"
        lower = "removable_neutral_modesty_band_lower"
        if lower in ids and upper not in ids:
            raise RuntimeError("BODY_SWIMWEAR_UPPER_PART_MISSING")
        if "neck" not in families or not ({"face", "head"} & set(families)):
            raise RuntimeError("BODY_MISSING_ANATOMICAL_PARTS: need neck and face/head")
        if "mouth" not in families:
            raise RuntimeError("BODY_MISSING_MOUTH_PART")
        if not any(f in {"torso", "body"} for f in families):
            raise RuntimeError("BODY_MISSING_TORSO_PART")
        for family in ("eye", "arm", "hand"):
            if not any(observed == family or
                       (family == "arm" and observed == "forearm")
                       for observed in families):
                raise RuntimeError("BODY_MISSING_RIG_COMPONENT: " + family)
        from tools.vts_native_visual_quality import require_live2d_body_underpaint
        # Explicit hidden neck underpaint may contain the required seam pixels.
        # It is intentionally OFF in neutral layer_order.txt, but survives as
        # an invisible editable PSD layer for actual head/neck deformation.
        hidden_neck = [p for p in (underpaint_parts or [])
                       if str(p.get("id", "")).casefold() == "hidden_neck_underpaint"]
        try:
            neck = require_live2d_body_underpaint(parts, canvas)
        except ValueError as error:
            if (not str(error).startswith("AI_ARTWORK_NECK_BODY_UNDERPAINT_MISSING:")
                    or len(hidden_neck) != 1):
                raise
            neck = {"status": "HIDDEN_NECK_BRIDGE_GEOMETRY_PENDING_VALIDATION",
                    "editor_review_required": True}
        # A 2D neck must physically extend behind the jaw as well as the
        # torso. A purely touching alpha edge is not occlusion-safe.
        import numpy as np
        def alpha_mask(record):
            canvas_alpha = Image.new("L", canvas, 0)
            canvas_alpha.paste(record["image"].convert("RGBA").getchannel("A"),
                               (int(record["left"]), int(record["top"])))
            return np.asarray(canvas_alpha) > 10
        face_parts = [p for p in parts if re.split(r"[._ -]+", str(p["id"]).casefold())[0] in ("face", "head")]
        neck_parts = [p for p in parts if re.split(r"[._ -]+", str(p["id"]).casefold())[0] == "neck"]
        face_alpha = np.zeros((canvas[1], canvas[0]), dtype=bool)
        neck_alpha = np.zeros_like(face_alpha)
        for p in face_parts:
            face_alpha |= alpha_mask(p)
        for p in neck_parts:
            neck_alpha |= alpha_mask(p)
        overlap = int(np.count_nonzero(face_alpha & neck_alpha))
        if overlap == 0 or neck["status"] == "HIDDEN_NECK_BRIDGE_GEOMETRY_PENDING_VALIDATION":
            if len(hidden_neck) != 1:
                if overlap == 0:
                    raise RuntimeError("ARTWORK_JAW_NECK_UNDERPAINT_MISSING: no face-neck alpha overlap")
                raise RuntimeError("AI_ARTWORK_NECK_BODY_UNDERPAINT_MISSING: missing painted neck-torso overlap")
            hidden_alpha = alpha_mask(hidden_neck[0])
            torso_parts = [p for p in parts if semantic_family(str(p["id"]).casefold()) in ("torso", "body")]
            jaw_parts = [p for p in parts if semantic_family(str(p["id"]).casefold()) == "jaw"]
            torso_alpha = np.zeros_like(neck_alpha)
            jaw_alpha = face_alpha.copy()
            for p in torso_parts:
                torso_alpha |= alpha_mask(p)
            for p in jaw_parts:
                jaw_alpha |= alpha_mask(p)
            # Unlike a token bypass, physically require the hidden paint to
            # connect jaw, neck, and torso across all three seam regions.
            metrics = {
                "hidden_jaw_overlap_pixels": int(np.count_nonzero(hidden_alpha & jaw_alpha)),
                "hidden_neck_overlap_pixels": int(np.count_nonzero(hidden_alpha & neck_alpha)),
                "hidden_torso_overlap_pixels": int(np.count_nonzero(hidden_alpha & torso_alpha)),
            }
            if min(metrics.values()) < 16:
                raise RuntimeError("ARTWORK_HIDDEN_NECK_BRIDGE_INCOMPLETE: " + str(metrics))
            neck.update(metrics)
            neck["status"] = "EXPLICIT_HIDDEN_NECK_BRIDGE_PRESENT_RIG_VISUAL_REVIEW_REQUIRED"
            neck["editor_review_required"] = True
        neck["face_neck_overlap_pixels"] = overlap
        for component in ("eye", "hand"):
            related = {"eye", "eyes", "eyewhite", "eyelash", "irides", "pupil"} if component == "eye" else {"hand"}
            members = [x for x, family in zip(ids, families) if family in related]
            side_tokens = [set(re.split(r"[._ -]+", x)) for x in members]
            for side, accepted in (("left", {"l", "left"}), ("right", {"r", "right"})):
                side_parts = [tokens for tokens in side_tokens if tokens & accepted]
                if not side_parts:
                    raise RuntimeError("ARTWORK_BILATERAL_PART_MISSING: "
                                       + component + "_" + side)
                if component == "eye":
                    # Separate moving eye strata prevent a flat iris blob from
                    # being stretched as an entire eye during yaw/blink.
                    for kind, aliases in (
                        ("iris", {"iris", "irides", "pupil"}),
                        ("white", {"white", "whites", "sclera", "eyewhite"}),
                        ("lash", {"lash", "lashes", "eyelash", "eyelid", "lid"}),
                    ):
                        if not any(tokens & aliases for tokens in side_parts):
                            raise RuntimeError("ARTWORK_EYE_STRATA_MISSING: "
                                               + side + "_" + kind)
    else:
        neck = {"status": "NOT_BODY"}
    return {"status": "SEMANTIC_SOURCE_PREFLIGHT_PASS",
            "parts": len(ids), "neck": neck, "visual_quality_verified": False}

def _write_artwork_regeneration_request(output: Path, *, asset: str,
                                       source: Path, error: Exception) -> Path:
    """Actionable handoff back to the external image-generating AI.

    Colab cannot silently launch ChatGPT/Gemini. Preserve the original
    failed artwork and request only the missing asset-specific art.
    """
    destination = output / "ARTWORK_REGENERATION_REQUEST.md"
    destination.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 대형 이미지 AI용 재작화 요청",
        "",
        f"- 자산: {asset}",
        f"- 제출 원화 ZIP: {source.name}",
        f"- 실제 검증 실패: {str(error)}",
        "",
        "이 문서는 Colab의 오픈소스 실행 코드가 아니라 외부 이미지 생성 AI에 전달할 오류 보고서다.",
        "해당 ZIP의 자산·모드 지침을 다시 모두 읽은 후 기존 캐릭터 정체성·캔버스·"
        "다른 정상 파츠를 보존하고 문제 영역만 실제로 재작화한다.",
        "투명색으로 덧칠하거나 누락 파츠를 기계적으로 늘려 실패를 숨기지 않는다.",
        "고친 원화·숨은 면·다각도 참고·독립 RGBA와 일관된 layer_order 및 master를 새 ZIP으로 제출한다.",
        "See-through/PSD2Live 프로그램을 이미지 생성 AI에서 실행하지 않는다.",
        "",
        "코드 확인: 이 오류가 해소되기 전에는 PSD2Live/Cubism 성공 판정 금지.",
    ]
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _write_json(output / "regeneration_issue.json", {
        "schema": "vtuber/artwork-regeneration-request-v1",
        "source": str(source), "asset": asset, "issue": str(error),
        "artifact": str(destination), "state": "AWAITING_EXTERNAL_IMAGE_REGENERATION",
    })
    return destination


def prepare_multiview_input(source: Path, output: Path, *, asset: str, edition: str,
                            require_views: bool = True) -> dict:
    """Entry point for Colab before launching See-through or an auto-rigger."""
    source = Path(source).resolve(strict=True)
    from tools.vts_ai_pack_import import inspect_large_ai_pack
    info = inspect_large_ai_pack(source, edition=edition)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    try:
        view = _check_view_members(source, asset=asset,
                                   output=output / "reference_views",
                                   required=require_views)
        part = validate_artwork_parts(info["parts"], info["canvas"], asset=asset,
                                      underpaint_parts=info.get("underpaint_parts", []))
    except (ValueError, RuntimeError) as error:
        request = _write_artwork_regeneration_request(
            output, asset=asset, source=source, error=error)
        raise RuntimeError(f"ARTWORK_REGENERATION_REQUIRED: {request}") from error
    # Compare authored visible composite against the AI's nominated master.
    # Extra hidden underpaint should disappear under correct draw order.
    import numpy as np
    from PIL import Image
    composite = Image.new("RGBA", info["canvas"], (0, 0, 0, 0))
    for record in info["parts"]:
        piece = Image.new("RGBA", info["canvas"], (0, 0, 0, 0))
        piece.alpha_composite(record["image"].convert("RGBA"),
                              (int(record["left"]), int(record["top"])))
        composite.alpha_composite(piece)
    master = info["master"].convert("RGBA")
    x = np.asarray(composite, dtype=np.int16)
    y = np.asarray(master, dtype=np.int16)
    support = (x[..., 3] > 10) | (y[..., 3] > 10)
    visible_rgb_mae = float(np.abs(x[..., :3] - y[..., :3])[support].mean()) if np.any(support) else 255.0
    alpha_mae = float(np.abs(x[..., 3] - y[..., 3]).mean())
    fidelity = {"rgb_visible_mae": round(visible_rgb_mae, 4),
                "alpha_mae": round(alpha_mae, 4),
                "measured_on": "neutral artwork composite",
                "display_state_transitions_verified": False}
    _write_json(output / "neutral_composite_fidelity.json", fidelity)
    if visible_rgb_mae > 12.0 or alpha_mae > 4.0:
        cause = RuntimeError("NEUTRAL_ARTWORK_PARTS_DONT_REBUILD_MASTER: "
                             + json.dumps(fidelity, ensure_ascii=False)
                             + "; redraw misplaced/duplicate layers")
        request = _write_artwork_regeneration_request(
            output, asset=asset, source=source, error=cause)
        raise RuntimeError(f"ARTWORK_REGENERATION_REQUIRED: {request}") from cause
    report = {"schema": "vtuber/colab-art-to-rig-preflight-v1",
              "source": str(source), "asset": asset, "edition": edition,
              "views": view, "parts": part, "neutral_composite": fidelity,
              "state": "SOURCE_ART_VALIDATED_NOT_RIGGED"}
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

def render_actual_native_moc3(model3: Path, output: Path, *,
                             timeout_seconds: int = 600) -> dict:
    """Render the *PSD2Live MOC3* through independent Cubism runtime wrappers.

    Missing GL/Core dependencies remain a flagged blocker, never fabricated
    screenshots. No Cubism Editor PRO installation is required for the renderer.
    """
    import importlib.util
    model3 = Path(model3).resolve(strict=True)
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    if os.environ.get("VTS_SKIP_NATIVE_POSE_RENDER") == "1":
        raise RuntimeError("NATIVE_POSE_RENDER_DISABLED_BY_USER")
    requirements = (
        ("live2d", "live2d-py"), ("pygame", "pygame"),
        ("OpenGL", "PyOpenGL"),
    )
    to_install = [package for module, package in requirements
                  if importlib.util.find_spec(module) is None]
    if to_install:
        subprocess.run([sys.executable, "-m", "pip", "install",
                        "--disable-pip-version-check", *to_install],
                       check=True, timeout=900)
    runner = shutil.which("xvfb-run")
    if not runner and sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        if os.name == "posix" and getattr(os, "geteuid", lambda: 1)() == 0:
            subprocess.run(["apt-get", "update", "-qq"], check=True, timeout=600)
            subprocess.run(["apt-get", "install", "-y", "xvfb", "xauth"],
                           check=True, timeout=600)
        runner = shutil.which("xvfb-run")
    if not runner and sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        raise RuntimeError("NATIVE_POSE_DISPLAY_REQUIRED: xvfb-run unavailable")
    args = [sys.executable, "-u", "-m", "tools.vts_native_moc_pose_worker",
            "--model3", str(model3), "--output", str(output)]
    if runner:
        args = [runner, "-a", *args]
    env = os.environ.copy()
    if runner:
        env.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")
    log = output / "native_pose.log"
    with log.open("w", encoding="utf-8") as stream:
        proc = subprocess.run(args, cwd=Path(__file__).resolve().parents[1],
                              env=env, stdout=stream, stderr=subprocess.STDOUT,
                              timeout=timeout_seconds, check=False)
    path = output / "native_pose_report.json"
    if not path.is_file():
        raise RuntimeError(f"NATIVE_POSE_RUNTIME_FAILED: exit={proc.returncode}; log={log}")
    report = json.loads(path.read_text(encoding="utf-8"))
    if proc.returncode or not report.get("native_pose_rendered") or not report.get("pose_activity_passed"):
        raise RuntimeError(f"NATIVE_POSE_QA_FAILED: exit={proc.returncode}; log={log}")
    return report


def write_handoff_verdict(output: Path, *, source_report: dict,
                          rig_result: dict, pose_report: dict | None = None,
                          native_pose_report: dict | None = None) -> dict:
    """Never equate a structural MOC3 check or a second rig's pose to visual QA."""
    output = Path(output)
    report = {
        "schema": "vtuber/native-quality-verdict-v1",
        "artwork_source_ready": bool(source_report["parts"]["status"]),
        "native_rig_artifacts_created": bool(rig_result.get("moc3_generated")),
        "native_reference_files_valid": bool(
            (rig_result.get("psd2live") or {}).get("runtime_references_valid")),
        "independent_pose_reference": pose_report,
        "actual_native_pose_rendered": bool(native_pose_report and native_pose_report.get("native_pose_rendered")),
        "native_pose_activity_passed": bool(native_pose_report and native_pose_report.get("pose_activity_passed")),
        "native_pose_report": native_pose_report,
        "vts_runtime_verified": False,
        "artistic_quality_verified": False,
        "state": ("NATIVE_POSE_FRAMES_CAPTURED_ART_REVIEW_REQUIRED"
                  if native_pose_report and native_pose_report.get("pose_activity_passed")
                  else "NATIVE_MODEL_CREATED_NATIVE_RENDER_NOT_VERIFIED"),
        "blockers": [
            "Native pose rendering missing or incomplete" if not native_pose_report else
            "Native screenshots require artist review for eye/neck seam correctness",
            "VTube Studio live tracking not exercised",
            "Auxiliary multi-view drawings are not automatically keyed to deformers",
        ],
    }
    _write_json(output / "quality_verdict.json", report)
    return report


def build_review_contact_sheet(reference_report: dict, pose_report: dict | None,
                               output: Path) -> Path:
    """Visually pair source views with secondary pose renders for review.

    Image2Live2D previews are explicitly NOT PSD2Live MOC3 pose screenshots.
    """
    from PIL import Image, ImageDraw, ImageFont
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    observed = reference_report["observed"]
    frame_by_pose = {x["pose"]: x["image"] for x in
                     (pose_report or {}).get("frames", [])}
    native = (pose_report or {}).get("source") == "live2d_py_cubism_native_runtime"
    rig_heading = ("NATIVE MOC3 (NOT VTS CERTIFIED)" if native else
                   "SECONDARY RIG (NOT CUBISM)")
    pairs = [
        ("head_three_quarter_L", "yaw_left_45" if native else "yaw_left"),
        ("head_three_quarter_R", "yaw_right_45" if native else "yaw_right"),
        # These are deliberately NOT equivalent angles. The left side is an
        # actual 90-degree artist reference; PSD2Live's rig is limited to 45.
        # Displaying them together exposes the missing profile authoring.
        ("head_profile_L", "yaw_left_45" if native else "yaw_left"),
        ("head_profile_R", "yaw_right_45" if native else "yaw_right"),
        ("head_pitch_up", "pitch_up"),
        ("head_pitch_down", "pitch_down"),
        ("neck_underpaint", "neutral"),
    ]
    width, boxh = 1100, 370
    canvas = Image.new("RGB", (width, boxh * len(pairs)), "#e6e7eb")
    draw = ImageDraw.Draw(canvas)
    for i, (ref_name, rig_pose) in enumerate(pairs):
        left = observed.get(ref_name, {}).get("file")
        right = frame_by_pose.get(rig_pose)
        for column, source in enumerate((left, right)):
            start_x, start_y = column * 550, i * boxh
            draw.rectangle((start_x + 4, start_y + 4, start_x + 546,
                            start_y + boxh - 4), fill="#ffffff")
            draw.text((start_x + 12, start_y + 10),
                      ("AI ART " + ref_name if column == 0 else
                       rig_heading + " " + rig_pose), fill="#242424")
            if source and Path(source).is_file():
                with Image.open(source) as picture:
                    image = picture.convert("RGBA")
                    image.thumbnail((520, 316))
                    base = Image.new("RGBA", image.size, (255, 255, 255, 255))
                    base.alpha_composite(image)
                    canvas.paste(base.convert("RGB"),
                                 (start_x + (550-image.width)//2, start_y+45))
            else:
                draw.text((start_x+20, start_y+80), "No image", fill="#b02020")
    canvas.save(output)
    return output

def package_detached_asset_from_ai(source: Path, imported: dict, output: Path,
                                   *, asset: str, body_reference: Path,
                                   source_qa: dict) -> dict:
    """Deliver a detached HAIR/OUTFIT/ACCESSORY PSD without faking a full avatar.

    This is not a Cubism FREE whole-character rig nor a PRO-licensed action:
    no Cubism Editor and no proprietary SDK required for PSD packaging.
    The uploaded body reference is a same-canvas alignment constraint.
    """
    if asset == "body" or asset not in VIEW_SETS:
        raise ValueError("DETACHED_ASSET_KIND_REQUIRED")
    from PIL import Image
    from zipfile import ZIP_DEFLATED
    body_reference = Path(body_reference).resolve(strict=True)
    with Image.open(body_reference) as reference, Image.open(imported["master"]) as art:
        if reference.size != art.size:
            raise ValueError("DETACHED_ASSET_BODY_CANVAS_MISMATCH")
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    destination = out / f"{asset}_detached_artwork.zip"
    if destination.exists():
        raise FileExistsError(destination)
    body_bytes_sha = hashlib.sha256(body_reference.read_bytes()).hexdigest()
    art_file = Path(imported["psd"]).resolve(strict=True)
    with ZipFile(destination, "w", ZIP_DEFLATED) as archive:
        archive.write(art_file, f"artwork/{asset}.psd")
        archive.write(Path(imported["master"]), "artwork/master.png")
        archive.write(body_reference, "reference/body" + body_reference.suffix.lower())
        archive.write(source, "input_reference/finished_ai_artwork.zip")
        archive.writestr("metadata/detached_asset.json", json.dumps({
            "schema": "vtuber/detached-2d-asset-v1",
            "asset": asset, "import_psd": f"artwork/{asset}.psd",
            "body_reference_sha256": body_bytes_sha,
            "body_reference_same_canvas": True,
            "rig_generated": False,
            "placement_art_quality_verified": False,
            "source_views_matched": bool(source_qa["views"]["valid"]),
            "segmentation_status": source_qa.get("parts", {}).get("status"),
            "extra_layer_refinement_verified": False,
            "note": "Detached PSD and original AI parts; attach to a complete "
                    "avatar and verify its actual movement. Not an MOC3.",
        }, ensure_ascii=False, indent=2))
        archive.writestr("README_RESULT.md",
                         "별도 자산의 원화 및 편집용 PSD입니다. PRO 라이선스 없이 "
                         "Colab에서 PSD 패키지를 준비합니다. 완성 캐릭터의 "
                         "실제 리깅·부착·추적 및 시각 품질은 확인되지 않았습니다.\n")
    with ZipFile(destination) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("DETACHED_ARTWORK_PACKAGE_INVALID")
    return {
        "state": "detached_artwork_ready_attachment_required",
        "package": str(destination), "moc3_generated": False,
        "editor_required": True, "source_artwork": str(art_file),
        "body_reference_sha256": body_bytes_sha,
        "notes": "No face-tracked model built from detached art.",
    }


def check_psd2live_body_semantics(metadata: dict) -> dict:
    """Catch skin/eye/limb tags lost between authored PSD and generated MOC3.

    The vendor can generate an animation for a recognized tag even when that
    tag names the WRONG source pixels. A non-empty MOC3 is not enough.
    """
    records = (metadata or {}).get("records") or []
    eyes = {"eyewhite": set(), "irides": set(), "eyelash": set()}
    limbs = set()
    for item in records:
        name = str(item.get("semantic_tag") or "")
        side = item.get("side")
        if name in eyes and side in {"l", "r"}:
            eyes[name].add(side)
        if name == "handwear" and side in {"l", "r"}:
            limbs.add(side)
    missing = []
    for kind, sides in eyes.items():
        missing.extend(kind + "_" + side for side in ("l", "r") if side not in sides)
    missing.extend("arm_hand_" + side for side in ("l", "r") if side not in limbs)
    report = {"schema": "vtuber/semantic-rig-binding-v1",
              "source_count": len(records),
              "eye_and_arm_sides": {**{k:sorted(v) for k,v in eyes.items()},
                                    "arm_hand": sorted(limbs)},
              "missing": missing, "passed": bool(records) and not missing}
    if not report["passed"]:
        raise RuntimeError("NATIVE_RIG_LAYER_ROLE_LOST: "
                           + json.dumps(report, ensure_ascii=False))
    return report


def process_completed_ai_2d_zip(source: Path, output: Path, *,
                                edition: str, scope: str, asset: str,
                                reference_image: Path | None = None,
                                require_views: bool = True,
                                mode: str | None = None) -> dict:
    """Single Colab entry: QA art, import PSD, reuse existing converter, review poses.

    All execution stays in Python. The original image-AI instructions are data,
    not executable backends. Actual MOC3 runtime proof still requires the app.
    """
    if edition not in ("free", "pro") or scope not in ("upper", "full"):
        raise ValueError("INVALID_2D_MODE")
    if asset not in VIEW_SETS:
        raise ValueError("INVALID_2D_ASSET")
    source = Path(source).resolve(strict=True)
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    from tools.vts_segmentation_profiles import (
        get_segmentation_profile, infer_live2d_mode,
        select_source_segmentation, write_segmentation_plan,
    )
    mode = mode or infer_live2d_mode(scope)
    if mode not in ("live2d_bust_up", "live2d_upper", "live2d_full"):
        raise ValueError("LIVE2D_SEGMENTATION_MODE_MISMATCH")
    if (scope == "full") != (mode == "live2d_full"):
        raise ValueError("LIVE2D_SEGMENTATION_FRAME_MISMATCH")
    select_source_segmentation(mode, asset)
    profile = write_segmentation_plan(mode, asset,
                                      output / "segmentation_plan.json")
    from tools.vts_source_only_pack import is_source_only_zip, prepare_source_only_2d
    source_only = is_source_only_zip(source)
    if source_only:
        preflight = prepare_source_only_2d(
            source, output / "source_qa", asset=asset)
        imported = None
    else:
        preflight = prepare_multiview_input(
            source, output / "source_qa", asset=asset, edition=edition,
            require_views=require_views)
        from tools.vts_ai_pack_import import prepare_large_ai_pack
        imported = prepare_large_ai_pack(source, output / "imported", edition=edition)
    if source_only and preflight.get("authored_parts_present"):
        from tools.vts_authored_part_art import assemble_authored_parts
        authored_report = assemble_authored_parts(
            source, Path(preflight["master"]), output / "authored_parts",
            asset=asset, edition=edition, scope=scope,
            enforce_required_parts=True)
        imported = {
            "master": Path(preflight["master"]),
            "psd": Path(authored_report["psd"]),
        }
        preflight["parts"] = {
            "status": "AI_AUTHORED_INDIVIDUAL_RGBA_PARTS_ASSEMBLED",
            "count": authored_report["independent_rgba_png_count"],
            "master_exactly_reconstructed":
                authored_report["neutral_exact_same_as_master"],
            "visual_quality_verified": False,
        }
        preflight["authored_part_art"] = authored_report
    preflight["segmentation_profile"] = profile
    # Authored RGBA/PSD takes precedence over See-through guesses. See-through
    # remains available in the image-only path in vts_production.
    # An isolated detachable layer pack cannot be routed into a FREE
    # whole-character avatar builder; it is a PSD attachment to a real body.
    if asset == "body":
        from tools.vts_production import make_cubism_handoff
        # Source-only ZIP: pass the original master to the existing real
        # See-through inference. An already-partitioned legacy ZIP bypasses it.
        master = Path(preflight["master"]) if source_only else imported["master"]
        native = make_cubism_handoff(
            master, output / "native",
            edition=edition, scope=scope,
            asset_kind=asset if edition == "pro" else None,
            reference_image=reference_image,
            external_psd=None if imported is None else Path(imported["psd"]),
            qwen=False, preserve_supplied_parts=imported is not None,
            psd2live=True)
    else:
        if reference_image is None:
            raise ValueError("DETACHED_ASSET_REQUIRES_BODY_REFERENCE_IMAGE")
        if source_only and imported is None:
            # Detached hair/outfit/accessory does not contain a full face/head.
            # Upstream See-through V3 always runs a head crop: do NOT guess a
            # full character or produce unrelated eyes/body parts.
            from tools.vts_asset_input import prepare_detached_asset
            prepared, report = prepare_detached_asset(
                Path(preflight["master"]), output / "detached_source",
                asset_kind=asset, qwen=False, layer_count=4, pass_budget=0,
                third_party=Path("/content/vtuber_builder/third_party"))
            imported = {"master": Path(preflight["master"]), "psd": Path(prepared)}
            preflight["parts"] = {
                "status": "DETACHED_ALPHA_SINGLE_LAYER_REFINEMENT_REQUIRED",
                "count": 1, "needs_asset_specific_micro_split": True,
                "visual_quality_verified": False, "foreground": report}
            preflight["detached_segmentation"] = report
        native = package_detached_asset_from_ai(
            source, imported, output / "detached",
            asset=asset, body_reference=reference_image,
            source_qa=preflight)
    if not Path(native["package"]).is_file():
        raise RuntimeError("NATIVE_HANDOFF_PACKAGE_MISSING")
    evidence = {"schema": "vtuber/ai-2d-open-source-pipeline-v1",
                "source_zip": str(source), "edition": edition,
                "scope": scope, "asset": asset,
                "source_artwork": str(native.get("art_psd") if source_only and asset == "body"
                                      else imported["psd"]),
                "source_art_only": source_only,
                "layer_decomposition": (
                    "image_ai_individual_rgba_parts"
                    if source_only and preflight.get("authored_parts_present")
                    else "see_through_v3_body_head"
                    if source_only and asset == "body"
                    else "source_alpha_only_needs_asset_refinement"
                    if source_only else "author_supplied"),
                "segmentation_profile": profile,
                "stage": ("native_rig_generated_unverified" if asset == "body"
                          else "detached_artwork_requires_micro_split_and_attachment"),
                 "multiview_reference_keyforms_bound": False,
                "native": native, "source_qa": preflight,
                "pose_qa": None,
                "moc3_application_verified": False}
    if asset == "body":
        if native.get("state") != "psd2live_rigged_unverified":
            raise RuntimeError("PSD2LIVE_REAL_MODEL_NOT_CREATED")
        # Fail before expensive independent/native rendering when eye-white
        # pixels were mislabelled as irises or a limb lost character-side info.
        try:
            evidence["semantic_rig_binding"] = check_psd2live_body_semantics(
                native.get("psd2live_layer_names") or {})
        except RuntimeError as exc:
            evidence["stage"] = "semantic_rig_binding_failed"
            evidence["semantic_rig_binding_error"] = str(exc)
            _write_json(output / "pipeline_result.json", evidence)
            raise
        try:
            pose = render_independent_pose_preview(
                Path(evidence["source_artwork"]), output / "independent_pose")
            evidence["pose_qa"] = pose
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
            evidence["pose_qa_error"] = str(exc)
            evidence["pose_qa"] = None
        # Unlike the alternate preview, these frames load the actual PSD2Live MOC3.
        native_pose_report = None
        try:
            model3 = Path(native["psd2live"]["model3_json"])
            native_pose_report = render_actual_native_moc3(
                model3, output / "native_moc3_pose")
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
            evidence["native_pose_error"] = str(exc)
        evidence["native_pose"] = native_pose_report
        verdict = write_handoff_verdict(
            output / "quality", source_report=preflight,
            rig_result=native, pose_report=evidence["pose_qa"],
            native_pose_report=native_pose_report)
        evidence["quality"] = verdict
        evidence["contact_sheet"] = str(build_review_contact_sheet(
            preflight["views"], evidence["pose_qa"],
            output / "quality" / "multiview_pose_reference_comparison.png"))
        if native_pose_report:
            evidence["native_contact_sheet"] = str(build_review_contact_sheet(
                preflight["views"], native_pose_report,
                output / "quality" / "multiview_vs_native_moc3_comparison.png"))
        if not native_pose_report or not native_pose_report.get("native_pose_geometry_passed", False):
            # Native MOC3 compile success is NOT a completed model when arms
            # are disconnected or clipping masks break during rotation.
            evidence["stage"] = "native_pose_geometry_failed"
            _write_json(output / "pipeline_result.json", evidence)
            raise RuntimeError(
                "NATIVE_RIG_POSE_GEOMETRY_FAILED: actual MOC3 screenshots "
                "show disconnected body parts, missing geometry QA, or canvas clipping; "
                + str(evidence.get("native_pose_error", "see native_moc3_pose/native_pose_report.json")))
    if asset == "body":
        # PSD2Live builds from the front PSD. Source multi-view PNGs were
        # inspected, not mapped onto the native ArtMesh deformation curves.
        # A rig that merely rotates its eye parts must never be "complete".
        evidence["stage"] = "native_poses_checked_multiview_unbound_review_required"
        evidence["native_head_gaze_isolation_passed"] = bool(
            native_pose_report and
            (native_pose_report.get("parameter_isolation") or {}).get("passed"))
        evidence["garment_shape_review_required"] = True
    _write_json(output / "pipeline_result.json", evidence)
    return evidence


def prepare_3d_turnaround_input(source: Path, output: Path, *, asset: str) -> dict:
    """Check the complete eight-view 3D image brief, not only four PNG names.

    The existing VRM worker still consumes its explicitly supported orthogonal
    reference views. This validates (but does not silently train on) diagonal
    references; no 3D hair/outfit native generator is fabricated here.
    """
    if asset not in VIEW_SETS:
        raise ValueError("INVALID_3D_ASSET")
    from PIL import Image
    source = Path(source).resolve(strict=True)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    expected = tuple(f"{asset}_{direction}" for direction in VIEWS_FOR_3D) + (
        f"{asset}_detail_occlusion",)
    found: dict[str, str] = {}
    contents: dict[str, str] = {}
    with ZipFile(source) as archive:
        for info in archive.infolist():
            result = _safe_view_name(info.filename)
            if not result or result[0] != "views":
                continue
            stem = result[1]
            if stem not in expected:
                continue
            if stem in found:
                raise ValueError("3D_DUPLICATE_ANGLE: " + stem)
            if info.file_size > 48_000_000:
                raise ValueError("3D_ANGLE_OVERSIZED: " + stem)
            data = archive.read(info)
            with Image.open(io.BytesIO(data)) as image:
                if image.format != "PNG" or min(image.size) < 128:
                    raise ValueError("3D_ANGLE_INVALID: " + stem)
                pixels = hashlib.sha256(image.convert("RGBA").tobytes()).hexdigest()
            target = output / f"{stem}.png"
            target.write_bytes(data)
            found[stem] = str(target)
            contents[stem] = pixels
    missing = sorted(set(expected) - set(found))
    repeated = [n for digest in set(contents.values())
                if len(n := [k for k, v in contents.items() if v == digest]) > 1]
    report = {"schema": "vtuber/3d-turnaround-preflight-v1",
              "required_views": list(expected), "found": found,
              "missing": missing, "duplicated_pixel_groups": repeated,
              "front_back_left_right_used_by_existing_vrm_worker": True,
              "diagonal_views_automatically_consumed_by_vrm_mesh": False,
              "state": "SOURCE_ART_VERIFIED_NOT_NATIVE_MODEL"}
    _write_json(output / "turnaround_report.json", report)
    if missing or repeated:
        raise RuntimeError("3D_TURNAROUND_REGENERATION_REQUIRED: "
                           + json.dumps({"missing": missing, "duplicates": repeated}))
    return report
