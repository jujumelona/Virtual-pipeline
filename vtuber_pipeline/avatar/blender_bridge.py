"""Real headless Blender/VRM Add-on round-trip for a validated rigged VRM."""
from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import subprocess


def export_blender_from_vrm(source_vrm: str, output_dir: str,
                            *, timeout_sec: int = 1200) -> dict:
    """Import real VRM into Blender, audit deformation and export native VRM 1.0.

    No synthetic .blend, renamed GLB, or fallback to a non-Blender exporter.
    """
    source = Path(source_vrm).resolve()
    if not source.is_file() or source.suffix.lower() != ".vrm":
        raise ValueError("Blender source must be an existing VRM")
    blender = os.getenv("VTUBER_BLENDER_BINARY") or shutil.which("blender")
    if not blender or not Path(blender).is_file():
        raise RuntimeError("Blender 4.2+ executable is required (VTUBER_BLENDER_BINARY)")
    folder = Path(output_dir).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    blend = folder / "avatar_rigged.blend"
    target = folder / "avatar.vrm"
    report = folder / "blender_export_report.json"
    for artifact in (blend, target, report):
        artifact.unlink(missing_ok=True)
    script = Path(__file__).resolve().parents[2] / "tools/blender_jobs/avatar_rig_export.py"
    if not script.is_file():
        raise FileNotFoundError(script)
    command = [str(blender), "--background", "--factory-startup", "--python",
               str(script), "--", str(source), str(blend), str(target), str(report)]
    log_path = folder / "blender_export.log"
    try:
        with log_path.open("w", encoding="utf-8") as log:
            process = subprocess.run(
                command, stdout=log, stderr=subprocess.STDOUT,
                timeout=timeout_sec, check=False,
            )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Blender VRM export timed out; log={log_path}") from exc
    if process.returncode != 0:
        raise RuntimeError(f"Blender VRM export failed ({process.returncode}); log={log_path}")
    if not report.is_file():
        raise RuntimeError("Blender process emitted no export validation report")
    evidence = json.loads(report.read_text(encoding="utf-8"))
    if not (evidence.get("native_addon_export") and evidence.get("rigged_skin")
            and evidence.get("nonempty_shape_keys")):
        raise RuntimeError("Blender audit rejected missing skin or animated shape keys")
    if (not blend.is_file() or blend.stat().st_size < 128 or
            blend.open("rb").read(7) != b"BLENDER"):
        raise RuntimeError("No valid editable Blender project was produced")
    if (not target.is_file() or target.stat().st_size < 128 or
            target.open("rb").read(4) != b"glTF"):
        raise RuntimeError("VRM Add-on did not export a valid GLB/VRM file")
    return {"status": "complete", "blend": str(blend), "vrm_path": str(target),
            "vrm": str(target), "report_json": str(report), "output_path": str(target)}


def export_blender_vrm(refined_glb: str, skeleton_json: str,
                       texture_manifest: str, expressions_json: str,
                       gaze_json: str, spring_json: str,
                       output_dir: str) -> dict:
    """Full-data contract: promote a rigged GLB to Blender-backed VRM.

    The rigged GLB already contains genuine JOINTS_0/WEIGHTS_0 attributes.
    The four JSON contracts must be real, nonempty files; never substitute
    placeholder shapes or fabricated gaze/spring metadata.
    """
    from vtuber_pipeline.avatar.vrm_export import export_vrm
    for name in (refined_glb, skeleton_json, texture_manifest,
                 expressions_json, gaze_json, spring_json):
        if not Path(name).is_file():
            raise FileNotFoundError(name)
    expressions = json.loads(Path(expressions_json).read_text(encoding="utf-8"))
    gaze = json.loads(Path(gaze_json).read_text(encoding="utf-8"))
    springs = json.loads(Path(spring_json).read_text(encoding="utf-8"))
    skeleton = json.loads(Path(skeleton_json).read_text(encoding="utf-8"))
    texture = json.loads(Path(texture_manifest).read_text(encoding="utf-8"))
    if not skeleton or not texture or not expressions or not gaze or not springs:
        raise ValueError("Rig/texture/expression/gaze/physics contract is empty")
    prepared_dir = Path(output_dir) / "pre_blender"
    pre = export_vrm(
        refined_glb, str(prepared_dir), expressions=expressions,
        springbone_config=springs, gaze_config=gaze,
    )
    if pre.get("status") != "complete":
        raise RuntimeError(f"Pre-Blender VRM contract failed: {pre.get('error')}")
    return export_blender_from_vrm(pre["vrm_path"], output_dir)
