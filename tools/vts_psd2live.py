"""PSD2Live v3.3.1 CLI bridge for real Live2D model delivery.

Separate GPL-3.0 program: never vendor its code into this repository.
A built PSD is necessary but not evidence of a rig. The bridge only returns
success after a real CLI exit and checking every Cubism runtime dependency.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
from zipfile import ZipFile, ZIP_DEFLATED

PSD2LIVE_URL = "https://github.com/tsunehimatoi/psd2live.git"
PSD2LIVE_REF = "v3.3.1"


def _gradle_bridge(root: Path, task: str) -> list[str]:
    """Configure our launcher without modifying the external release's files."""
    sources = Path(__file__).resolve().parent / "psd2live_bridge"
    init = sources / "bridge.init.gradle"
    if not init.is_file() or not (sources / "VtsRigMain.kt").is_file():
        raise RuntimeError(f"PSD2LIVE_BUDGET_ADAPTER_MISSING: {sources}")
    return [str(root / "gradlew"), "--no-daemon", "--init-script", str(init),
            f"-PvtsBridgeSources={sources}", task]


def _source_root(third_party: Path | None) -> Path:
    override = os.environ.get("VTS_PSD2LIVE_HOME")
    if override:
        return Path(override).expanduser().resolve()
    if third_party is not None:
        return Path(third_party).expanduser().resolve() / "psd2live"
    return Path("/content/vtuber_builder/third_party/psd2live")


def _java_major(output: str) -> int:
    match = re.search(r'version\s+"(?:1\.)?(\d+)', output)
    if match:
        return int(match.group(1))
    match = re.search(r'openjdk\s+(\d+)', output.lower())
    return int(match.group(1)) if match else 0


def _java_env() -> dict:
    env = dict(os.environ)
    candidates = []
    if env.get("JAVA_HOME"):
        candidates.append(Path(env["JAVA_HOME"]) / "bin/java")
    candidates.extend(sorted(Path("/usr/lib/jvm").glob("java-21*/bin/java")))
    if shutil.which("java"):
        candidates.append(Path(shutil.which("java")))
    for candidate in candidates:
        if not candidate.is_file():
            continue
        check = subprocess.run([str(candidate), "-version"], capture_output=True,
                               text=True, timeout=15, check=False)
        if _java_major(check.stdout + check.stderr) >= 21:
            if candidate.name == "java" and candidate.parent.name == "bin":
                env["JAVA_HOME"] = str(candidate.parent.parent.resolve())
                env["PATH"] = str(candidate.parent.resolve()) + os.pathsep + env.get("PATH", "")
            return env
    raise RuntimeError(
        "PSD2LIVE_JDK21_REQUIRED: install OpenJDK 21 before running. "
        "On Colab: !apt-get update -qq && apt-get install -y openjdk-21-jdk-headless")


def ensure_psd2live(third_party: Path | None, *, timeout_seconds: int = 300) -> Path:
    """Fetch exact release only if absent; never overwrite user's checkout."""
    root = _source_root(third_party)
    if not (root / "gradlew").is_file():
        if root.exists() and any(root.iterdir()):
            raise RuntimeError(f"PSD2LIVE_SOURCE_INVALID: nonempty checkout {root}")
        git = shutil.which("git")
        if git is None:
            raise RuntimeError("PSD2LIVE_GIT_MISSING: git required for source bootstrap")
        root.parent.mkdir(parents=True, exist_ok=True)
        from tools.vts_subprocess import run_logged
        rc = run_logged([git, "clone", "--depth", "1", "--branch", PSD2LIVE_REF,
                         PSD2LIVE_URL, str(root)], cwd=root.parent,
                        log_path=root.parent / "psd2live_clone.log",
                        timeout_seconds=timeout_seconds)
        if rc:
            raise RuntimeError(f"PSD2LIVE_CLONE_FAILED: exit={rc}")
    if not (root / "gradlew").is_file():
        raise RuntimeError(f"PSD2LIVE_WRAPPER_MISSING: {root}/gradlew")
    if (root / ".git").exists():
        tag = subprocess.run(
            ["git", "-C", str(root), "describe", "--tags", "--exact-match", "HEAD"],
            capture_output=True, text=True, timeout=15, check=False)
        if tag.returncode != 0 or tag.stdout.strip() != PSD2LIVE_REF:
            raise RuntimeError(
                f"PSD2LIVE_VERSION_MISMATCH: expected {PSD2LIVE_REF}, "
                f"checkout={root}, tag={tag.stdout.strip()!r}; "
                "use the exact pinned release")
    return root


