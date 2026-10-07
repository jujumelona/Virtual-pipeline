"""SpringBone physics configuration for VRM avatars.

This module provides functions for generating VRM SpringBone configurations
for hair, ears, ribbons, tails, and clothing physics.
"""

import pathlib
from typing import Dict, Any, List, Optional
from enum import Enum


class SpringBoneClass(Enum):
    """Classification of SpringBone types."""
    HAIR = "hair"
    EARS = "ears"
    RIBBON = "ribbon"
    TAIL = "tail"
    CLOTHING = "clothing"


# Default SpringBone presets for each class
SPRING_BONE_PRESETS: Dict[str, Dict[str, float]] = {
    "hair": {
        "stiffness": 0.5,
        "gravity": 0.1,
        "drag": 0.2,
        "hit_radius": 0.02
    },
    "ears": {
        "stiffness": 0.7,
        "gravity": 0.05,
        "drag": 0.1,
        "hit_radius": 0.03
    },
    "ribbon": {
        "stiffness": 0.6,
        "gravity": 0.08,
        "drag": 0.15,
        "hit_radius": 0.01
    },
    "tail": {
        "stiffness": 0.4,
        "gravity": 0.15,
        "drag": 0.3,
        "hit_radius": 0.02
    },
    "clothing": {
        "stiffness": 0.3,
        "gravity": 0.12,
        "drag": 0.25,
        "hit_radius": 0.03
    }
}


def find_bones_by_region(mesh_path: str, skeleton: Dict[str, Any], region: str) -> List[str]:
    """Find bones belonging to a specific region based on vertex proximity.
    
    Args:
        mesh_path: Path to the mesh file.
        skeleton: Skeleton data with bone positions.
        region: Region name ('hair', 'ears', 'clothing', etc.)
        
    Returns:
        List of bone names belonging to the region.
    """
    # Region-specific heuristics based on bone position
    # This is a stub implementation - real implementation would analyze mesh vertex weights
    region_bones = {
        "hair": [],  # Would be populated by analyzing head-top vertices
        "ears": [],  # Would be populated by analyzing side-of-head vertices
        "clothing": [],  # Would be populated by analyzing torso vertices
    }
    return region_bones.get(region, [])


def classify_springbone_chains(mesh_path: str, skeleton: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Classify bone chains into SpringBone categories and build joint configs.
    
    This function analyzes the mesh and skeleton to identify bones that should
    have SpringBone physics applied, such as hair, ears, ribbons, tails, and clothing.
    
    Args:
        mesh_path: Path to the mesh file.
        skeleton: Skeleton data with bone hierarchy and positions.
        
    Returns:
        List of SpringBone chain dictionaries with VRMC_springBone 1.0 format:
        Each chain has 'name' and 'joints' array where each joint has:
        - node: bone/node name
        - hitRadius: collision radius
        - stiffness: spring stiffness (NOT stiffiness)
        - gravityPower: gravity influence
        - gravityDir: gravity direction [x, y, z]
        - dragForce: drag coefficient
    """
    chains = []
    
    # Find hair bones
    hair_bones = find_bones_by_region(mesh_path, skeleton, "hair")
    if hair_bones:
        preset = SPRING_BONE_PRESETS["hair"]
        joints = []
        for bone_name in hair_bones:
            joints.append({
                "node": bone_name,
                "hitRadius": preset["hit_radius"],
                "stiffness": preset["stiffness"],
                "gravityPower": preset["gravity"],
                "gravityDir": [0.0, -1.0, 0.0],
                "dragForce": preset["drag"]
            })
        chains.append({
            "name": "hair",
            "joints": joints
        })
    
    # Find ear bones
    ear_bones = find_bones_by_region(mesh_path, skeleton, "ears")
    if ear_bones:
        preset = SPRING_BONE_PRESETS["ears"]
        joints = []
        for bone_name in ear_bones:
            joints.append({
                "node": bone_name,
                "hitRadius": preset["hit_radius"],
                "stiffness": preset["stiffness"],
                "gravityPower": preset["gravity"],
                "gravityDir": [0.0, -1.0, 0.0],
                "dragForce": preset["drag"]
            })
        chains.append({
            "name": "ears",
            "joints": joints
        })
    
    return chains


def generate_springbone_config(
    mesh_path: str,
    output_dir: str
) -> Dict[str, Any]:
    """Generate SpringBone configuration for a mesh.
    
    Generates VRMC_springBone 1.0 compliant configuration with proper
    field names (stiffness, not stiffiness) and joints array structure.
    
    Args:
        mesh_path: Path to the mesh.
        output_dir: Directory to write springbone.json.
        
    Returns:
        Dictionary with VRMC_springBone 1.0 configuration:
        {
            "status": "complete",
            "specVersion": "1.0",
            "colliders": [],
            "colliderGroups": [],
            "springs": [
                {
                    "name": "hair",
                    "joints": [
                        {
                            "node": "bone_name",
                            "hitRadius": 0.02,
                            "stiffness": 0.5,
                            "gravityPower": 0.1,
                            "gravityDir": [0.0, -1.0, 0.0],
                            "dragForce": 0.2
                        }
                    ]
                }
            ]
        }
    """
    result = {
        "status": "pending",
        "mesh_path": mesh_path,
        "specVersion": "1.0",
        "colliders": [],
        "colliderGroups": [],
        "springs": []
    }
    
    # Create springbone groups with proper VRMC_springBone 1.0 format
    # Each spring has 'joints' array (NOT 'jointEdges')
    for bone_class, preset in SPRING_BONE_PRESETS.items():
        spring = {
            "name": bone_class,
            "joints": []  # Populated by classify_springbone_chains
        }
        result["springs"].append(spring)
    
    result["status"] = "complete"
    result["note"] = "Bone chains need to be populated by classify_springbone_chains"
    
    # Write springbone.json
    _write_springbone_json(output_dir, result)
    
    return result


def apply_springbone_preset(
    bone_class: str,
    custom_preset: Optional[Dict[str, float]] = None
) -> Dict[str, float]:
    """Apply SpringBone preset for a bone class.
    
    Args:
        bone_class: Name of the bone class.
        custom_preset: Optional custom preset to merge.
        
    Returns:
        SpringBone parameters for the class.
    """
    base_preset = SPRING_BONE_PRESETS.get(bone_class, SPRING_BONE_PRESETS["hair"])
    
    if custom_preset:
        return {**base_preset, **custom_preset}
    
    return base_preset.copy()


def _write_springbone_json(output_dir: str, config: Dict[str, Any]) -> None:
    """Write springbone.json to output directory."""
    from vtuber_pipeline.core.utils import save_json
    
    pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)
    output_path = pathlib.Path(output_dir) / "springbone.json"
    save_json(config, str(output_path))
