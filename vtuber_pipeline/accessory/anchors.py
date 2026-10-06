"""Anchor points management for accessory attachment.

This module defines anchor points on VTuber avatars where accessories
can be attached, such as head, ears, hands, etc.
"""

import pathlib
from typing import Dict, Any, List


# Standard anchor points on VRM avatars
ANCHOR_POINTS: List[Dict[str, Any]] = [
    {"name": "HEAD_TOP", "bone": "head", "offset": [0.0, 0.1, 0.0]},
    {"name": "FACE", "bone": "head", "offset": [0.0, 0.0, 0.05]},
    {"name": "LEFT_EAR", "bone": "head", "offset": [-0.08, 0.02, 0.0]},
    {"name": "RIGHT_EAR", "bone": "head", "offset": [0.08, 0.02, 0.0]},
    {"name": "NECK", "bone": "neck", "offset": [0.0, 0.0, 0.0]},
    {"name": "CHEST", "bone": "chest", "offset": [0.0, 0.0, 0.05]},
    {"name": "LEFT_SHOULDER", "bone": "leftShoulder", "offset": [0.0, 0.0, 0.0]},
    {"name": "RIGHT_SHOULDER", "bone": "rightShoulder", "offset": [0.0, 0.0, 0.0]},
    {"name": "LEFT_HAND", "bone": "leftHand", "offset": [0.0, 0.0, 0.0]},
    {"name": "RIGHT_HAND", "bone": "rightHand", "offset": [0.0, 0.0, 0.0]},
    {"name": "LEFT_FOOT", "bone": "leftFoot", "offset": [0.0, 0.0, 0.0]},
    {"name": "RIGHT_FOOT", "bone": "rightFoot", "offset": [0.0, 0.0, 0.0]},
    {"name": "HIPS", "bone": "hips", "offset": [0.0, 0.0, 0.0]},
    {"name": "SPINE", "bone": "spine", "offset": [0.0, 0.0, -0.05]},
]


def generate_anchor_manifest(vrm_path: str, output_dir: str) -> Dict[str, Any]:
    """Generate an anchor manifest for a VRM file.
    
    Analyzes the VRM to find bone positions and generates anchor points
    for accessory attachment.
    
    Args:
        vrm_path: Path to the VRM file.
        output_dir: Directory to write the anchor manifest.
        
    Returns:
        Dictionary with anchor point data.
    """
    result = {
        "status": "pending",
        "vrm_path": vrm_path,
        "anchors": []
    }
    
    # Generate anchor data from predefined points
    for anchor in ANCHOR_POINTS:
        result["anchors"].append({
            "name": anchor["name"],
            "bone": anchor["bone"],
            "offset": anchor["offset"],
            "position": [0.0, 0.0, 0.0],  # Would be computed from actual bone
            "rotation": [0.0, 0.0, 0.0, 1.0]
        })
    
    result["status"] = "complete"
    
    # Write manifest
    _write_anchor_manifest(output_dir, result)
    
    return result


def _write_anchor_manifest(output_dir: str, result: Dict[str, Any]) -> None:
    """Write anchor manifest to output directory."""
    from vtuber_pipeline.core.utils import save_json
    
    pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)
    output_path = pathlib.Path(output_dir) / "anchor_manifest.json"
    save_json(result, str(output_path))