def _git_revision(root: Path) -> str | None:
    if not (root / ".git").exists():
        return None
    try:
        result = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                                capture_output=True, text=True, timeout=10, check=True)
        return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def validate_psd2live_output(folder: Path, *, edition: str | None = None) -> dict:
    """Verify model references, MOC3 magic, texture PNG and optional sidecars.

    This is an artifact contract, not a proof of good animation or successful
    loading by the proprietary Cubism Core / VTube Studio.
    """
    from vtuber_pipeline.two_d.cubism_handoff import validate_official_export
    root = Path(folder).resolve(strict=True)
    checked = validate_official_export(str(root))
    model = Path(checked["model3_json"]).resolve()
    model_dir = model.parent
    if not model_dir.is_relative_to(root):
        raise RuntimeError("PSD2LIVE_OUTPUT_OUTSIDE_ROOT")
    # Runtime manifest is the source of truth for atlas pages. Setting
    # --atlas 2048 does NOT by itself ensure Cubism FREE's one-page limit.
    from PIL import Image
    manifest = json.loads(model.read_text(encoding="utf-8"))
    refs = manifest.get("FileReferences", {})
    texture_names = refs.get("Textures", [])
    atlas_pages = []
    for name in texture_names:
        texture = (model_dir / name).resolve()
        with Image.open(texture) as image:
            atlas_pages.append({"name": name, "size": [image.width, image.height]})
    if edition == "free":
        if len(atlas_pages) != 1 or any(
                width > 2048 or height > 2048
                for width, height in (item["size"] for item in atlas_pages)):
            raise RuntimeError(
                f"PSD2LIVE_FREE_ATLAS_LIMIT: expected one page <=2048px, "
                f"actual={atlas_pages}")
    # PSD2Live may produce its editable project and CMO3 as siblings.
    all_files = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise RuntimeError(f"PSD2LIVE_OUTPUT_SYMLINK: {path}")
        if path.is_file():
            if not path.stat().st_size:
                raise RuntimeError(f"PSD2LIVE_OUTPUT_EMPTY: {path}")
            all_files.append(path)
    if not all_files:
        raise RuntimeError("PSD2LIVE_OUTPUT_EMPTY")
    cmo3_files = [str(p) for p in all_files if p.suffix.lower() == ".cmo3"]
    if not cmo3_files:
        raise RuntimeError("PSD2LIVE_CMO3_MISSING: CLI default must export editable Cubism CMO3")
    return {
        "model3_json": str(model),
        "moc3": checked["moc3"],
        "required_files": checked["files"],
        "files": [str(p) for p in all_files],
        "cmo3": cmo3_files,
        "project": [str(p) for p in all_files if p.suffix.lower() == ".psd2live"],
        "runtime_references_valid": True,
        "runtime_execution_verified": False,
        "atlas_pages": atlas_pages,
        "cubism_free_atlas_verified": edition == "free",
        "cubism_free_editor_limits_verified": False,
        "not_inspected": ["native_artmesh_count", "native_deformer_count",
                          "native_parameter_count", "native_part_count",
                          "native_blendshape_parameters", "native_artpath_count"],
    }


