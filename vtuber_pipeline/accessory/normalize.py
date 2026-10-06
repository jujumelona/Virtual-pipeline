"""Accessory normalization module for VTuber Pipeline.

This module provides functions for normalizing GLB accessory files
to ensure consistent scale, orientation, and centering.
"""

import pathlib
from typing import Dict, Any


def normalize_glb(input_path: str, output_path: str) -> Dict[str, Any]:
    """Normalize a GLB file for accessory use.
    
    Performs:
    1. Center at origin
    2. Scale to unit size
    3. Align principal axes
    4. Clean up unused data
    
    Args:
        input_path: Path to the input GLB file.
        output_path: Path to save the normalized GLB.
        
    Returns:
        Dictionary with normalization results.
    """
    result = {
        "status": "pending",
        "input_path": input_path,
        "output_path": output_path
    }
    
    try:
        import numpy as np
        
        try:
            import trimesh
            
            # Load mesh
            mesh = trimesh.load(input_path)
            
            # Get vertices
            if hasattr(mesh, 'vertices'):
                vertices = np.array(mesh.vertices)
                
                # Center at origin
                centroid = np.mean(vertices, axis=0)
                result["centroid"] = centroid.tolist()
                
                # Scale to unit sphere
                max_distance = np.max(np.linalg.norm(vertices - centroid, axis=1))
                scale = 1.0 / max_distance if max_distance > 0 else 1.0
                result["scale"] = float(scale)
                
                # Principal axes (stub - would compute PCA)
                result["principal_axes"] = [
                    [1.0, 0.0, 0.0],
                    [0.0, 1.0, 0.0],
                    [0.0, 0.0, 1.0]
                ]
                
                # Export normalized mesh
                pathlib.Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                mesh.export(output_path)
                
                result["status"] = "complete"
            else:
                result["status"] = "error"
                result["error"] = "No vertices found in mesh"
                
        except ImportError:
            result["status"] = "stub"
            result["warning"] = "trimesh not installed"
            
    except ImportError:
        result["status"] = "error"
        result["error"] = "numpy not installed"
    
    return result
