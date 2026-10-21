"""PSD2Live v3.6 texture-guided remesh, preserving existing keys/weights/Glue.

Unlike global strength retries, this invokes the editor's real
layer_mesh_structure operation on an already-authored, inspected mesh.
The PSD2Live v3.6 application owns the mesh-migration algorithm.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from tools.vts_reference_keyform_author import _require_mcp_cli, _run_mcp


def _settings(sensitivity: float, min_length: float, max_vertices: int) -> dict:
    if (isinstance(sensitivity, bool) or not isinstance(sensitivity, (int, float))
            or not math.isfinite(sensitivity) or not 0 <= sensitivity <= 1):
        raise ValueError("TEXTURE_MESH_SENSITIVITY_INVALID")
    if (isinstance(min_length, bool) or not isinstance(min_length, (int, float))
            or not math.isfinite(min_length) or not 1 <= min_length <= 128):
        raise ValueError("TEXTURE_MESH_MIN_LENGTH_INVALID")
    if (isinstance(max_vertices, bool) or not isinstance(max_vertices, int)
            or not 16 <= max_vertices <= 16000):
        raise ValueError("TEXTURE_MESH_VERTEX_BUDGET_INVALID")
    return {"sensitivity": float(sensitivity),
            "min_length": float(min_length),
            "fill": False, "bands": True,
            "max_vertices": max_vertices}


def refine_texture_meshes(*, proxy_root: Path, mesh_targets: list[str],
                          output: Path, sensitivity: float = 0.65,
                          min_length: float = 8.0,
                          max_vertices: int = 6000,
                          executor=None, render=None) -> dict:
    """Remesh loaded modern-editor project; reject empty lines, no-op and bad poses."""
    root = Path(proxy_root).resolve()
    _require_mcp_cli(root)
    if (not isinstance(mesh_targets, list) or not 1 <= len(mesh_targets) <= 8
            or len(mesh_targets) != len(set(mesh_targets)) or
            any(not isinstance(x, str) or not x.startswith("mesh:")
                    or len(x) <= 5 for x in mesh_targets)):
        raise ValueError("Provide 1..8 distinct REAL PSD2Live mesh:<id> handles")
    config = _settings(sensitivity, min_length, max_vertices)
    output = Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("Texture remesh output directory must be fresh")
    output.mkdir(parents=True, exist_ok=True)
    log = []
    copy = output / "texture_refined.psd2live"
    log.append(_run_mcp(root, "project_save_as", {"path": str(copy)},
                        output / "mcp", executor))
    if not copy.is_file():
        raise RuntimeError("PSD2Live failed to save independent editable copy")
    diagnostics = []
    for index, target in enumerate(mesh_targets):
        trial = output / "mcp" / ("mesh_" + str(index))
        request = {"target": target, "settings": config}
        preview = _run_mcp(root, "layer_mesh_structure_preview",
                           request, trial, executor)
        raw = preview["response"]
        # Official preview enumerates actual texture lines from the real
        # source raster; no lines => geometric refinement cannot be claimed.
        lines = raw.get("lines")
        if not isinstance(lines, list) or not lines:
            raise RuntimeError("TEXTURE_MESH_NO_SOURCE_GUIDES: " + target)
        log.append(preview)
        edited = _run_mcp(root, "layer_mesh_structure",
                          request, trial, executor)
        if not edited["response"].get("state"):
            raise RuntimeError("TEXTURE_MESH_NOT_COMMITTED: " + target)
        log.append(edited)
        diagnostics.append({"target": target, "texture_guides": len(lines),
                            "committed_state": edited["response"]["state"]})
    log.append(_run_mcp(root, "project_save", {}, output / "mcp", executor))
    models_dir = output / "native_model"
    log.append(_run_mcp(root, "project_export_model",
                        {"output_directory": str(models_dir)},
                        output / "mcp", executor))
    models = list(models_dir.rglob("*.model3.json"))
    if len(models) != 1:
        raise RuntimeError("TEXTURE_MESH_NATIVE_EXPORT_MISSING")
    from tools.vts_multiview_runtime import render_actual_native_moc3
    worker = render or render_actual_native_moc3
    native = worker(models[0], output / "native_pose")
    if (not isinstance(native, dict)
            or not native.get("native_pose_geometry_passed")
            or not native.get("pose_activity_passed")
            or not native.get("native_mouth_interpolation_passed")
            or not (native.get("parameter_isolation") or {}).get("passed")):
        raise RuntimeError("TEXTURE_MESH_NATIVE_POSE_GATE_FAILED")
    verdict = {
        "schema": "vtuber/psd2live-texture-remesh-v1",
        "status": "real_native_remesh_pose_passed",
        "model3": str(models[0]),
        "editable_project": str(copy),
        "targets": diagnostics,
        "native_pose_report": native,
        "mcp_receipts": log,
        "actual_vtube_studio_tracking_verified": False,
        "artistic_quality_verified": False,
        "render_vs_reference_fidelity_verified": False,
    }
    (output / "texture_mesh_verdict.json").write_text(
        json.dumps(verdict, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8")
    return verdict


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--psd2live-source", type=Path, required=True)
    parser.add_argument("--mesh-targets", type=Path, required=True,
                        help="JSON list of actual inspected mesh:<id> handles")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sensitivity", type=float, default=0.65)
    parser.add_argument("--min-length", type=float, default=8.0)
    parser.add_argument("--max-vertices", type=int, default=6000)
    args = parser.parse_args()
    verdict = refine_texture_meshes(
        proxy_root=args.psd2live_source,
        mesh_targets=json.loads(args.mesh_targets.read_text(encoding="utf-8")),
        output=args.output, sensitivity=args.sensitivity,
        min_length=args.min_length, max_vertices=args.max_vertices)
    print(json.dumps(verdict, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
