"""Eye-gaze configuration derived from actual rigged GLB eye nodes."""

import pathlib
from typing import Dict, Any, List
from dataclasses import dataclass, field


@dataclass
class GazeConfig:
    left_eye_center: List[float] = field(default_factory=list)
    right_eye_center: List[float] = field(default_factory=list)
    forward_vector: List[float] = field(default_factory=lambda: [0.0, 0.0, 1.0])
    yaw_limit_deg: float = 30.0
    pitch_limit_deg: float = 20.0


def _local_matrix(node):
    import numpy as np
    if getattr(node, "matrix", None):
        return np.asarray(node.matrix, dtype=float).reshape((4, 4), order="F")
    t = np.asarray(node.translation or [0.0, 0.0, 0.0], dtype=float)
    s = np.asarray(node.scale or [1.0, 1.0, 1.0], dtype=float)
    x, y, z, w = node.rotation or [0.0, 0.0, 0.0, 1.0]
    r = np.array([
        [1 - 2*y*y - 2*z*z, 2*x*y - 2*z*w, 2*x*z + 2*y*w],
        [2*x*y + 2*z*w, 1 - 2*x*x - 2*z*z, 2*y*z - 2*x*w],
        [2*x*z - 2*y*w, 2*y*z + 2*x*w, 1 - 2*x*x - 2*y*y],
    ], dtype=float)
    m = np.eye(4, dtype=float)
    m[:3, :3] = r @ np.diag(s)
    m[:3, 3] = t
    return m


def _world_matrices(gltf):
    nodes = gltf.nodes or []
    parents = {}
    for p, node in enumerate(nodes):
        for child in (node.children or []):
            parents[child] = p
    cache = {}
    def world(i):
        if i in cache:
            return cache[i]
        local = _local_matrix(nodes[i])
        parent = parents.get(i)
        cache[i] = world(parent) @ local if parent is not None else local
        return cache[i]
    return [world(i) for i in range(len(nodes))]


def compute_eye_bones(mesh_path: str) -> Dict[str, Any]:
    """Read leftEye/rightEye world transforms from a rigged GLB/VRM."""
    from pygltflib import GLTF2
    import numpy as np

    path = pathlib.Path(mesh_path)
    if not path.is_file():
        raise FileNotFoundError(f"Rigged mesh not found: {mesh_path}")
    gltf = GLTF2().load(str(path))
    nodes = gltf.nodes or []
    by_name = {node.name: i for i, node in enumerate(nodes) if node.name}
    missing = [name for name in ("leftEye", "rightEye") if name not in by_name]
    if missing:
        raise ValueError(f"Missing eye bone nodes: {missing}")

    worlds = _world_matrices(gltf)
    result = {}
    for key, name in (("left_eye", "leftEye"), ("right_eye", "rightEye")):
        world = worlds[by_name[name]]
        forward = world[:3, 2]
        norm = np.linalg.norm(forward)
        if norm > 1e-8:
            forward = forward / norm
        result[key] = {
            "node_index": by_name[name],
            "position": world[:3, 3].tolist(),
            "forward": forward.tolist(),
        }
    return result


def configure_gaze(mesh_path: str, output_dir: str) -> Dict[str, Any]:
    """Configure look-at from actual eye bone nodes."""
    result: Dict[str, Any] = {"status": "pending", "mesh_path": mesh_path}
    try:
        bones = compute_eye_bones(mesh_path)
        left = bones["left_eye"]
        right = bones["right_eye"]
        forward = [
            (left["forward"][i] + right["forward"][i]) / 2.0
            for i in range(3)
        ]
        config = GazeConfig(
            left_eye_center=left["position"],
            right_eye_center=right["position"],
            forward_vector=forward,
        )
        result["status"] = "complete"
        result["config"] = {
            "left_eye_center": config.left_eye_center,
            "right_eye_center": config.right_eye_center,
            "forward_vector": config.forward_vector,
            "yaw_limit_deg": config.yaw_limit_deg,
            "pitch_limit_deg": config.pitch_limit_deg,
            "left_eye_node": left["node_index"],
            "right_eye_node": right["node_index"],
        }
    except Exception as exc:
        result["status"] = "error"
        result["error"] = str(exc)
        result["config"] = {}

    _write_gaze_json(output_dir, result)
    return result


def compute_gaze_limits(bones: Dict[str, Any]) -> Dict[str, Any]:
    return {"yaw_min": -30, "yaw_max": 30, "pitch_min": -20, "pitch_max": 20}


def _write_gaze_json(output_dir: str, config: Dict[str, Any]) -> None:
    from vtuber_pipeline.core.utils import save_json
    pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)
    save_json(config, str(pathlib.Path(output_dir) / "gaze.json"))
