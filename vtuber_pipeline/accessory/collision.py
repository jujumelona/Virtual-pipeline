"""Approximate accessory/avatar collision detection and push-out."""

import pathlib

from typing import Dict, Any, Optional


def _apply_transform(vertices, transform):
    import numpy as np

    if not transform:
        return vertices.copy()
    scale = np.asarray(transform.get("scale", [1.0, 1.0, 1.0]), dtype=float)
    translation = np.asarray(transform.get("translation", [0.0, 0.0, 0.0]), dtype=float)
    x, y, z, w = transform.get("rotation", [0.0, 0.0, 0.0, 1.0])
    rotation = np.array([
        [1 - 2*y*y - 2*z*z, 2*x*y - 2*z*w, 2*x*z + 2*y*w],
        [2*x*y + 2*z*w, 1 - 2*x*x - 2*z*z, 2*y*z - 2*x*w],
        [2*x*z - 2*y*w, 2*y*z + 2*x*w, 1 - 2*x*x - 2*y*y],
    ], dtype=float)
    return (vertices * scale) @ rotation.T + translation


def _load_world_mesh(path: str):
    """Load mesh geometry with every scene-node transform baked into vertices."""
    import trimesh

    loaded = trimesh.load(
        path,
        file_type="glb" if pathlib.Path(path).suffix.lower() == ".vrm" else None,
        process=False,
    )
    if isinstance(loaded, trimesh.Scene):
        loaded = loaded.to_mesh()
    if not isinstance(loaded, trimesh.Trimesh) or len(loaded.vertices) == 0:
        raise ValueError(f"Mesh contains no usable triangle geometry: {path}")
    return loaded


def check_collision(
    accessory_path: str,
    body_path: str,
    world_transform: Optional[Dict[str, Any]] = None,
    clearance: float = 0.003,
) -> Dict[str, Any]:
    """Detect approximate penetration using nearest body vertices/normals.

    This does real geometry work and does not default to "no collision". The
    signed test is an approximation suitable for anchor fitting; callers can
    apply the returned push-out vector and recheck.
    """
    result: Dict[str, Any] = {
        "status": "pending",
        "accessory_path": accessory_path,
        "body_path": body_path,
        "collisions": [],
    }
    try:
        import numpy as np
        import trimesh
        from scipy.spatial import cKDTree

        accessory = _load_world_mesh(accessory_path)
        body = _load_world_mesh(body_path)

        acc_vertices = _apply_transform(np.asarray(accessory.vertices), world_transform)
        body_vertices = np.asarray(body.vertices)
        body_normals = np.asarray(body.vertex_normals)

        tree = cKDTree(body_vertices)
        distances, nearest_idx = tree.query(acc_vertices)
        nearest_points = body_vertices[nearest_idx]
        nearest_normals = body_normals[nearest_idx]
        signed = np.einsum("ij,ij->i", acc_vertices - nearest_points, nearest_normals)

        penetration_mask = (signed < 0.0) & (distances <= max(clearance * 6.0, 0.02))
        penetration_indices = np.flatnonzero(penetration_mask)
        push_vectors = []
        for idx in penetration_indices:
            depth = float(-signed[idx] + clearance)
            push_vectors.append(nearest_normals[idx] * depth)

        if push_vectors:
            pushout = np.mean(np.asarray(push_vectors), axis=0)
            max_depth = float(np.max(-signed[penetration_mask]))
        else:
            pushout = np.zeros(3, dtype=float)
            max_depth = 0.0

        result.update({
            "status": "complete",
            "collision_detected": bool(len(penetration_indices)),
            "penetration_count": int(len(penetration_indices)),
            "penetration_ratio": float(len(penetration_indices) / max(len(acc_vertices), 1)),
            "max_penetration_depth": max_depth,
            "pushout_vector": pushout.tolist(),
            "clearance": clearance,
        })
    except Exception as exc:
        result["status"] = "error"
        result["error"] = str(exc)

    return result


def resolve_collision(
    accessory_path: str,
    body_path: str,
    world_transform: Optional[Dict[str, Any]] = None,
    clearance: float = 0.003,
) -> Dict[str, Any]:
    """Return a corrected world translation using one geometry push-out step."""
    result = check_collision(accessory_path, body_path, world_transform, clearance)
    if result.get("status") != "complete":
        return result

    transform = dict(world_transform or {})
    translation = list(transform.get("translation", [0.0, 0.0, 0.0]))
    push = result.get("pushout_vector", [0.0, 0.0, 0.0])
    corrected = [float(a + b) for a, b in zip(translation, push)]
    result["corrected_world_translation"] = corrected
    result["resolved"] = bool(result.get("collision_detected"))
    return result
