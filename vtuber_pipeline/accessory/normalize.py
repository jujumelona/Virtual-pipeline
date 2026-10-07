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

        mesh = trimesh.load(input_path, process=False)
        if isinstance(mesh, trimesh.Scene):
            mesh = mesh.to_mesh()
        if not isinstance(mesh, trimesh.Trimesh):
            raise ValueError("Accessory input contains no triangle mesh")
        source_visual_kind = getattr(mesh.visual, "kind", None)
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

        reloaded = trimesh.load(str(out), process=False)
        if isinstance(reloaded, trimesh.Scene):
            reloaded = reloaded.to_mesh()
        if not isinstance(reloaded, trimesh.Trimesh) or len(reloaded.vertices) == 0:
            raise RuntimeError("Normalized accessory cannot be re-imported")
        output_visual_kind = getattr(reloaded.visual, "kind", None)
        if source_visual_kind in {"vertex", "texture"} and output_visual_kind is None:
            raise RuntimeError(
                f"Accessory visual data was lost during normalization: "
                f"{source_visual_kind} -> {output_visual_kind}"
            )

        result.update({
            "source_visual_kind": source_visual_kind,
            "output_visual_kind": output_visual_kind,
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
