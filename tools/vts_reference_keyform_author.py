"""Reference-grounded Live2D keyform corrections via PSD2Live's public MCP.

This module does NOT fake a 90-degree profile by stretching a frontal mesh.
It authors *actual* ParamAngleX keyform changes on inspected Warp IDs, using
landmarks measured in actual rendered poses and matching source reference art.
A running local PSD2Live project and its MCP proxy are required for execution.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import subprocess
import sys
from PIL import Image

SUPPORTED = {
    "head_three_quarter_L": -30,
    "head_three_quarter_R": 30,
    "head_pitch_up": None,
    "head_pitch_down": None,
}
REQUIRED_SHAPE = {"face_contour", "nose_tip", "jaw", "eye_left"}


def _point(value, canvas, label):
    if (not isinstance(value, list) or len(value) != 2 or
            any(isinstance(x, bool) or not isinstance(x, (float, int)) or
                not math.isfinite(x) for x in value)):
        raise ValueError(f"Invalid {label} landmark")
    if not (0 <= value[0] < canvas[0] and 0 <= value[1] < canvas[1]):
        raise ValueError(f"{label} outside canvas")
    return value


def compile_native_reference_edits(manifest: dict, root: Path) -> dict:
    """Build parameter-keyed mesh edits, never arbitrary 2D overlay layers.

    The coordinates in 'observed' must come from an actual MOC3/PSD2Live
    rendered pose, and 'desired' from the corresponding reference PNG.
    """
    root = Path(root).resolve()
    canvas = manifest.get("canvas")
    if (not isinstance(canvas, list) or len(canvas) != 2 or
            any(isinstance(v, bool) or not isinstance(v, int) or
                not 256 <= v <= 8192 for v in canvas)):
        raise ValueError("Reference canvas must contain valid pixel dimensions")
    bindings = manifest.get("warp_bindings")
    if not isinstance(bindings, dict):
        raise ValueError("Must provide real workspace Warp IDs")
    if not REQUIRED_SHAPE <= set(bindings):
        raise ValueError("Required facial features must be mapped to real Warp IDs")
    if len(set(bindings.values())) != len(bindings):
        raise ValueError("Each reference feature requires its own independent warp")
    for name, target in bindings.items():
        if not isinstance(name, str) or not isinstance(target, str) or not (
                target.startswith("warp:") and len(target) > 5):
            raise ValueError("Invalid warp target for " + str(name))
    poses = manifest.get("poses")
    if not isinstance(poses, list) or not 1 <= len(poses) <= 4:
        raise ValueError("Expected 1 to 4 measured reference poses")
    edits = []
    summaries = []
    used = set()
    for item in poses:
        if not isinstance(item, dict):
            raise ValueError("Invalid reference pose")
        view = item.get("view")
        angle = item.get("angle_x")
        if view not in ("head_three_quarter_L", "head_three_quarter_R"):
            raise ValueError(
                "90-degree and pitch profile require separate native art/keyforms; "
                "the frontal-warp reference adapter only supports +/-30 yaw")
        if angle != SUPPORTED[view] or (view in used):
            raise ValueError("Incorrect or duplicate signed yaw reference")
        used.add(view)
        ref = root / "reference_views" / (view + ".png")
        native_frame = root / "native_poses" / (view + ".png")
        if not ref.is_file() or not native_frame.is_file():
            raise FileNotFoundError("Real reference AND native pose PNG required: " + view)
        for image_path in (ref, native_frame):
            with Image.open(image_path) as image:
                image.verify()
            with Image.open(image_path) as image:
                if image.size != tuple(canvas):
                    raise ValueError("Reference / native pose must share original canvas: "
                                     + image_path.name)
        observed, desired = item.get("observed"), item.get("desired")
        if not isinstance(observed, dict) or not isinstance(desired, dict):
            raise ValueError("Both native and desired reference landmarks are required")
        if set(observed) != set(desired) or not REQUIRED_SHAPE <= set(observed):
            raise ValueError("Missing/bad correspondences for head silhouette, nose, eyes")
        if not set(observed) <= set(bindings):
            raise ValueError("Landmark has no explicit warp binding")
        changes = []
        for part in sorted(observed):
            current = _point(observed[part], canvas, view + ":" + part + ":native")
            goal = _point(desired[part], canvas, view + ":" + part + ":reference")
            dx = (goal[0] - current[0]) / canvas[0]
            dy = (goal[1] - current[1]) / canvas[1]
            if math.hypot(dx, dy) > 0.12:
                raise ValueError("Reference warp exceeds safe 12% canvas displacement")
            if abs(dx) < 0.0001 and abs(dy) < 0.0001:
                continue
            changes.append({
                "target": bindings[part],
                "key": {"ParamAngleX": angle},
                "operations": [{"type": "translate",
                                "delta": [round(dx, 6), round(dy, 6)]}],
            })
        if not changes:
            raise ValueError("All provided reference landmarks are unchanged")
        edits.extend(changes)
        summaries.append({"view": view, "angle_x": angle,
                          "affected_warps": [x["target"] for x in changes],
                          "native_frame": str(native_frame),
                          "reference_image": str(ref)})
    return {
        "schema": "vtuber/native-keyform-reference-edits-v1",
        "parameter": "ParamAngleX", "canvas": canvas,
        "changes": edits, "views": summaries,
        "method": "PSD2Live MCP rig_deform on existing keyform objects",
        "reference_angles_used_as_rig_keyforms": False,
        "native_execution_required": True,
        "missing_full_profile": True,
    }


def _run_mcp(proxy_root: Path, operation: str, request: dict,
             work: Path, executor=None) -> dict:
    """Invoke upstream MCP proxy against a *running local* PSD2Live editor."""
    work.mkdir(parents=True, exist_ok=True)
    request_path = work / (operation + "_request.json")
    request_path.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
    proxy = proxy_root / "mcp_proxy.py"
    if not proxy.is_file():
        raise FileNotFoundError("PSD2Live official MCP proxy missing: " + str(proxy))
    cmd = [sys.executable, str(proxy), "call", operation,
           "@" + str(request_path), "--edit", "--out", str(work)]
    runner = executor or subprocess.run
    proc = runner(cmd, cwd=str(proxy_root),
                  capture_output=True, text=True, timeout=240, check=False)
    receipt = {"operation": operation, "exit_code": proc.returncode,
               "stdout": (proc.stdout or "")[-12000:],
               "stderr": (proc.stderr or "")[-4000:]}
    (work / (operation + "_receipt.json")).write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    if proc.returncode:
        raise RuntimeError("PSD2Live MCP rejected "+operation+": "+
                           str(work / (operation+"_receipt.json")))
    return receipt


def apply_reference_keyforms(plan: dict, *, proxy_root: Path, work: Path,
                             export_to: Path, executor=None) -> dict:
    """Write keyforms, persist the PSD2Live project, and export native model.

    No success unless the model actually exports and native pose QA passes.
    """
    if plan.get("schema") != "vtuber/native-keyform-reference-edits-v1":
        raise ValueError("Unknown native-reference edit plan")
    changes = plan.get("changes")
    if not isinstance(changes, list) or not changes:
        raise ValueError("Cannot apply an empty reference plan")
    if len(changes) > 128:
        raise ValueError("Too many keyform edits for one atomic request")
    proxy_root, work, export_to = (Path(p).resolve() for p in
                                  (proxy_root, work, export_to))
    if export_to.exists() and any(export_to.iterdir()):
        raise ValueError("Native export directory must be empty")
    log = []
    # --edit obtains the current project state; changes target actual Warp IDs.
    # Preview the exact same edits first, before modifying workspace history.
    log.append(_run_mcp(proxy_root, "workspace_preview_edits",
                        {"request": {"edits": [
                            {"operation": "rig_deform",
                             "request": {"changes": changes}}
                        ]}}, work, executor))
    log.append(_run_mcp(proxy_root, "rig_deform",
                        {"request": {"changes": changes}}, work, executor))
    log.append(_run_mcp(proxy_root, "project_save",
                        {"request": {}}, work, executor))
    log.append(_run_mcp(proxy_root, "project_export_model",
                        {"request": {"output_directory": str(export_to)}},
                        work, executor))
    models = list(export_to.rglob("*.model3.json"))
    if len(models) != 1:
        raise RuntimeError("MCP export did not yield exactly one Cubism model3.json")
    from tools.vts_multiview_runtime import render_actual_native_moc3
    native = render_actual_native_moc3(models[0], work / "native_validation")
    if not native.get("pose_activity_passed"):
        raise RuntimeError("Reference-authored MOC3 native poses did not pass")
    report = {
        **plan, "reference_angles_used_as_rig_keyforms": True,
        "native_execution_required": False,
        "full_90_degree_profile_verified": False,
        "reference_landmark_fidelity_verified": False,
        "mcp_receipts": log, "native_pose_qa": native,
        "exported_model3": str(models[0]),
    }
    (work / "native_reference_binding.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--proxy-root", type=Path)
    parser.add_argument("--export-to", type=Path)
    args = parser.parse_args()
    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    plan = compile_native_reference_edits(data, args.root)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "native_reference_plan.json").write_text(
        json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    if args.apply:
        if args.proxy_root is None or args.export_to is None:
            parser.error("--apply requires --proxy-root and --export-to")
        apply_reference_keyforms(plan, proxy_root=args.proxy_root,
                                 work=args.output / "mcp",
                                 export_to=args.export_to)
    else:
        print("Reference keyform plan written; no native model modified.")
    print(args.output / "native_reference_plan.json")


if __name__ == "__main__":
    main()
