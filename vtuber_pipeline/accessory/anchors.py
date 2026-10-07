"""Accessory anchor extraction from a real VRM/glTF skeleton."""

import pathlib
from typing import Dict, Any, List


ANCHOR_POINTS: List[Dict[str, Any]] = [
    {"name": "HEAD_TOP", "bone": "head", "offset": [0.0, 0.10, 0.0], "target_size": 0.18},
    {"name": "FACE", "bone": "head", "offset": [0.0, 0.0, 0.07], "target_size": 0.14},
    {"name": "LEFT_EAR", "bone": "head", "offset": [0.08, 0.02, 0.0], "target_size": 0.06},
    {"name": "RIGHT_EAR", "bone": "head", "offset": [-0.08, 0.02, 0.0], "target_size": 0.06},
    {"name": "NECK", "bone": "neck", "offset": [0.0, 0.0, 0.0], "target_size": 0.12},
    {"name": "CHEST", "bone": "chest", "offset": [0.0, 0.0, 0.07], "target_size": 0.18},
    {"name": "BACK", "bone": "chest", "offset": [0.0, 0.0, -0.08], "target_size": 0.28},
    {"name": "LEFT_SHOULDER", "bone": "leftShoulder", "offset": [0.0, 0.0, 0.0], "target_size": 0.10},
    {"name": "RIGHT_SHOULDER", "bone": "rightShoulder", "offset": [0.0, 0.0, 0.0], "target_size": 0.10},
    {"name": "LEFT_HAND", "bone": "leftHand", "offset": [0.0, 0.0, 0.0], "target_size": 0.12},
    {"name": "RIGHT_HAND", "bone": "rightHand", "offset": [0.0, 0.0, 0.0], "target_size": 0.12},
    {"name": "LEFT_FOOT", "bone": "leftFoot", "offset": [0.0, 0.0, 0.0], "target_size": 0.14},
    {"name": "RIGHT_FOOT", "bone": "rightFoot", "offset": [0.0, 0.0, 0.0], "target_size": 0.14},
    {"name": "HIPS", "bone": "hips", "offset": [0.0, 0.0, 0.0], "target_size": 0.18},
]


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
    import numpy as np

    nodes = gltf.nodes or []
    parents = {}
    for parent_idx, node in enumerate(nodes):
        for child in (node.children or []):
            parents[child] = parent_idx

    cache = {}
    def world(idx):
        if idx in cache:
            return cache[idx]
        local = _local_matrix(nodes[idx])
        parent = parents.get(idx)
        cache[idx] = world(parent) @ local if parent is not None else local
        return cache[idx]

    return [world(i) for i in range(len(nodes))]


def generate_anchor_manifest(vrm_path: str, output_dir: str) -> Dict[str, Any]:
    """Read actual bone nodes and derive accessory anchor transforms."""
    result: Dict[str, Any] = {"status": "pending", "vrm_path": vrm_path, "anchors": []}
    try:
        import numpy as np
        from pygltflib import GLTF2

        path = pathlib.Path(vrm_path)
        if not path.is_file():
            raise FileNotFoundError(f"Base VRM not found: {vrm_path}")
        gltf = GLTF2().load(str(path))
        nodes = gltf.nodes or []
        name_to_idx = {node.name: i for i, node in enumerate(nodes) if node.name}
        worlds = _world_matrices(gltf)

        missing = []
        for anchor in ANCHOR_POINTS:
            idx = name_to_idx.get(anchor["bone"])
            if idx is None:
                missing.append(anchor["bone"])
                continue
            world = worlds[idx]
            offset_h = np.array([*anchor["offset"], 1.0], dtype=float)
            position = (world @ offset_h)[:3].tolist()
            linear = world[:3, :3]
            if abs(float(np.linalg.det(linear))) < 1e-10:
                raise ValueError(f"Anchor bone has singular world transform: {anchor['bone']}")
            world_to_local_linear = np.linalg.inv(linear)
            result["anchors"].append({
                "name": anchor["name"],
                "bone": anchor["bone"],
                "node_index": idx,
                "offset": anchor["offset"],
                "position": position,
                "rotation": list(nodes[idx].rotation or [0.0, 0.0, 0.0, 1.0]),
                "world_linear": linear.tolist(),
                "world_to_local_linear": world_to_local_linear.tolist(),
                "target_size": anchor["target_size"],
            })

        if not result["anchors"]:
            raise ValueError("No supported humanoid anchor bones were found in the VRM")
        result["status"] = "complete"
        if missing:
            result["warnings"] = [f"Missing anchor bone: {name}" for name in sorted(set(missing))]
    except Exception as exc:
        result["status"] = "error"
        result["error"] = str(exc)

    _write_anchor_manifest(output_dir, result)
    return result


def _write_anchor_manifest(output_dir: str, result: Dict[str, Any]) -> None:
    from vtuber_pipeline.core.utils import save_json

    pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)
    save_json(result, str(pathlib.Path(output_dir) / "anchor_manifest.json"))
