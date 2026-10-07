"""Accessory GLB normalization."""

import pathlib
from typing import Dict, Any


def normalize_glb(input_path: str, output_path: str) -> Dict[str, Any]:
    """Center an accessory, scale it to unit extent, and record PCA axes."""
    result: Dict[str, Any] = {
        "status": "pending", "input_path": input_path, "output_path": output_path
    }
    try:
        import numpy as np
        import trimesh

        mesh = trimesh.load(input_path)
        if isinstance(mesh, trimesh.Scene):
            geometries = list(mesh.geometry.values())
            if not geometries:
                raise ValueError("Accessory scene contains no geometry")
            mesh = trimesh.util.concatenate(geometries)
        vertices = np.asarray(mesh.vertices)
        if len(vertices) == 0:
            raise ValueError("Accessory mesh has no vertices")

        bounds_min, bounds_max = mesh.bounds
        center = (bounds_min + bounds_max) / 2.0
        extents = bounds_max - bounds_min
        max_extent = float(np.max(extents))
        if max_extent <= 1e-8:
            raise ValueError("Accessory mesh has zero extent")

        mesh.apply_translation(-center)
        scale = 1.0 / max_extent
        mesh.apply_scale(scale)

        centered = np.asarray(mesh.vertices)
        covariance = np.cov(centered.T)
        values, vectors = np.linalg.eigh(covariance)
        order = np.argsort(values)[::-1]
        principal_axes = vectors[:, order].T

        out = pathlib.Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        mesh.export(str(out))
        if not out.is_file() or out.stat().st_size == 0:
            raise RuntimeError("Normalized accessory export produced no file")

        result.update({
            "status": "complete",
            "source_center": center.tolist(),
            "source_extents": extents.tolist(),
            "scale": scale,
            "principal_axes": principal_axes.tolist(),
        })
    except Exception as exc:
        result["status"] = "error"
        result["error"] = str(exc)
    return result