def run_psd2live(psd: Path, output: Path, *, edition: str,
                 third_party: Path | None = None, timeout_seconds: int = 7200,
                 runner=None, head_strength: float = 1.0,
                 body_strength: float = 1.0, mesh_spacing: int = 40) -> dict:
    """Run the pinned official pipeline with an explicit atlas generation budget."""
    if edition not in ("free", "pro"):
        raise ValueError("invalid Cubism edition")
    if not (0.6 <= head_strength <= 1.5 and 0.6 <= body_strength <= 1.5):
        raise ValueError("PSD2LIVE_RIG_STRENGTH_OUT_OF_RANGE")
    if isinstance(mesh_spacing, bool) or not isinstance(mesh_spacing, int) or not 20 <= mesh_spacing <= 80:
        raise ValueError("PSD2LIVE_MESH_SPACING_OUT_OF_RANGE")
    psd = Path(psd).expanduser().resolve(strict=True)
    if psd.suffix.lower() != ".psd" or psd.stat().st_size < 26:
        raise ValueError("PSD2Live input must be a nonempty layered PSD")
    output = Path(output).expanduser().resolve()
    if output.is_relative_to(psd.parent):
        # Separate output avoids accidentally packaging the entire artwork ZIP.
        raise ValueError("PSD2Live model output must be outside the artwork directory")
    output.mkdir(parents=True, exist_ok=True)
    # Do not pass a stale model from a previous run as new success evidence.
    if any(output.iterdir()):
        raise RuntimeError(f"PSD2LIVE_OUTPUT_NOT_EMPTY: {output}")
    root = ensure_psd2live(third_party)
    env = _java_env()
    # Do not use shell=True. Gradle --args takes a single value.
    atlas = 2048 if edition == "free" else 4096
    atlas_pages = 1 if edition == "free" else 8  # official AtlasBudget default
    # GUI PipelineConfig starts at 40 mesh units, while CLI defaults to
    # 64. Choose the GUI's higher-detail setting explicitly, with DOCUMENT
    # (2048-reference) units so huge source raster sizes do not explode
    # the mesh budget. The upstream CLI has no maxPages flag; our small
    # launcher supplies the official AtlasBudget API before generation.
    # PSD2Live v3.3.1 uses actual nunif/waifu2x neural SR for scale > 1.
    # Unlike ordinary resizing, this fails without explicitly configured Art weights.
    nunif_dir = os.environ.get("VTS_PSD2LIVE_NUNIF_DIR", "").strip()
    nunif_models = os.environ.get("VTS_PSD2LIVE_NUNIF_MODELS", "").strip()
    if bool(nunif_dir) != bool(nunif_models):
        raise RuntimeError("PSD2LIVE_NUNIF_CONFIG_INCOMPLETE: set both nunif and Art model directories")
    upscale_factor = 1
    upscale_args = ""
    if nunif_dir:
        repo_dir = Path(nunif_dir).expanduser().resolve()
        model_dir = Path(nunif_models).expanduser().resolve()
        if not (repo_dir / "waifu2x").is_dir() or not model_dir.is_dir():
            raise RuntimeError("PSD2LIVE_NUNIF_CONFIG_INVALID: source or model directory missing")
        if not any(model_dir.glob("*.pth")):
            raise RuntimeError("PSD2LIVE_NUNIF_WEIGHTS_MISSING: no Art .pth files found")
        upscale_factor = int(os.environ.get("VTS_PSD2LIVE_UPSCALE",
                                           "2" if edition == "free" else "4"))
        if upscale_factor not in (1, 2, 4):
            raise ValueError("PSD2LIVE_UPSCALE_INVALID: choose 1, 2 or 4")
        if upscale_factor > 1:
            python_executable = Path(os.environ.get("VTS_PSD2LIVE_PYTHON", sys.executable))
            if not python_executable.is_file():
                raise RuntimeError("PSD2LIVE_UPSCALE_PYTHON_MISSING: configure a Python executable")
            upscale_args = (f" --upscale-python {shlex.quote(str(python_executable))}"
                            f" --nunif-dir {shlex.quote(str(repo_dir))}"
                            f" --upscale-model {shlex.quote(str(model_dir))}")
    args = (f"--input {shlex.quote(str(psd))} "
            f"--output {shlex.quote(str(output))} "
            f"--atlas {atlas} --atlas-pages {atlas_pages} --lang en "
            f"--mesh-spacing {mesh_spacing} --mesh-wrap 0 "
            f"--head-strength {head_strength:.4f} --body-strength {body_strength:.4f} --mouth-outline false "
            f"--upscale {upscale_factor}"
            f"{upscale_args}")
    cmd = _gradle_bridge(root, "vtsRig") + [f"--args={args}"]
    from tools.vts_subprocess import run_logged
    run = runner or run_logged
    log = output.parent / "psd2live_cli.log"
    print(f"[VTS PSD2LIVE START] input={psd} atlas={atlas} pages={atlas_pages} "
          f"source={root} ref={PSD2LIVE_REF}", flush=True)
    rc = run(cmd, cwd=root, env=env, log_path=log,
             timeout_seconds=timeout_seconds)
    if rc:
        raise RuntimeError(f"PSD2LIVE_CLI_FAILED exit={rc}; log={log}")
    checked = validate_psd2live_output(output, edition=edition)
    fit_report = output / "vts_atlas.json"
    if not fit_report.is_file():
        raise RuntimeError("PSD2LIVE_ATLAS_REPORT_MISSING: official budget launcher did not complete")
    fit = json.loads(fit_report.read_text(encoding="utf-8"))
    if (fit.get("schema") != "vtuber/psd2live-atlas-v1" or
            fit.get("page_size") != atlas or fit.get("max_pages") != atlas_pages or
            fit.get("padding") != 2 or
            not isinstance(fit.get("fit"), (int, float)) or
            not math.isfinite(fit["fit"]) or not 0 < fit["fit"] <= 1 or
            [item.get("size") for item in fit.get("pages", [])] !=
            [item["size"] for item in checked["atlas_pages"]]):
        raise RuntimeError(f"PSD2LIVE_ATLAS_REPORT_INVALID: {fit_report}")
    measured_fit = float(fit["fit"])
    fit_quality = ("severely_downscaled" if measured_fit < .5 else
                   "downscaled" if measured_fit < .9 else "high_density")
    print(f"[VTS ATLAS QUALITY] edition={edition} fit={measured_fit:.4f} "
          f"quality={fit_quality} native_upscale={upscale_factor} "
          f"neural_super_resolution={bool(upscale_args)}", flush=True)
    checked.update({
        "atlas_quality": fit_quality,
        "effective_texture_detail_verified": False,
        "nunif_model_configured": bool(upscale_args),
        "backend": "psd2live", "version_ref": PSD2LIVE_REF,
        "source": PSD2LIVE_URL, "commit": _git_revision(root),
        "license": "GPL-3.0", "cli_command": cmd,
        "log": str(log), "atlas_size": atlas,
        "atlas_budget": {"page_size": atlas, "max_pages": atlas_pages, "padding": 2},
        "atlas_fit": fit,
        "invocation": "official PipelineConfig/AtlasBudget API via external Gradle launcher",
        "rig_options": {
            "mesh_spacing": mesh_spacing,
            "mesh_spacing_basis": "GUI PipelineConfig=40; CLI default=64",
            "mesh_units": "document_2048_reference",
            "mesh_wrap": 0,
            "head_strength": head_strength, "body_strength": body_strength,
            "upscale_factor": upscale_factor,
            "upscale_backend": "PSD2Live nunif/waifu2x neural SR" if upscale_args else "disabled (upstream default)",
            "mouth_outline_generated": False,
            "mouth_outline_reason": "Supplied artwork already contains painted mouth contour; adding synthetic ribbons duplicates the lip.",
            "generate_deformers": True, "generate_motions": True,
            "generate_physics": True, "export_cmo3": True,
            "export_moc3": True,
            "preset": "CLI direct PSD generation; GUI Minimal/Default/Full not exposed",
        },
        "status": "rigged_artifacts_validated",
    })
    print(f"[VTS PSD2LIVE PASS] model={checked['model3_json']} "
          f"files={len(checked['files'])}", flush=True)
    return checked


