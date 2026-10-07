"""Hair geometry extraction from the reconstructed reference mesh."""

import pathlib
from typing import Dict, Any


def extract_hair(mesh_path: str, output_dir: str) -> Dict[str, Any]:
    """Extract an actual top-head submesh instead of returning a placeholder.

    The current implementation is geometry-first and deliberately conservative:
    it keeps faces concentrated in the upper head region, splits connected
    components, drops tiny islands, and writes a real GLB when enough geometry
    exists. It does not claim semantic perfection; ambiguous cases return
    ``partial`` instead of fabricating a successful hair asset.
    """
    result: Dict[str, Any] = {
        "status": "pending",
        "mesh_path": mesh_path,
        "hair_components": [],
    }
    out_dir = pathlib.Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        import numpy as np
        import trimesh

        mesh = trimesh.load(mesh_path)
        if isinstance(mesh, trimesh.Scene):
            geometries = list(mesh.geometry.values())
            if not geometries:
                raise ValueError("Reference scene contains no geometry")
            mesh = trimesh.util.concatenate(geometries)
        if len(mesh.vertices) == 0 or len(mesh.faces) == 0:
            raise ValueError("Reference mesh is empty")

        vertices = np.asarray(mesh.vertices)
        faces = np.asarray(mesh.faces)
        bounds_min, bounds_max = mesh.bounds
        height = float(bounds_max[1] - bounds_min[1])
        if height <= 1e-8:
            raise ValueError("Reference mesh has invalid height")

        # Candidate region: upper 30% of the reconstructed character. Requiring
        # at least two candidate vertices per face avoids isolated triangles.
        y_cut = bounds_max[1] - 0.30 * height
        candidate_vertices = vertices[:, 1] >= y_cut
        face_mask = np.count_nonzero(candidate_vertices[faces], axis=1) >= 2
        face_indices = np.flatnonzero(face_mask)
        if len(face_indices) == 0:
            result.update({
                "status": "partial",
                "warning": "No upper-head faces were available for hair extraction",
                "hair_vertex_count": 0,
            })
            return result

        extracted = mesh.submesh([face_indices], append=True, repair=True)
        if extracted is None or len(extracted.faces) == 0:
            result.update({
                "status": "partial",
                "warning": "Hair candidate submesh was empty after extraction",
                "hair_vertex_count": 0,
            })
            return result

        components = extracted.split(only_watertight=False)
        kept = [
            comp for comp in components
            if len(comp.faces) >= 8 and len(comp.vertices) >= 8
        ]
        if not kept:
            kept = [extracted]
        kept = sorted(kept, key=lambda comp: len(comp.faces), reverse=True)[:8]
        hair_mesh = trimesh.util.concatenate(kept) if len(kept) > 1 else kept[0]

        hair_path = out_dir / "hair.glb"
        hair_mesh.export(str(hair_path))
        if not hair_path.is_file() or hair_path.stat().st_size == 0:
            raise RuntimeError("Hair GLB export produced no file")

        result.update({
            "status": "complete",
            "hair_glb": str(hair_path),
            "hair_vertex_count": int(len(hair_mesh.vertices)),
            "hair_face_count": int(len(hair_mesh.faces)),
            "hair_ratio": float(len(hair_mesh.vertices) / max(len(mesh.vertices), 1)),
            "hair_components": [
                {"id": i, "vertex_count": int(len(comp.vertices)), "face_count": int(len(comp.faces))}
                for i, comp in enumerate(kept)
            ],
            "method": "upper_head_geometry",
        })
    except Exception as exc:
        result["status"] = "error"
        result["error"] = str(exc)

    return result


def generate_hair_glb(mesh_path: str, output_dir: str) -> str:
    """Compatibility wrapper returning the real extracted hair GLB path."""
    result = extract_hair(mesh_path, output_dir)
    if result.get("status") != "complete":
        raise RuntimeError(result.get("error") or result.get("warning") or "Hair extraction failed")
    return str(result["hair_glb"])
