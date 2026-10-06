"""TripoSR mesh analysis for template fitting.

This module provides the analyze_reference function for extracting
canonical scale, principal axes, and ROI information from reconstructed
meshes.
"""

import pathlib
from typing import Dict, Any, List


def analyze_reference(mesh_path: str, output_dir: str) -> Dict[str, Any]:
    """Analyze a reconstructed mesh for template fitting.
    
    Computes:
    - Canonical scale normalization (fit to unit sphere)
    - Principal axes via PCA
    - Head ROI (region of interest)
    - Shoulder ROI
    - Front camera estimation
    
    Args:
        mesh_path: Path to the reconstructed mesh (.glb, .obj, etc.)
        output_dir: Directory to write reference_analysis.json.
        
    Returns:
        Dictionary with analysis results.
    """
    result = {
        "mesh_path": mesh_path,
        "status": "pending",
        "canonical_scale": 1.0,
        "principal_axes": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        "head_roi": {"center": [0.0, 0.0, 0.0], "radius": 0.1},
        "shoulder_roi": {"center": [0.0, -0.2, 0.0], "radius": 0.2},
        "front_camera": {"position": [0.0, 0.0, 2.0], "target": [0.0, 0.0, 0.0]}
    }
    
    # Try to load mesh and compute actual values
    try:
        import numpy as np
        
        try:
            import trimesh
            
            # Load mesh
            mesh = trimesh.load(mesh_path)
            
            # Get vertices
            if hasattr(mesh, 'vertices'):
                vertices = np.array(mesh.vertices)
            else:
                # Handle scene with multiple meshes
                vertices = np.vstack([m.vertices for m in mesh.geometry.values()])
            
            # Compute centroid
            centroid = np.mean(vertices, axis=0)
            result["centroid"] = centroid.tolist()
            
            # Compute canonical scale (fit to unit sphere)
            distances = np.linalg.norm(vertices - centroid, axis=1)
            max_distance = np.max(distances)
            result["canonical_scale"] = 1.0 / max_distance if max_distance > 0 else 1.0
            
            # Compute principal axes via PCA
            centered = vertices - centroid
            cov = np.cov(centered.T)
            eigenvalues, eigenvectors = np.linalg.eigh(cov)
            # Sort by eigenvalue (descending)
            idx = np.argsort(eigenvalues)[::-1]
            principal_axes = eigenvectors[:, idx].T
            result["principal_axes"] = principal_axes.tolist()
            
            # Estimate head ROI (top 25% of mesh by Y coordinate)
            y_coords = vertices[:, 1]
            y_sorted_idx = np.argsort(y_coords)
            top_quarter_count = len(vertices) // 4
            head_vertices = vertices[y_sorted_idx[-top_quarter_count:]]
            head_center = np.mean(head_vertices, axis=0)
            head_radius = np.max(np.linalg.norm(head_vertices - head_center, axis=1))
            result["head_roi"] = {
                "center": head_center.tolist(),
                "radius": float(head_radius)
            }
            
            # Estimate shoulder ROI (below head, above hips)
            y_mid = (np.max(y_coords) + np.min(y_coords)) / 2
            shoulder_vertices = vertices[
                (y_coords > y_mid - 0.1 * max_distance) & 
                (y_coords < y_mid + 0.1 * max_distance)
            ]
            if len(shoulder_vertices) > 0:
                shoulder_center = np.mean(shoulder_vertices, axis=0)
                shoulder_radius = np.max(np.linalg.norm(shoulder_vertices - shoulder_center, axis=1))
                result["shoulder_roi"] = {
                    "center": shoulder_center.tolist(),
                    "radius": float(shoulder_radius)
                }
            
            # Estimate front camera (assume +Z is front)
            result["front_camera"] = {
                "position": [centroid[0], centroid[1], centroid[2] + 2.0 * max_distance],
                "target": centroid.tolist()
            }
            
            result["status"] = "complete"
            
        except ImportError:
            # trimesh not available, use stub values
            result["status"] = "stub"
            result["warning"] = "trimesh not installed, using stub values"
            
    except ImportError:
        # numpy not available
        result["status"] = "error"
        result["error"] = "numpy not installed"
    
    # Write output
    _write_analysis_json(output_dir, result)
    
    return result


def _write_analysis_json(output_dir: str, result: Dict[str, Any]) -> None:
    """Write reference_analysis.json to output directory."""
    from vtuber_pipeline.core.utils import save_json
    
    pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)
    output_path = pathlib.Path(output_dir) / "reference_analysis.json"
    save_json(result, str(output_path))
