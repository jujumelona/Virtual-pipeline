"""Accessory anchor extraction from a real VRM/glTF skeleton."""

import pathlib
from typing import Dict, Any, List, Optional

from vtuber_pipeline.core.gltf import load_gltf


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
    nodes = gltf.nodes or []
    parents = {}
    for parent_idx, node in enumerate(nodes):
        for child in (node.children or []):
            child = int(child)
            if child in parents:
                raise ValueError(f"VRM node {child} has multiple parents")
            parents[child] = parent_idx

    cache = {}
    visiting = set()

    def world(idx):
        if idx in cache:
            return cache[idx]
        if idx in visiting:
            raise ValueError("VRM node hierarchy contains a cycle")
        visiting.add(idx)
        local = _local_matrix(nodes[idx])
        parent = parents.get(idx)
        value = world(parent) @ local if parent is not None else local
        visiting.remove(idx)
        cache[idx] = value
        return value

    return [world(i) for i in range(len(nodes))]


def _validate_vector(
    value: Any,
    length: int,
    *,
    name: str,
    default: Optional[List[float]] = None,
) -> List[float]:
    import numpy as np

    if value is None:
        if default is None:
            raise ValueError(f"{name} is required")
        value = default
    arr = np.asarray(value, dtype=float)
    if arr.shape != (length,) or not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} must contain {length} finite numbers")
    return arr.astype(float).tolist()


def _decompose_world_linear(linear):
    """Return pure rotation quaternion and inherited scale for a bone world matrix."""
    import numpy as np
    from scipy.spatial.transform import Rotation

    linear = np.asarray(linear, dtype=float)
    if linear.shape != (3, 3) or not np.all(np.isfinite(linear)):
        raise ValueError("Bone world transform contains an invalid linear matrix")
    if abs(float(np.linalg.det(linear))) < 1e-10:
        raise ValueError("Bone world transform is singular")

    scale = np.linalg.norm(linear, axis=0)
    if np.any(scale <= 1e-10):
        raise ValueError("Bone world transform contains zero scale")

    # Polar decomposition removes inherited scale/shear before converting to
    # the quaternion used by the collision-space transform.
    u, _, vh = np.linalg.svd(linear)
    rotation = u @ vh
    if np.linalg.det(rotation) < 0.0:
        u[:, -1] *= -1.0
        rotation = u @ vh
    quaternion = Rotation.from_matrix(rotation).as_quat()
    return rotation, quaternion.astype(float).tolist(), scale.astype(float).tolist()


def _build_anchor(
    *,
    name: str,
    bone: str,
    offset: List[float],
    target_size: float,
    node_index: int,
    world,
    attachment_rotation: Optional[List[float]] = None,
) -> Dict[str, Any]:
    import numpy as np
    from scipy.spatial.transform import Rotation

    if not isinstance(target_size, (int, float)) or not np.isfinite(target_size):
        raise ValueError(f"{name}.target_size must be finite")
    target_size = float(target_size)
    if target_size <= 0.0:
        raise ValueError(f"{name}.target_size must be > 0")

    offset = _validate_vector(offset, 3, name=f"{name}.offset")
    local_quat = _validate_vector(
        attachment_rotation,
        4,
        name=f"{name}.rotation",
        default=[0.0, 0.0, 0.0, 1.0],
    )
    local_norm = float(np.linalg.norm(local_quat))
    if local_norm <= 1e-10:
        raise ValueError(f"{name}.rotation quaternion has zero length")
    local_quat = (np.asarray(local_quat, dtype=float) / local_norm).tolist()

    linear = np.asarray(world[:3, :3], dtype=float)
    parent_rotation_matrix, parent_quat, world_scale = _decompose_world_linear(linear)
    local_rotation_matrix = Rotation.from_quat(local_quat).as_matrix()
    world_rotation = Rotation.from_matrix(
        parent_rotation_matrix @ local_rotation_matrix
    ).as_quat().astype(float).tolist()

    offset_h = np.array([*offset, 1.0], dtype=float)
    position = (world @ offset_h)[:3]
    if not np.all(np.isfinite(position)):
        raise ValueError(f"{name} world position is non-finite")

    return {
        "name": name,
        "bone": bone,
        "node_index": int(node_index),
        "offset": offset,
        "position": position.astype(float).tolist(),
        "attachment_rotation": local_quat,
        "rotation": world_rotation,
        "parent_world_rotation": parent_quat,
        "world_scale": world_scale,
        "world_linear": linear.tolist(),
        "world_to_local_linear": np.linalg.inv(linear).tolist(),
        "target_size": target_size,
    }


