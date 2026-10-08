"""VRMC_springBone 1.0 configuration generation."""

from __future__ import annotations

import pathlib
from typing import Dict, Any, List, Optional

from vtuber_pipeline.core.gltf import load_gltf


SPRING_BONE_PRESETS: Dict[str, Dict[str, float]] = {
    "hair": {"stiffness": 0.50, "gravity": 0.10, "drag": 0.20, "hit_radius": 0.02},
    "ears": {"stiffness": 0.70, "gravity": 0.08, "drag": 0.15, "hit_radius": 0.01},
    "tail": {"stiffness": 0.40, "gravity": 0.15, "drag": 0.30, "hit_radius": 0.02},
    "clothing": {"stiffness": 0.30, "gravity": 0.12, "drag": 0.25, "hit_radius": 0.03},
}

_REGION_TOKENS = {
    "hair": ("hair", "bang", "ponytail", "braid", "ahoge"),
    "ears": ("ear_", "ear.", "catear", "foxear", "rabbit_ear"),
    "tail": ("tail",),
    "clothing": ("ribbon", "skirt", "cape", "cloth", "sleeve", "tie"),
}


def _load_node_names(mesh_path: str) -> List[str]:
    """Read glTF/GLB node names without fabricating secondary bones."""
    try:
        from pygltflib import GLTF2
    except ImportError as exc:
        raise ImportError("pygltflib is required for SpringBone node discovery") from exc

    path = pathlib.Path(mesh_path)
    if not path.is_file():
        raise FileNotFoundError(f"Rigged GLB not found: {mesh_path}")

    gltf = load_gltf(path)
    return [node.name or "" for node in (gltf.nodes or [])]


def find_bones_by_region(
    mesh_path: str, skeleton: Optional[Dict[str, Any]], region: str
) -> List[str]:
    """Find real secondary-bone node names for one SpringBone region."""
    names: List[str] = []
    if skeleton:
        names.extend(str(name) for name in skeleton.get("names", []) if name)
    if not names:
        names = _load_node_names(mesh_path)

    tokens = _REGION_TOKENS.get(region, ())
    return [
        name for name in names
        if any(token in name.lower() for token in tokens)
    ]


def _joint_from_name(name: str, preset: Dict[str, float]) -> Dict[str, Any]:
    return {
        "node": name,
        "hitRadius": preset["hit_radius"],
        "stiffness": preset["stiffness"],
        "gravityPower": preset["gravity"],
        "gravityDir": [0.0, -1.0, 0.0],
        "dragForce": preset["drag"],
    }


def classify_springbone_chains(
    mesh_path: str, skeleton: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """Build SpringBone chains from actual secondary-bone node names."""
    chains: List[Dict[str, Any]] = []
    for region, preset in SPRING_BONE_PRESETS.items():
        bone_names = find_bones_by_region(mesh_path, skeleton, region)
        if not bone_names:
            continue
        if region == "hair":
            import re
            strands = {}
            for name in bone_names:
                match = re.fullmatch(r"hairStrand([0-9]+)(Root|Mid|Tip)", name)
                if match:
                    strands.setdefault(int(match.group(1)), {})[match.group(2)] = name
            if strands:
                for strand_id, parts in sorted(strands.items()):
                    if set(parts) != {"Root", "Mid", "Tip"}:
                        raise ValueError(f"Hair strand {strand_id} has incomplete springbone chain")
                    chains.append({
                        "name": f"hairStrand{strand_id:02d}",
                        "joints": [
                            _joint_from_name(parts[level], preset)
                            for level in ("Root", "Mid", "Tip")
                        ],
                        "colliderGroups": [],
                    })
                continue
        chains.append({
            "name": region,
            "joints": [_joint_from_name(name, preset) for name in bone_names],
            "colliderGroups": [],
        })
    return chains


def generate_springbone_config(mesh_path: str, output_dir: str) -> Dict[str, Any]:
    """Generate a VRMC_springBone 1.0 config from a rigged GLB.

    Empty/fabricated chains are not emitted. A rig with no secondary bones is
    an explicit error because Avatar Mode requires a real secondary chain.
    """
    result: Dict[str, Any] = {
        "status": "pending",
        "mesh_path": mesh_path,
        "specVersion": "1.0",
        "colliders": [],
        "colliderGroups": [],
        "springs": [],
    }
    try:
        springs = classify_springbone_chains(mesh_path)
        result["springs"] = springs
        if springs:
            result["status"] = "complete"
            result["joint_count"] = sum(len(s["joints"]) for s in springs)
        else:
            result["status"] = "error"
            result["joint_count"] = 0
            result["error"] = (
                "No secondary-bone nodes were found in the rigged GLB"
            )
    except Exception as exc:
        result["status"] = "error"
        result["error"] = str(exc)

    _write_springbone_json(output_dir, result)
    return result


def apply_springbone_preset(
    bone_class: str, custom_preset: Optional[Dict[str, float]] = None
) -> Dict[str, float]:
    """Return a deterministic physics preset for one secondary-bone class."""
    base = SPRING_BONE_PRESETS.get(bone_class, SPRING_BONE_PRESETS["hair"])
    return {**base, **(custom_preset or {})}


def _write_springbone_json(output_dir: str, config: Dict[str, Any]) -> None:
    from vtuber_pipeline.core.utils import save_json

    pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)
    save_json(config, str(pathlib.Path(output_dir) / "springbone.json"))
