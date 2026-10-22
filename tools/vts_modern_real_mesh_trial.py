"""Real v3.6 native MCP texture-guided mesh edit + saved project/export.

No fixture IDs or synthetic mesh pass: paginate the loaded CMO3 rig objects,
ask upstream for texture-line previews, commit an actual operation against
the copied project, export genuine MOC3/CMO3, and validate runtime references.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.vts_modern_editable_project import _external_client, _serve_local_mcp
from tools.vts_psd2live_modern import ensure_modern_psd2live
from tools.vts_psd2live import validate_psd2live_output


def native_mesh_targets(editor) -> list[str]:
    ids = []
    offset = 0
    while True:
        page = editor.call("workspace_inspect",
                           {"scope": "objects", "offset": offset, "limit": 64})[0]
        values = page.get("items")
        if not isinstance(values, list) or page.get("total") is None:
            raise RuntimeError("PSD2LIVE_MESH_INSPECTION_INVALID")
        for obj in values:
            if isinstance(obj, dict) and obj.get("target", "").startswith("mesh:"):
                ids.append(obj["target"])
        next_offset = page.get("next")
        if next_offset is None:
            break
        if not isinstance(next_offset, int) or next_offset <= offset:
            raise RuntimeError("PSD2LIVE_MESH_PAGING_INVALID")
        offset = next_offset
    if len(ids) != len(set(ids)):
        raise RuntimeError("PSD2LIVE_DUPLICATE_MESH_IDS")
    return ids


def run_real_mesh_trial(project: Path, output: Path, *,
                        source: Path | None = None, clone: bool = False,
                        connect=None, serve=None,
                        max_candidates: int = 32) -> dict:
    project = Path(project).resolve(strict=True)
    if project.suffix != ".psd2live":
        raise ValueError("Must edit actual .psd2live archive")
    output = Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("Actual mesh trial requires clean output")
    if not 1 <= max_candidates <= 128:
        raise ValueError("Mesh preview budget must be 1..128")
    root = ensure_modern_psd2live(source, clone=clone)
    output.mkdir(parents=True, exist_ok=True)
    settings = {"sensitivity": 0.7, "min_length": 8.0,
                "max_lines": 32, "max_vertices": 5000,
                "fill": False, "bands": False}
    result = {
        "schema": "vtuber/actual-psd2live-native-mesh-remesh-trial-v1",
        "source_project": str(project),
        "native_project_opened": False,
        "editable_copy_saved": False,
        "mesh_changes_committed": False,
        "model_exported": False,
        "native_render_verified": False,
        "vtube_studio_tracking_verified": False,
        "visual_quality_improved": False,
        "candidates": [],
    }
    receipt = output / "real_mesh_trial.json"
    def store():
        receipt.write_text(json.dumps(result, ensure_ascii=False, indent=2,
                                      default=str), encoding="utf-8")
    try:
        session = serve or _serve_local_mcp
        with session(root, output / "mcp") as (endpoint, token, _):
            factory = connect or _external_client
            with factory(root / "mcp_proxy.py", endpoint, token) as editor:
                opened = editor.edit("project_open", path=str(project))
                if not opened.get("state") or not opened.get("project_id"):
                    raise RuntimeError("PSD2LIVE_NOT_OPENED")
                result["native_project_opened"] = True
                copy = output / "remesh-edited.psd2live"
                saved = editor.edit("project_save_as", path=str(copy))
                if not saved.get("state") or not copy.is_file():
                    raise RuntimeError("PSD2LIVE_EDITABLE_COPY_NOT_SAVED")
                result["editable_copy_saved"] = True
                ids = native_mesh_targets(editor)
                result["actual_loaded_mesh_count"] = len(ids)
                if not ids:
                    raise RuntimeError("PSD2LIVE_ACTUAL_CMO3_HAS_NO_MESHES")
                target = None
                for handle in ids[:max_candidates]:
                    try:
                        preview = editor.call(
                            "layer_mesh_structure_preview",
                            {"target": handle, "settings": settings})[0]
                    except Exception as exc:
                        result["candidates"].append({
                            "target": handle, "preview_error": str(exc)[:450]})
                        continue
                    lines = preview.get("lines", []) if isinstance(preview, dict) else []
                    result["candidates"].append({
                        "target": handle, "texture_structure_lines": len(lines)})
                    if lines and isinstance(lines, list):
                        target = handle
                        break
                if target is None:
                    raise RuntimeError("NO_ACTUAL_TEXTURE_LINES_FOR_NATIVE_REMESH")
                result["selected_target"] = target
                # It must be a genuinely loaded ID, and the upstream editor
                # must acknowledge a NEW saved state and history node.
                state_before = editor.state()
                change = editor.edit("layer_mesh_structure",
                                     target=target, settings=settings)
                state_after = editor.state()
                if not change.get("state") or state_after == state_before:
                    raise RuntimeError("NATIVE_MESH_REBUILD_NOT_COMMITTED")
                result["mesh_changes_committed"] = True
                result["before_state"] = state_before
                result["after_state"] = state_after
                # Keep native output separate from the original PSD/CMO3.
                editor.edit("project_save")
                export = output / "native_export"
                exported = editor.edit("project_export_model",
                                       output_directory=str(export))
                checked = validate_psd2live_output(export, edition="pro")
                if not checked["runtime_references_valid"] or not checked["cmo3"]:
                    raise RuntimeError("NATIVE_MESH_EXPORT_INVALID")
                result["model_exported"] = True
                result["model3_json"] = checked["model3_json"]
                result["cmo3"] = checked["cmo3"]
                result["editable_project"] = str(copy)
                result["export_receipt"] = exported
    finally:
        store()
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-candidates", type=int, default=32)
    args = parser.parse_args()
    r = run_real_mesh_trial(args.project, args.output,
                            source=args.source, max_candidates=args.max_candidates)
    print(json.dumps({k: v for k, v in r.items()
                      if k not in ("candidates", "export_receipt")},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
