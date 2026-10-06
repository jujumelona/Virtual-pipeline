"""Material configuration for VRM avatars.

This module provides functions for configuring MToon-compatible
materials for VTuber avatars.
"""

import pathlib
from typing import Dict, Any, List, Optional
from enum import Enum


class MaterialGroup(Enum):
    """Material groups for VTuber avatars."""
    FACE = "face"
    EYES = "eyes"
    HAIR = "hair"
    CLOTHES = "clothes"
    BODY = "body"


# List of material groups for avatar
MATERIAL_GROUPS = ["face", "eyes", "hair", "clothes", "body"]


def configure_materials(
    mesh_path: str,
    output_dir: str
) -> Dict[str, Any]:
    """Configure MToon-compatible materials for a mesh.
    
    Creates material configurations for each material group:
    - Face: Skin tone, high smoothness
    - Eyes: White sclera, colored iris
    - Hair: Gradient or solid color
    - Clothes: Fabric-like appearance
    - Body: Skin tone, lower smoothness
    
    Args:
        mesh_path: Path to the mesh.
        output_dir: Directory to write materials_report.json.
        
    Returns:
        Dictionary with material configurations.
    """
    result = {
        "status": "pending",
        "mesh_path": mesh_path,
        "materials": {}
    }
    
    # Create MToon configs for each group
    for group in MATERIAL_GROUPS:
        result["materials"][group] = _create_mtoon_config(group)
    
    result["status"] = "complete"
    
    # Write materials_report.json
    _write_materials_report(output_dir, result)
    
    return result


def classify_materials(
    mesh_path: str,
    texture_paths: Dict[str, str]
) -> Dict[str, Dict[str, Any]]:
    """Classify mesh materials into groups.
    
    Args:
        mesh_path: Path to the mesh.
        texture_paths: Dictionary mapping texture names to paths.
        
    Returns:
        Dictionary mapping group names to material info.
    """
    result = {}
    
    for group in MATERIAL_GROUPS:
        result[group] = {
            "material_name": f"{group}_material",
            "texture_path": texture_paths.get(group),
            "classification": group
        }
    
    return result


def _create_mtoon_config(group: str, texture_path: Optional[str] = None) -> Dict[str, Any]:
    """Create MToon-compatible material configuration.
    
    MToon is a toon shader used in VRM for stylized rendering.
    It supports:
    - Lit color and texture
    - Shade color and texture
    - Rim lighting
    - Outline
    
    Args:
        group: Material group name.
        texture_path: Optional path to texture file.
        
    Returns:
        Material configuration dictionary.
    """
    # Base MToon config
    config = {
        "name": f"{group}_material",
        "shader": "VRM/MToon",
        "renderQueue": 2000,
        "properties": {
            "_Color": [1.0, 1.0, 1.0, 1.0],
            "_MainTex": texture_path,
            "_ShadeColor": [0.97, 0.81, 0.76, 1.0],
            "_ShadeTexture": None,
            "_BumpScale": 1.0,
            "_BumpMap": None,
            "_ReceiveShadowRate": 1.0,
            "_ShadingGradeRate": 1.0,
            "_ShadeShift": 0.0,
            "_ShadeToony": 0.9,
            "_LightColorAttenuation": 0.0,
            "_IndirectLightIntensity": 0.1,
            "_RimColor": [0.0, 0.0, 0.0, 1.0],
            "_RimTexture": None,
            "_RimLightingMix": 1.0,
            "_RimFresnelPower": 1.0,
            "_RimLift": 0.0,
            "_OutlineWidth": 0.0,
            "_OutlineWidthTexture": None,
            "_OutlineColor": [0.0, 0.0, 0.0, 1.0],
            "_OutlineScaledMaxDistance": 1.0,
            "_OutlineLightingMix": 1.0
        }
    }
    
    # Customize per group
    if group == "face":
        config["properties"]["_ShadeToony"] = 0.95
        config["properties"]["_ShadeColor"] = [0.95, 0.85, 0.82, 1.0]
        config["properties"]["_RimLift"] = 0.1
    elif group == "eyes":
        config["properties"]["_ShadeToony"] = 0.9
        config["properties"]["_ShadeColor"] = [0.9, 0.9, 0.9, 1.0]
    elif group == "hair":
        config["properties"]["_ShadeToony"] = 0.85
        config["properties"]["_RimLift"] = 0.05
        config["properties"]["_OutlineWidth"] = 0.02
    elif group == "clothes":
        config["properties"]["_ShadeToony"] = 0.8
        config["properties"]["_OutlineWidth"] = 0.01
    elif group == "body":
        config["properties"]["_ShadeToony"] = 0.9
        config["properties"]["_ShadeColor"] = [0.95, 0.85, 0.82, 1.0]
    
    return config


def _write_materials_report(output_dir: str, result: Dict[str, Any]) -> None:
    """Write materials_report.json to output directory."""
    from vtuber_pipeline.core.utils import save_json
    
    pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)
    output_path = pathlib.Path(output_dir) / "materials_report.json"
    save_json(result, str(output_path))
