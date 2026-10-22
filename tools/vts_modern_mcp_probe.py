"""Inspect genuine v3.6 CMO3 mesh/deformer IDs and operation schemas.

This does not classify an export as an improved rig. The response log is a
ground-truth input to safe, actually applied mesh/keyform changes.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.vts_modern_editable_project import _external_client, _serve_local_mcp
from tools.vts_psd2live_modern import ensure_modern_psd2live


def inspect_native_editability(project: Path, output: Path, *,
                               source: Path | None = None,
                               clone: bool = False,
                               connect=None, serve=None) -> dict:
    project = Path(project).resolve(strict=True)
    if project.suffix != ".psd2live":
        raise ValueError("Real .psd2live project is required")
    root = ensure_modern_psd2live(source, clone=clone)
    output = Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("Use a fresh inspection output directory")
    output.mkdir(parents=True, exist_ok=True)
    server = serve or _serve_local_mcp
    with server(root, output / "mcp") as (endpoint, token, log):
        client = (connect or _external_client)(root / "mcp_proxy.py",
                                                endpoint, token)
        with client as editor:
            load = editor.edit("project_open", path=str(project))
            if not load.get("state") or not load.get("project_id"):
                raise RuntimeError("PSD2LIVE_PROJECT_OPEN_UNCONFIRMED")
            inspected = {}
            for scope in ("project", "objects", "layers", "parameters"):
                value = editor.call("workspace_inspect", {"scope": scope})[0]
                if not isinstance(value, dict):
                    raise RuntimeError("PSD2LIVE_INSPECT_NOT_OBJECT: " + scope)
                inspected[scope] = value
            if inspected["project"].get("project_id") != load["project_id"]:
                raise RuntimeError("PSD2LIVE_INSPECT_DIFFERENT_PROJECT")
            # Store raw native details for deterministic mesh/keyform binding.
            report = {
                "schema": "vtuber/v360-real-mcp-introspection-v1",
                "source_project": str(project),
                "project_open_verified": True,
                "native_objects_inspected": True,
                "raw_inspection": inspected,
                "mesh_or_warp_edit_committed": False,
                "rendered_pose_improvement_verified": False,
                "vtube_studio_tracking_verified": False,
            }
            (output / "native_edit_inspection.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2,
                           default=str), encoding="utf-8")
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--project", type=Path, required=True)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    report = inspect_native_editability(args.project, args.output,
                                        source=args.source)
    raw = report["raw_inspection"]
    print(json.dumps({
        "status": "REAL_EDITABLE_PROJECT_INSPECTED",
        "project_id": raw["project"].get("project_id"),
        "objects": str(raw["objects"])[:7000],
        "layers": str(raw["layers"])[:3000],
        "parameters": str(raw["parameters"])[:1500],
        "mesh_or_warp_edit_committed": False,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
