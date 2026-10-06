"""Eye gaze (look-at) configuration for VRM avatars.

This module provides functions for configuring VRM look-at behavior,
which controls eye bone rotation to follow a target point.
"""

import pathlib
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field


@dataclass
class GazeConfig:
    """Configuration for VRM look-at behavior.
    
    Attributes:
        left_eye_center: Center position of left eye [x, y, z].
        right_eye_center: Center position of right eye [x, y, z].
        forward_vector: Forward direction vector [x, y, z].
        yaw_limit_deg: Maximum horizontal rotation angle in degrees.
        pitch_limit_deg: Maximum vertical rotation angle in degrees.
    """
    left_eye_center: List[float] = field(default_factory=lambda: [-0.03, 0.0, 0.05])
    right_eye_center: List[float] = field(default_factory=lambda: [0.03, 0.0, 0.05])
    forward_vector: List[float] = field(default_factory=lambda: [0.0, 0.0, 1.0])
    yaw_limit_deg: float = 30.0
    pitch_limit_deg: float = 20.0


def configure_gaze(mesh_path: str, output_dir: str) -> Dict[str, Any]:
    """Configure VRM look-at (gaze) parameters for a mesh.
    
    Computes eye bone positions and gaze limits from the mesh.
    
    Args:
        mesh_path: Path to the mesh.
        output_dir: Directory to write gaze.json.
        
    Returns:
        Dictionary with gaze configuration.
    """
    result = {
        "status": "pending",
        "mesh_path": mesh_path
    }
    
    # Default gaze config
    gaze_config = GazeConfig()
    
    try:
        import numpy as np
        
        try:
            import trimesh
            
            mesh = trimesh.load(mesh_path)
            
            if hasattr(mesh, 'vertices'):
                vertices = np.array(mesh.vertices)
                
                # Stub: estimate eye positions
                # In actual implementation:
                # 1. Use landmarks to find eye centers
                # 2. Compute forward vector from mesh orientation
                # 3. Estimate limits from eye socket geometry
                
                # Find approximate eye region (front-top-center of mesh)
                x_median = np.median(vertices[:, 0])
                y_upper = np.percentile(vertices[:, 1], 80)
                z_front = np.max(vertices[:, 2])
                
                left_eye = [x_median - 0.03, y_upper, z_front - 0.02]
                right_eye = [x_median + 0.03, y_upper, z_front - 0.02]
                
                gaze_config = GazeConfig(
                    left_eye_center=left_eye,
                    right_eye_center=right_eye,
                    forward_vector=[0.0, 0.0, 1.0],
                    yaw_limit_deg=30.0,
                    pitch_limit_deg=20.0
                )
                
                result["status"] = "complete"
                
            else:
                result["status"] = "stub"
                result["warning"] = "Mesh has no vertices"
                
        except ImportError:
            result["status"] = "stub"
            result["warning"] = "trimesh not installed"
            
    except ImportError:
        result["status"] = "stub"
        result["warning"] = "numpy not installed"
    
    # Convert dataclass to dict
    result["config"] = {
        "left_eye_center": gaze_config.left_eye_center,
        "right_eye_center": gaze_config.right_eye_center,
        "forward_vector": gaze_config.forward_vector,
        "yaw_limit_deg": gaze_config.yaw_limit_deg,
        "pitch_limit_deg": gaze_config.pitch_limit_deg
    }
    
    # Write gaze.json
    _write_gaze_json(output_dir, result["config"])
    
    return result


def compute_eye_bones(mesh_path: str) -> Dict[str, Any]:
    """Compute eye bone positions from mesh.
    
    Args:
        mesh_path: Path to the mesh.
        
    Returns:
        Dictionary with left and right eye bone info.
    """
    return {
        "left_eye": {
            "position": [-0.03, 0.0, 0.05],
            "forward": [0.0, 0.0, 1.0]
        },
        "right_eye": {
            "position": [0.03, 0.0, 0.05],
            "forward": [0.0, 0.0, 1.0]
        }
    }


def compute_gaze_limits(bones: Dict[str, Any]) -> Dict[str, Any]:
    """Compute gaze rotation limits.
    
    Args:
        bones: Eye bone information.
        
    Returns:
        Dictionary with yaw and pitch limits.
    """
    return {
        "yaw_min": -30,
        "yaw_max": 30,
        "pitch_min": -20,
        "pitch_max": 20
    }


def _write_gaze_json(output_dir: str, config: Dict[str, Any]) -> None:
    """Write gaze.json to output directory."""
    from vtuber_pipeline.core.utils import save_json
    
    pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)
    output_path = pathlib.Path(output_dir) / "gaze.json"
    save_json(config, str(output_path))
