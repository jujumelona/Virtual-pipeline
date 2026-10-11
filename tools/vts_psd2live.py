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
                 runner=None) -> dict:
    """Run the pinned official pipeline with an explicit atlas generation budget."""
    if edition not in ("free", "pro"):
        raise ValueError("invalid Cubism edition")
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
    mesh_spacing = 40
    # Native PSD2Live texture enlargement, not neural super-resolution.
    # FREE has only one 2048px atlas; excessive intermediate enlargement may
    # be thrown away at final packing. PRO can exploit larger multi-page atlas.
    upscale_factor = 2 if edition == "free" else 4
    args = (f"--input {shlex.quote(str(psd))} "
            f"--output {shlex.quote(str(output))} "
            f"--atlas {atlas} --atlas-pages {atlas_pages} --lang en "
            f"--mesh-spacing {mesh_spacing} --mesh-wrap 0 "
            f"--head-strength 1.0 --body-strength 1.0 --upscale {upscale_factor}")
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
          "neural_super_resolution=false", flush=True)
    checked.update({
        "atlas_quality": fit_quality,
        "effective_texture_detail_verified": False,
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
            "head_strength": 1.0, "body_strength": 1.0,
            "upscale_factor": upscale_factor,
            "upscale_backend": "PSD2Live TextureUpscaleConfig (non-neural)",
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
            public = {key: value for key, value in result.items()
                      if key != "cli_command"}
            z.writestr("metadata/psd2live_bridge.json",
                       json.dumps(public, ensure_ascii=False, indent=2))

        tmp.replace(output_zip)
    finally:
        tmp.unlink(missing_ok=True)
    return output_zip

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