def package_psd2live(result: dict, artwork_zip: Path, output_zip: Path) -> Path:
    """Deliver loadable model files at ZIP root, with original PSD package."""
    model = Path(result["model3_json"]).resolve()
    all_files = [Path(p).resolve() for p in result["files"]]
    root = Path(os.path.commonpath([str(p.parent) for p in all_files])).resolve()
    if not model.is_relative_to(root):
        raise RuntimeError("PSD2LIVE_MODEL_PATH_INVALID")
    artwork_zip = Path(artwork_zip).resolve(strict=True)
    output_zip = Path(output_zip).resolve()
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    if output_zip.exists():
        raise RuntimeError(f"PSD2LIVE_ARCHIVE_ALREADY_EXISTS: {output_zip}")
    tmp = output_zip.with_name(output_zip.name + ".partial")
    tmp.unlink(missing_ok=True)
    try:
        with ZipFile(tmp, "w", ZIP_DEFLATED, compresslevel=6) as z:
            for p in all_files:
                if p.is_symlink() or not p.is_relative_to(root) or not p.is_file():
                    raise RuntimeError(f"PSD2LIVE_OUTPUT_PATH_INVALID: {p}")
                name = str(p.relative_to(root)).replace("\\", "/")
                if name.startswith("source_artwork/") or name.startswith("metadata/"):
                    raise RuntimeError("PSD2LIVE_OUTPUT_RESERVED_PREFIX")
                z.write(p, name)
            z.write(artwork_zip, "source_artwork/" + artwork_zip.name)
            from tools.vts_native_visual_quality import review_psd2live_export
            visual_review = review_psd2live_export(model.parent, artwork_zip)
            z.writestr("metadata/visual_quality_review.json",
                       json.dumps(visual_review, ensure_ascii=False, indent=2))
            if visual_review["warnings"]:
                print("[VTS VISUAL QUALITY NEEDS REVIEW] "
                      + " | ".join(visual_review["warnings"]), flush=True)
            z.writestr("README_VTUBE_STUDIO.md", (
                "# VTube Studio용 모델 파일과 확인 절차\\n\\n"
                "이 ZIP을 압축 해제합니다. 최종 *.model3.json, *.moc3, 참조된 텍스처/"
                "physics/expressions/motions 파일의 상대 경로를 유지하세요.\\n\\n"
                "VTube Studio에서 사용자 모델 폴더를 열고 내보낸 모델 폴더를 넣거나 "
                "해당 모델을 불러옵니다. 모델 폴더만 이동하고 source_artwork/의 PSD "
                "참고 ZIP은 작동에 필수는 아닙니다.\\n\\n"
                "PSD2Live CLI가 실제 파일을 생성했는지와 링크를 검사했습니다. "
                "단, Cubism Core/VTube Studio 실행, 추적, 눈·입·팔 움직임, 머리/옷 "
                "흔들림 및 물리 품질은 자동으로 검증하지 못했습니다. "
                "신체만 그린 입력은 헤어·의상이 없는 신체 모델입니다. "
                "모델 전체가 자동 완성되었다고 간주하지 마세요.\\n"
            ).replace("\\\\n", "\\n"))
            public = {key: value for key, value in result.items()
                      if key != "cli_command"}
            z.writestr("metadata/psd2live_bridge.json",
                       json.dumps(public, ensure_ascii=False, indent=2))

        tmp.replace(output_zip)
    finally:
        tmp.unlink(missing_ok=True)
    return output_zip

