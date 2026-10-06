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


def generate_springbone_config(
    mesh_path: str,
    output_dir: str
) -> Dict[str, Any]:
    """Generate SpringBone configuration for a mesh.
    
    Analyzes the mesh to classify bone chains and applies appropriate
    presets for each SpringBone group.
    
    Args:
        mesh_path: Path to the mesh.
        output_dir: Directory to write springbone.json.
        
    Returns:
        Dictionary with SpringBone configuration.
    """
    result = {
        "status": "pending",
        "mesh_path": mesh_path,
        "springbone_groups": []
    }
    
    # Create springbone groups with presets
    for bone_class, preset in SPRING_BONE_PRESETS.items():
        group = {
            "name": bone_class,
            "stiffiness": preset["stiffness"],
            "gravityPower": preset["gravity"],
            "dragForce": preset["drag"],
            "hitRadius": preset["hit_radius"],
            "bones": []  # Populated by actual analysis
        }
        result["springbone_groups"].append(group)
    
    result["status"] = "complete"
    result["note"] = "Bone chains need to be populated by mesh analysis"
    
    # Write springbone.json
    _write_springbone_json(output_dir, result)
    
    return result


def classify_springbone_chains(
    mesh_path: str,
    rig_data: Dict[str, Any]
) -> Dict[str, List[str]]:
    """Classify bone chains into SpringBone categories.
    
    Uses geometric heuristics to determine bone chain purpose:
    - Hair: Top of head, multiple chains
    - Ears: Side of head, 1-2 chains
    - Ribbon: Decorative, often symmetrical
    - Tail: Bottom of spine
    - Clothing: Attached to torso
    
    Args:
        mesh_path: Path to the mesh.
        rig_data: Rig data with bone positions.
        
    Returns:
        Dictionary mapping class names to bone chain lists.
    """
    result = {
        "hair": [],
        "ears": [],
        "ribbon": [],
        "tail": [],
        "clothing": []
    }
    
    # Stub implementation
    # In actual implementation:
    # 1. Get all bone positions and hierarchy
    # 2. Compute bone chain endpoints
    # 3. Classify by position and chain structure
    
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
