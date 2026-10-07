"""Optional physics planning for accessories."""

import pathlib
from typing import Dict, Any, Optional


def compute_bone_chain(accessory_path: str, joint_count: int = 3) -> Dict[str, Any]:
    """Estimate a simple chain along the accessory principal axis."""
    result: Dict[str, Any] = {"status": "pending", "bone_chains": []}
    try:
        import numpy as np
        import trimesh

        mesh = trimesh.load(accessory_path)
        if isinstance(mesh, trimesh.Scene):
            geometries = list(mesh.geometry.values())
            if not geometries:
                raise ValueError("Accessory scene contains no geometry")
            mesh = trimesh.util.concatenate(geometries)
        vertices = np.asarray(mesh.vertices)
        if len(vertices) < 4:
            raise ValueError("Not enough vertices for physics-chain estimation")

        center = vertices.mean(axis=0)
        covariance = np.cov((vertices - center).T)
        values, vectors = np.linalg.eigh(covariance)
        axis = vectors[:, int(np.argmax(values))]
        projection = (vertices - center) @ axis
        lo, hi = float(projection.min()), float(projection.max())
        samples = np.linspace(lo, hi, max(joint_count, 2))
        joints = [(center + axis * value).tolist() for value in samples]
        result.update({
            "status": "complete",
            "bone_chains": [{"name": "accessory", "positions": joints}],
            "principal_axis": axis.tolist(),
        })
    except Exception as exc:
        result["status"] = "error"
        result["error"] = str(exc)
    return result


def add_physics_chain(
    accessory_path: str,
    output_dir: str,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Plan optional accessory physics without claiming unsupported baking.

    Static accessories are the default and return ``skipped``. When physics is
    explicitly requested a geometric chain is estimated, but the result is
    marked ``partial`` until the static accessory baker gains skinned-mesh
    merging support.
    """
    cfg = dict(config or {})
    enabled = bool(cfg.get("enabled", False))
    result: Dict[str, Any] = {"accessory_path": accessory_path}

    if not enabled:
        result.update({"status": "skipped", "reason": "physics disabled"})
    else:
        chain = compute_bone_chain(accessory_path, int(cfg.get("joint_count", 3)))
        if chain.get("status") == "complete":
            result.update({
                "status": "partial",
                "config": {
                    "stiffness": float(cfg.get("stiffness", 0.5)),
                    "gravity": float(cfg.get("gravity", 0.1)),
                    "drag": float(cfg.get("drag", 0.2)),
                    "hit_radius": float(cfg.get("hit_radius", 0.02)),
                },
                "bone_chains": chain["bone_chains"],
                "warning": "Dynamic accessory skin/bone merge is not supported by static bake.",
            })
        else:
            result.update({"status": "error", "error": chain.get("error", "chain estimation failed")})

    pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)
    from vtuber_pipeline.core.utils import save_json
    output_path = pathlib.Path(output_dir) / "physics.json"
    save_json(result, str(output_path))
    result["output_path"] = str(output_path)
    return result
