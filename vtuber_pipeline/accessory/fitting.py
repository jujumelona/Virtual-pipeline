"""Accessory fitting against a VRM anchor manifest."""

import pathlib
from typing import Dict, Any


def fit_accessory(
    accessory_path: str,
    anchor_name: str,
    anchor_manifest: Dict[str, Any],
    output_dir: str,
) -> Dict[str, Any]:
    """Normalize and scale an accessory for a concrete avatar anchor.

    The mesh scale is baked into the exported GLB. Bone-relative translation
    is kept in metadata so the baker can parent the accessory without
    double-transforming its vertices.
    """
    result: Dict[str, Any] = {
        "status": "pending",
        "accessory_path": accessory_path,
        "anchor_name": anchor_name,
    }

    anchor = next(
        (a for a in anchor_manifest.get("anchors", []) if a.get("name") == anchor_name),
        None,
    )
    if anchor is None:
        return {**result, "status": "error", "error": f"Anchor {anchor_name!r} not found"}

    try:
        import numpy as np
        import trimesh

        mesh = trimesh.load(accessory_path)
        if isinstance(mesh, trimesh.Scene):
            geometries = list(mesh.geometry.values())
            if not geometries:
                raise ValueError("Accessory GLB contains no geometry")
            mesh = trimesh.util.concatenate(geometries)
        if len(mesh.vertices) == 0:
            raise ValueError("Accessory mesh is empty")

        bounds_min, bounds_max = mesh.bounds
        center = (bounds_min + bounds_max) / 2.0
        extents = bounds_max - bounds_min
        max_extent = float(np.max(extents))
        if max_extent <= 1e-8:
            raise ValueError("Accessory mesh has zero extent")

        target_size = float(anchor.get("target_size", 0.12))
        if not np.isfinite(target_size) or target_size <= 0.0:
            raise ValueError("Anchor target_size must be a positive finite number")
        uniform_scale = target_size / max_extent

        # Canonicalize accessory around its own origin and bake the uniform
        # scale. Translation remains bone-relative in attachment metadata.
        mesh.apply_translation(-center)
        mesh.apply_scale(uniform_scale)

        output_path = pathlib.Path(output_dir) / "fitted_accessory.glb"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        mesh.export(str(output_path))
        if not output_path.is_file() or output_path.stat().st_size == 0:
            raise RuntimeError("Fitted accessory export produced no file")

        local_translation = list(anchor.get("offset", [0.0, 0.0, 0.0]))
        local_rotation = list(
            anchor.get("attachment_rotation", [0.0, 0.0, 0.0, 1.0])
        )
        world_position = list(anchor.get("position", local_translation))
        world_rotation = list(anchor.get("rotation", local_rotation))
        world_scale = list(anchor.get("world_scale", [1.0, 1.0, 1.0]))
        result.update({
            "status": "complete",
            "output_path": str(output_path),
            "parent_bone": anchor.get("bone", "head"),
            "transform": {
                "translation": local_translation,
                "rotation": local_rotation,
                "scale": [1.0, 1.0, 1.0],
            },
            "world_transform": {
                "translation": world_position,
                "rotation": world_rotation,
                "scale": world_scale,
            },
            "source_extents": extents.tolist(),
            "target_size": target_size,
            "baked_uniform_scale": uniform_scale,
            "world_to_local_linear": anchor.get("world_to_local_linear"),
            "anchor_node_index": anchor.get("node_index"),
        })
    except Exception as exc:
        result["status"] = "error"
        result["error"] = str(exc)

    return result
