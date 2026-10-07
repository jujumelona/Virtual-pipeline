"""Prepared accessory artifacts: portable attachment manifest and preview."""

from __future__ import annotations

import pathlib
from typing import Any, Dict


def write_attachment_manifest(
    accessory_glb: str,
    anchor_name: str,
    fit_result: Dict[str, Any],
    collision_result: Dict[str, Any],
    output_dir: str,
) -> Dict[str, Any]:
    """Write the portable bone-local attachment contract for one accessory."""
    from vtuber_pipeline.core.utils import save_json

    output = pathlib.Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    path = output / "attachment.json"

    transform = dict(fit_result.get("transform") or {})
    required = {
        "translation": 3,
        "rotation": 4,
        "scale": 3,
    }
    for key, length in required.items():
        value = transform.get(key)
        if not isinstance(value, list) or len(value) != length:
            return {
                "status": "error",
                "error": f"attachment transform {key} must contain {length} values",
            }

    manifest = {
        "schema": "vtuber-pipeline/accessory-attachment-v1",
        "accessory_glb": pathlib.Path(accessory_glb).name,
        "anchor": anchor_name,
        "parent_bone": fit_result.get("parent_bone"),
        "parent_node_index": fit_result.get("anchor_node_index"),
        "transform": transform,
        "target_size": fit_result.get("target_size"),
        "collision": {
            "checked": collision_result.get("status") == "complete",
            "resolved": bool(collision_result.get("resolved")),
            "penetration_count": int(
                collision_result.get("penetration_count", 0)
            ),
            "max_penetration_depth": float(
                collision_result.get("max_penetration_depth", 0.0)
            ),
        },
    }
    if not manifest["parent_bone"]:
        return {
            "status": "error",
            "error": "attachment manifest is missing parent_bone",
        }

    save_json(manifest, str(path))
    if not path.is_file() or path.stat().st_size == 0:
        return {
            "status": "error",
            "error": "attachment.json was not written",
        }
    return {
        "status": "complete",
        "output_path": str(path),
        "attachment": manifest,
    }


def render_preview(
    accessory_glb: str,
    output_dir: str,
    size: int = 512,
) -> Dict[str, Any]:
    """Render a deterministic headless +Z orthographic accessory preview."""
    try:
        import numpy as np
        import trimesh
        from PIL import Image, ImageDraw

        mesh = trimesh.load(accessory_glb, process=False)
        if isinstance(mesh, trimesh.Scene):
            mesh = mesh.to_mesh()
        if not isinstance(mesh, trimesh.Trimesh) or len(mesh.vertices) == 0:
            raise ValueError("Accessory preview source has no triangle mesh")

        vertices = np.asarray(mesh.vertices, dtype=float)
        faces = np.asarray(mesh.faces, dtype=np.int64)
        if len(faces) == 0:
            raise ValueError("Accessory preview source has no faces")
        if not np.all(np.isfinite(vertices)):
            raise ValueError("Accessory preview source has non-finite vertices")

        xy = vertices[:, :2]
        lower = xy.min(axis=0)
        upper = xy.max(axis=0)
        extent = upper - lower
        max_extent = max(float(np.max(extent)), 1e-8)
        margin = max_extent * 0.08
        lower -= margin
        upper += margin
        extent = upper - lower

        canvas = int(max(128, min(int(size), 2048)))
        scale = min(
            (canvas - 2.0) / max(float(extent[0]), 1e-8),
            (canvas - 2.0) / max(float(extent[1]), 1e-8),
        )
        center = (lower + upper) * 0.5

        projected = np.empty_like(xy)
        projected[:, 0] = (
            (xy[:, 0] - center[0]) * scale + canvas * 0.5
        )
        projected[:, 1] = (
            canvas * 0.5 - (xy[:, 1] - center[1]) * scale
        )

        # Camera looks from +Z toward the origin: draw lower-Z faces first.
        depth = vertices[faces, 2].mean(axis=1)
        order = np.argsort(depth)

        # Bound preview work for dense TripoSR meshes while keeping a uniform
        # surface sample.
        max_faces = 12000
        if len(order) > max_faces:
            sample = np.linspace(
                0,
                len(order) - 1,
                max_faces,
                dtype=np.int64,
            )
            order = order[sample]

        vertex_colors = None
        try:
            colors = np.asarray(mesh.visual.vertex_colors)
            if colors.ndim == 2 and len(colors) == len(vertices):
                vertex_colors = colors[:, :4]
        except Exception:
            vertex_colors = None

        image = Image.new("RGBA", (canvas, canvas), (248, 248, 248, 255))
        draw = ImageDraw.Draw(image, "RGBA")

        for face_index in order:
            face = faces[int(face_index)]
            polygon = [
                (
                    float(projected[index, 0]),
                    float(projected[index, 1]),
                )
                for index in face
            ]
            if vertex_colors is not None:
                color = np.mean(
                    vertex_colors[face],
                    axis=0,
                ).astype(np.uint8)
                fill = tuple(int(v) for v in color.tolist())
            else:
                fill = (178, 183, 191, 255)
            draw.polygon(
                polygon,
                fill=fill,
                outline=(88, 92, 99, 110),
            )

        output = pathlib.Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)
        path = output / "preview.png"
        image.convert("RGB").save(path, format="PNG")
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError("Accessory preview PNG was not written")

        return {
            "status": "complete",
            "output_path": str(path),
            "face_count": int(len(faces)),
            "rendered_face_count": int(len(order)),
        }
    except Exception as exc:
        return {
            "status": "error",
            "error": str(exc),
        }