def _humanoid_node_map(gltf) -> Dict[str, int]:
    """Resolve semantic VRM humanoid names independently of raw node names."""
    extensions = gltf.extensions or {}
    if not isinstance(extensions, dict):
        return {}
    vrm = extensions.get("VRMC_vrm") or {}
    humanoid = vrm.get("humanoid") if isinstance(vrm, dict) else None
    human_bones = (
        humanoid.get("humanBones")
        if isinstance(humanoid, dict)
        else None
    )
    if not isinstance(human_bones, dict):
        return {}

    node_count = len(gltf.nodes or [])
    mapping: Dict[str, int] = {}
    for semantic, binding in human_bones.items():
        node = binding.get("node") if isinstance(binding, dict) else None
        if isinstance(node, int) and 0 <= node < node_count:
            mapping[str(semantic)] = node
    return mapping


def _resolve_anchor_node(
    identifier: str,
    *,
    humanoid_nodes: Dict[str, int],
    name_to_idx: Dict[str, int],
) -> Optional[int]:
    """Resolve a VRM semantic bone first, then an exact raw node name."""
    if identifier in humanoid_nodes:
        return humanoid_nodes[identifier]
    return name_to_idx.get(identifier)


def generate_anchor_manifest(
    vrm_path: str,
    output_dir: str,
    custom_anchor: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Read real bone nodes and derive preset plus optional CUSTOM anchors."""
    result: Dict[str, Any] = {
        "status": "pending",
        "vrm_path": vrm_path,
        "anchors": [],
    }
    try:
        path = pathlib.Path(vrm_path)
        if not path.is_file():
            raise FileNotFoundError(f"Base VRM not found: {vrm_path}")
        gltf = load_gltf(path)
        nodes = gltf.nodes or []
        name_to_idx = {
            node.name: i
            for i, node in enumerate(nodes)
            if node.name
        }
        humanoid_nodes = _humanoid_node_map(gltf)
        worlds = _world_matrices(gltf)

        missing = []
        for anchor in ANCHOR_POINTS:
            idx = _resolve_anchor_node(
                anchor["bone"],
                humanoid_nodes=humanoid_nodes,
                name_to_idx=name_to_idx,
            )
            if idx is None:
                missing.append(anchor["bone"])
                continue
            result["anchors"].append(_build_anchor(
                name=anchor["name"],
                bone=anchor["bone"],
                offset=anchor["offset"],
                target_size=float(anchor["target_size"]),
                node_index=idx,
                world=worlds[idx],
            ))

        if custom_anchor is not None:
            if not isinstance(custom_anchor, dict):
                raise ValueError("custom_anchor must be an object")
            parent_bone = str(custom_anchor.get("parent_bone") or "").strip()
            if not parent_bone:
                raise ValueError("CUSTOM anchor requires parent_bone")
            idx = _resolve_anchor_node(
                parent_bone,
                humanoid_nodes=humanoid_nodes,
                name_to_idx=name_to_idx,
            )
            if idx is None:
                raise ValueError(
                    f"CUSTOM anchor parent bone/node not found: {parent_bone!r}"
                )
            result["anchors"].append(_build_anchor(
                name="CUSTOM",
                bone=parent_bone,
                offset=custom_anchor.get("offset"),
                target_size=float(custom_anchor.get("target_size", 0.12)),
                node_index=idx,
                world=worlds[idx],
                attachment_rotation=custom_anchor.get("rotation"),
            ))

        if not result["anchors"]:
            raise ValueError("No supported humanoid anchor bones were found in the VRM")
        result["status"] = "complete"
        if missing:
            result["warnings"] = [
                f"Missing anchor bone: {name}"
                for name in sorted(set(missing))
            ]
    except Exception as exc:
        result["status"] = "error"
        result["error"] = str(exc)

    _write_anchor_manifest(output_dir, result)
    return result


def _write_anchor_manifest(output_dir: str, result: Dict[str, Any]) -> None:
    from vtuber_pipeline.core.utils import save_json

    pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)
    save_json(result, str(pathlib.Path(output_dir) / "anchor_manifest.json"))