def rig_existing_artwork_zip(artwork_zip: Path, output: Path, *,
                             edition: str, scope: str = "upper",
                             auto_repair: bool = False,
                             backend: str = "pinned") -> dict:
    """Resume an already-made PSD ZIP directly into real PSD2Live CLI export.

    The user's finished artwork ZIP already includes a true layered PSD.
    Running segmentation, importing the authored PNGs and re-exporting the
    PSD again would add cost and can alter semantics; use the actual bytes.
    """
    if edition not in ("free", "pro"):
        raise ValueError("Invalid Cubism edition")
    if backend not in ("pinned", "modern"):
        raise ValueError("Invalid PSD2Live backend")
    if backend == "modern" and auto_repair:
        raise ValueError("PSD2LIVE_MODERN_REPAIR_USES_MCP: legacy strength-only retry not supported")
    artwork_zip = Path(artwork_zip).expanduser().resolve(strict=True)
    if artwork_zip.suffix.lower() != ".zip":
        raise ValueError("Existing artwork input must be a ZIP")
    output = Path(output).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    with ZipFile(artwork_zip) as archive:
        entries = [item for item in archive.infolist() if not item.is_dir()]
        root_psds = [item for item in entries
                     if item.filename in {"avatar.psd", "body.psd"}]
        if len(root_psds) != 1 or any(
            item.filename == root_psds[0].filename for item in entries
            if item is not root_psds[0]
        ):
            raise ValueError("ARTWORK_ZIP_EXPECTS_SINGLE_ROOT_AVATAR_OR_BODY_PSD")
        psd_member = root_psds[0]
        if (psd_member.file_size < 26 or
                psd_member.file_size > 1024 * 1024 * 1024 or
                (psd_member.external_attr >> 16) & 0o170000 == 0o120000):
            raise ValueError("ARTWORK_ZIP_PSD_INVALID_SIZE_OR_SYMLINK")
        source = output / "artwork" / "registered.psd"
        source.parent.mkdir(parents=True, exist_ok=True)
        if source.exists():
            raise ValueError("ARTWORK_ZIP_OUTPUT_NOT_EMPTY")
        # Stream only the chosen PSD: do not extract arbitrary archive files.
        with archive.open(psd_member) as incoming, source.open("xb") as dst:
            remaining = psd_member.file_size
            while remaining:
                chunk = incoming.read(min(1024 * 1024, remaining))
                if not chunk:
                    raise ValueError("ARTWORK_ZIP_PSD_TRUNCATED")
                dst.write(chunk)
                remaining -= len(chunk)
            if incoming.read(1):
                raise ValueError("ARTWORK_ZIP_PSD_OVERRUN")
        # Previous Colab releases collapsed eye_L/eye_R into generic eye.002
        # in avatar.psd. Preserve the independently authored source semantics
        # when the original PSD is also packaged and its composite matches.
        semantic_source = output / "artwork" / "semantic_original.psd"
        source_name = "source_psd/see_through_layers.psd"
        if source_name in archive.namelist():
            member = archive.getinfo(source_name)
            if (26 <= member.file_size <= 1024 * 1024 * 1024 and
                    (member.external_attr >> 16) & 0o170000 != 0o120000):
                with archive.open(member) as incoming, semantic_source.open("xb") as dst:
                    while True:
                        block = incoming.read(1024 * 1024)
                        if not block:
                            break
                        dst.write(block)
    from psd_tools import PSDImage
    psd = PSDImage.open(source)
    leaves = [node for node in psd.descendants() if not node.is_group()
              and node.is_visible()]
    if (psd.depth != 8 or psd.color_mode.name != "RGB" or
            psd.width < 256 or psd.height < 256 or len(leaves) < 2):
        raise ValueError("ARTWORK_ZIP_REQUIRES_REAL_LAYERED_RGB8_PSD")
    restored_semantics = False
    if semantic_source.is_file():
        from PIL import ImageChops
        authored = PSDImage.open(semantic_source)
        authored_leaves = [node for node in authored.descendants()
                           if not node.is_group() and node.is_visible()]
        authored_names = [str(node.name).lower() for node in authored_leaves]
        original_image = authored.composite(apply_icc=False)
        packaged_image = psd.composite(apply_icc=False)
        same_visible_art = (
            authored.size == psd.size and len(authored_leaves) == len(leaves)
            and original_image is not None and packaged_image is not None
            and ImageChops.difference(
                original_image.convert("RGBA"),
                packaged_image.convert("RGBA")).getbbox() is None
        )
        has_bilateral_identity = any(
            "_l" in name or "_r" in name or ".left" in name or ".right" in name
            for name in authored_names
        )
        if same_visible_art and has_bilateral_identity:
            from tools.vts_production import psd_to_registered_rgba
            from tools.vts_artwork_export import build_artwork_package
            _, registered_zip, _ = psd_to_registered_rgba(
                semantic_source, output / "semantic_registration",
                artmesh_max=100 if edition == "free" else None)
            recovered = build_artwork_package(
                registered_zip, output / "semantic_recovered",
                edition=edition, scope=scope,
                asset_kind=None if edition == "free" else "body",
                qwen=False, official_second_pass=False,
                psd2live_names=True, preserve_source_parts=True)
            source = Path(recovered["art_psd"])
            restored_semantics = True
            print("[PSD2Live] Original source artwork pixels retained; "
                  "bilateral eye/arm/ear semantics restored without inference", flush=True)
        else:
            print("[PSD2Live] Semantic source not pixel-equivalent or not bilateral; "
                  "using original final PSD without guessing layer identity", flush=True)
    native_search = None
    if auto_repair:
        from tools.vts_native_autorepair import search_native_rig
        # This sees the SAME semantic PSD selected by the existing recovery
        # path, rather than silently discarding the original bilateral parts.
        native_search = search_native_rig(
            source, output / "native_search", edition=edition)
        rig = native_search["model"]
    elif backend == "modern":
        from tools.vts_psd2live_modern import run_modern_psd2live
        rig = run_modern_psd2live(
            source, output / "native_model", edition=edition, clone=True)
    else:
        rig = run_psd2live(source, output / "native_model", edition=edition)
    native_zip = output / "Live2D_PSD2Live_From_Existing_Artwork.zip"
    package_psd2live(rig, artwork_zip, native_zip)
    if native_search is not None:
        with ZipFile(native_zip, "a", ZIP_DEFLATED) as archive:
            archive.write(native_search["search_report"],
                          "qa/native_autorepair_search.json")
            pose_dir = output / "native_search" / (
                f"trial_{native_search['winner']:02d}") / "poses"
            for pose in sorted(pose_dir.glob("*.png")):
                archive.write(pose, "qa/native_pose/" + pose.name)
            receipt = pose_dir / "native_pose_report.json"
            if receipt.is_file():
                archive.write(receipt, "qa/native_pose/native_pose_report.json")
    return {
        "state": ("psd2live_rigged_native_pose_verified" if auto_repair
                  else "psd2live_rigged_unverified"),
        "package": str(native_zip),
        "moc3_generated": True, "psd2live": rig, "layer_count": len(leaves),
        "source_artwork": str(artwork_zip), "reused_existing_psd": True,
        "runtime_verified_in_app": False,
        "bilateral_semantics_restored": restored_semantics,
        "selected_rig_backend": backend,
        "native_pose": native_search["pose_report"] if native_search else None,
        "model_verified_by_native_pose": native_search is not None,
        "search_report": native_search["search_report"] if native_search else None,
    }


