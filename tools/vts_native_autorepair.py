"""Bounded native PSD2Live regeneration driven by actual MOC3 pose evidence.

Never treat a generated file, a second renderer, or structural checks as proof
of a working Live2D model. Each candidate is a fresh PSD2Live export that must
pass the real Cubism Core pose tester before any candidate is accepted.
"""
from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZipFile

# Values are restrained to keep failed model re-rigs predictable. No uncontrolled
# prompt-specific retry strings or deformation hacks.
CANDIDATES = (
    {"head_strength": 1.0, "body_strength": 1.0, "mesh_spacing": 40},
    {"head_strength": 0.85, "body_strength": 0.90, "mesh_spacing": 32},
    {"head_strength": 1.12, "body_strength": 0.85, "mesh_spacing": 32},
    {"head_strength": 0.90, "body_strength": 1.10, "mesh_spacing": 28},
)


def _pose_score(report: dict) -> tuple[int, dict]:
    if not isinstance(report, dict):
        return 0, {"native_pose_report_missing": True}
    geometry = bool(report.get("native_pose_geometry_passed"))
    isolated = bool((report.get("parameter_isolation") or {}).get("passed"))
    mouth = bool(report.get("native_mouth_interpolation_passed"))
    active = bool(report.get("pose_activity_passed"))
    # A score is diagnostic only. All gates are mandatory for acceptance.
    return sum([geometry, isolated, mouth, active]), {
        "geometry": geometry, "parameter_isolation": isolated,
        "mouth_interpolation": mouth, "pose_activity": active,
    }


def search_native_rig(psd: Path, output: Path, *, edition: str = "free",
                      candidates: tuple[dict, ...] = CANDIDATES,
                      build=None, render=None) -> dict:
    """Regenerate at bounded parameters; publish only a native-QA-passing result.

    build/render injections exist to test the orchestration without GPU, Gradle
    or Cubism. Production defaults always invoke the real pipelines.
    """
    from tools.vts_psd2live import run_psd2live
    from tools.vts_multiview_runtime import render_actual_native_moc3

    build = build or run_psd2live
    render = render or render_actual_native_moc3
    psd = Path(psd).resolve(strict=True)
    output = Path(output).resolve()
    if edition not in ("free", "pro"):
        raise ValueError("Invalid Cubism edition")
    if not 1 <= len(candidates) <= 8:
        raise ValueError("Candidate budget must be 1..8")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Auto-repair requires a fresh output directory")
    output.mkdir(parents=True, exist_ok=True)
    history = []
    best = None
    best_score = -1
    for index, config in enumerate(candidates):
        if not isinstance(config, dict) or set(config) != {
                "head_strength", "body_strength", "mesh_spacing"}:
            raise ValueError("Unsupported native rig tuning candidate")
        trial = output / f"trial_{index:02d}"
        data = {"index": index, "config": dict(config), "accepted": False}
        result = None
        render_returned_success = False
        try:
            result = build(psd, trial / "model", edition=edition, **config)
            # The genuine production build returns structurally checked MOC3
            # paths. Injection tests must return the same structural shape.
            model3 = Path(result["model3_json"]).resolve(strict=True)
            if not model3.is_relative_to(trial):
                raise RuntimeError("Candidate model path escaped isolated trial")
            native = render(model3, trial / "poses")
            data["render_report"] = native
            render_returned_success = True
        except Exception as exc:
            data["error"] = f"{type(exc).__name__}: {exc}"
            report_path = trial / "poses" / "native_pose_report.json"
            if report_path.is_file():
                data["render_report"] = json.loads(report_path.read_text(encoding="utf-8"))
        score, gates = _pose_score(data.get("render_report"))
        data["score"] = score
        data["gates"] = gates
        data["accepted"] = bool(result and render_returned_success and score == 4)
        history.append(data)
        if data["accepted"] and score > best_score:
            best, best_score = (result, index), score
            break  # No point regenerating a fully verified native rig.
    # Raw retry counts are not explanations. Provide actionable categories
    # for source-paint, actual mesh, keyed Warp and mouth-shape repair.
    from tools.vts_native_repair_plan import quality_repair_plan
    failure_observation = (history[-1].get("render_report") or {}) if history else {}
    next_actions = quality_repair_plan(failure_observation)
    report_path = output / "autorig_search.json"
    report_path.write_text(json.dumps({
        "schema": "vtuber/native-rig-search-v1",
        "source_psd": str(psd), "edition": edition,
        "trials": history, "accepted": best is not None,
        "next_quality_repair_actions": next_actions,
        "winner": best[1] if best else None,
        "application_tracking_verified": False,
    }, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    if best is None:
        raise RuntimeError(
            "NATIVE_AUTOREPAIR_NO_PASSING_CANDIDATE: " + str(report_path))
    return {"model": best[0], "pose_report": history[best[1]]["render_report"],
            "search_report": str(report_path), "winner": best[1],
            "model_verified_by_native_pose": True,
            "vts_application_tracking_verified": False}


def repair_existing_artwork_zip(artwork_zip: Path, output: Path, *,
                                edition: str = "free", scope: str = "upper",
                                candidates: tuple[dict, ...] = CANDIDATES,
                                build=None, render=None, package=None) -> dict:
    """Run native repair on source PSD bytes; never repeat AI segmentation."""
    if scope not in ("upper", "full"):
        raise ValueError("Invalid rig scope")
    source = Path(artwork_zip).resolve(strict=True)
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    with ZipFile(source) as archive:
        valid = [name for name in ("avatar.psd", "body.psd")
                 if name in archive.namelist()]
        if len(valid) != 1 or archive.namelist().count(valid[0]) != 1:
            raise ValueError("Artwork must contain exactly one root avatar/body PSD")
        info = archive.getinfo(valid[0])
        if not 26 <= info.file_size <= 1024 ** 3:
            raise ValueError("Invalid PSD size")
        extracted = output / "source.psd"
        if extracted.exists():
            raise ValueError("Existing PSD extraction would be overwritten")
        with archive.open(info) as inp, extracted.open("xb") as dst:
            while data := inp.read(1024 * 1024):
                dst.write(data)
    native = search_native_rig(extracted, output / "native_search",
                               edition=edition, candidates=candidates,
                               build=build, render=render)
    from tools.vts_psd2live import package_psd2live
    exporter = package or package_psd2live
    archive_path = output / "Live2D_Native_AutoRepaired.zip"
    exporter(native["model"], source, archive_path)
    if not archive_path.is_file():
        raise RuntimeError("Native model packager did not create its ZIP")
    from zipfile import ZIP_DEFLATED
    with ZipFile(archive_path, "a", ZIP_DEFLATED) as archive:
        archive.write(native["search_report"], "qa/native_autorepair_search.json")
        pose_path = output / "native_search" / f"trial_{native['winner']:02d}" / "poses"
        for frame in sorted(pose_path.glob("*.png")):
            archive.write(frame, "qa/native_pose/" + frame.name)
        evidence = pose_path / "native_pose_report.json"
        if evidence.is_file():
            archive.write(evidence, "qa/native_pose/native_pose_report.json")
    return {
        "state": "psd2live_rigged_native_pose_verified",
        "package": str(archive_path), "moc3_generated": True,
        "psd2live": native["model"],
        "native_pose": native["pose_report"],
        "search_report": native["search_report"],
        "runtime_verified_in_app": False,
        "model_verified_by_native_pose": True,
        "source_artwork": str(source),
        "reused_existing_psd": True,
    }