def prepare_psd2live(third_party: Path | None = None, *,
                     build_timeout_seconds: int = 3600) -> Path:
    """Colab preflight: provision JDK21, pin PSD2Live release, compile once."""
    from tools.vts_subprocess import run_logged
    try:
        env = _java_env()
    except RuntimeError:
        if os.name != "posix" or getattr(os, "geteuid", lambda: 1)() != 0:
            raise
        apt = shutil.which("apt-get")
        if apt is None:
            raise
        print("[VTS PSD2LIVE SETUP] installing OpenJDK 21", flush=True)
        for cmd, seconds in (
            ([apt, "update", "-qq"], 600),
            ([apt, "install", "-y", "openjdk-21-jdk-headless"], 900),
        ):
            rc = run_logged(cmd, cwd=Path("/tmp"),
                            timeout_seconds=seconds,
                            log_path=Path("/tmp/psd2live_jdk_setup.log"))
            if rc:
                raise RuntimeError(f"PSD2LIVE_JDK21_INSTALL_FAILED exit={rc}")
        env = _java_env()
    root = ensure_psd2live(third_party)
    log = root.parent / "psd2live_build.log"
    print(f"[VTS PSD2LIVE SETUP] building {PSD2LIVE_REF} from {root}", flush=True)
    rc = run_logged(_gradle_bridge(root, "classes"),
                    cwd=root, env=env, log_path=log,
                    timeout_seconds=build_timeout_seconds)
    if rc:
        raise RuntimeError(f"PSD2LIVE_GRADLE_BUILD_FAILED exit={rc}; log={log}")
    print(f"[VTS PSD2LIVE SETUP PASS] ref={PSD2LIVE_REF} "
          f"commit={_git_revision(root)}", flush=True)
    return root


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PSD2Live CLI dependency preflight")
    parser.add_argument("--prepare", action="store_true", required=True)
    parser.add_argument("--third-party", type=Path, default=None)
    args = parser.parse_args()
    prepare_psd2live(args.third_party)
