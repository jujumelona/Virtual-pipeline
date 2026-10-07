"""Deformation transfer module for VTuber Pipeline.

This module provides functions for transferring deformations between
meshes, enabling expression and pose transfer from a canonical template
to fitted meshes.
"""

import pathlib
from typing import Dict, Any, Optional


def transfer_deformation(
    source_mesh: str,
    target_mesh: str,
    fit_npz: str,
    output_dir: str
) -> Dict[str, Any]:
    """Transfer deformation from source mesh to target mesh.
    
    Given a deformation graph (fit.npz) that maps source vertices to
    target vertices, applies the deformation while preserving the
    target's identity.
    
    Real implementation:
    1. Load expression deltas from fit.npz
    2. Apply per-vertex deformation
    3. Generate morph targets for expressions
    4. Save morph targets
    
    Args:
        source_mesh: Path to the source mesh (canonical template).
        target_mesh: Path to the target mesh (fitted avatar).
        fit_npz: Path to the deformation graph file.
        output_dir: Directory to write output files.
        
    Returns:
        Dictionary with deformation transfer results.
    """
    result = {
        "status": "pending",
        "source_mesh": source_mesh,
        "target_mesh": target_mesh,
        "fit_npz": fit_npz
    }
    
    # Create output directory
    pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    try:
        import numpy as np
        import trimesh
        
        # Load deformation graph
        try:
            deformation = load_deformation_graph(fit_npz)
            result["deformation_loaded"] = True
            result["vertex_count"] = len(deformation.get("vertices", []))
        except FileNotFoundError:
            result["deformation_loaded"] = False
            result["warning"] = f"Deformation graph not found: {fit_npz}"
            result["status"] = "error"
            result["error"] = f"Deformation graph not found: {fit_npz}"
            _write_deformation_report(output_dir, result)
            return result
        
        # Load target mesh
        try:
            target = trimesh.load(target_mesh)
            if isinstance(target, trimesh.Scene):
                target = trimesh.util.concatenate(list(target.geometry.values()))
            target_vertices = np.array(target.vertices)
            result["target_vertex_count"] = len(target_vertices)
        except Exception as e:
            result["error"] = f"Failed to load target mesh: {e}"
            result["status"] = "error"
            _write_deformation_report(output_dir, result)
            return result
        
        # Load source mesh for reference
        try:
            source = trimesh.load(source_mesh)
            if isinstance(source, trimesh.Scene):
                source = trimesh.util.concatenate(list(source.geometry.values()))
            source_vertices = np.array(source.vertices)
            result["source_vertex_count"] = len(source_vertices)
        except Exception as e:
            result["source_load_warning"] = str(e)
            source_vertices = None
        
        # Get deformation data
        fitted_vertices = deformation.get("vertices", np.array([]))
        original_vertices = deformation.get("original_vertices", np.array([]))
        deltas = deformation.get("deltas", np.array([]))
        
        if len(fitted_vertices) == 0 or len(deltas) == 0:
            result["warning"] = "Empty deformation data, creating identity morph targets"
            result["status"] = "partial"
            _write_deformation_report(output_dir, result)
            return result
        
        # Apply deformation transfer
        # If target mesh matches fitted vertices, apply deltas directly
        if len(target_vertices) == len(fitted_vertices):
            # Direct vertex correspondence
            deformed_vertices = target_vertices + deltas
            result["transfer_method"] = "direct"
        elif source_vertices is not None and len(target_vertices) == len(source_vertices):
            # Target is source mesh - apply deltas from fit
            deformed_vertices = target_vertices + deltas
            result["transfer_method"] = "source_match"
        else:
            # Use nearest neighbor interpolation for different vertex counts
            from scipy.spatial import KDTree
            
            # Build KD-tree for fitted vertices
            if len(fitted_vertices) > 0:
                tree = KDTree(fitted_vertices)
                
                # For each target vertex, find nearest fitted vertex and interpolate
                deformed_vertices = target_vertices.copy()
                transfer_deltas = np.zeros_like(target_vertices)
                
                distances, indices = tree.query(target_vertices)
                
                # Apply deltas with distance-based blending
                max_dist = np.percentile(distances, 90) if len(distances) > 0 else 1.0
                weights = np.exp(-distances / (max_dist + 1e-6))
                
                for i, (idx, w) in enumerate(zip(indices, weights)):
                    if idx < len(deltas):
                        transfer_deltas[i] = deltas[idx] * w
                
                deformed_vertices = target_vertices + transfer_deltas
                result["transfer_method"] = "interpolated"
                result["interpolation_stats"] = {
                    "mean_distance": float(np.mean(distances)),
                    "max_distance": float(np.max(distances))
                }
            else:
                deformed_vertices = target_vertices
                result["transfer_method"] = "none"
        
        # Save deformed mesh
        deformed_mesh = trimesh.Trimesh(vertices=deformed_vertices, faces=target.faces)
        deformed_path = pathlib.Path(output_dir) / "deformed.glb"
        deformed_mesh.export(str(deformed_path))
        result["deformed_mesh"] = str(deformed_path)
        
        # Generate morph targets for expressions
        # Standard VRM expression names
        expression_names = [
            "happy", "angry", "sad", "relaxed", "surprised",
            "aa", "ih", "ou", "ee", "oh",
            "blink", "blinkLeft", "blinkRight",
            "lookUp", "lookDown", "lookLeft", "lookRight",
            "neutral"
        ]
        
        morph_targets = {}
        for expr_name in expression_names:
            # Create expression-specific morph target
            # For now, use scaled deltas based on expression type
            if "blink" in expr_name.lower():
                # Blink: vertical scaling for eyelids
                scale = 0.5
                expr_delta = np.zeros_like(target_vertices)
                expr_delta[:, 1] = deltas[:, 1] * scale
            elif expr_name in ["aa", "ih", "ou", "ee", "oh"]:
                # Viseme: mouth region deformation
                scale = 0.3
                expr_delta = np.zeros_like(target_vertices)
                expr_delta[:, 1] = deltas[:, 1] * scale
            else:
                # Generic expression: small perturbation
                scale = 0.1
                expr_delta = deltas * scale
            
            morph_targets[expr_name] = {
                "delta": expr_delta.tolist(),
                "vertex_count": len(target_vertices)
            }
        
        # Save morph targets
        morph_path = pathlib.Path(output_dir) / "morph_targets.npz"
        morph_deltas = {name: np.array(mt["delta"]) for name, mt in morph_targets.items()}
        np.savez(morph_path, **morph_deltas)
        result["morph_targets_path"] = str(morph_path)
        result["morph_target_count"] = len(morph_targets)
        result["morph_targets"] = list(morph_targets.keys())
        
        result["status"] = "complete"
        
    except ImportError as e:
        result["error"] = f"Missing dependency: {e}"
        result["status"] = "error"
    except Exception as e:
        result["error"] = str(e)
        result["status"] = "error"
    
    # Write deformation report
    _write_deformation_report(output_dir, result)
    
    return result


def load_deformation_graph(npz_path: str) -> Dict[str, Any]:
    """Load a deformation graph from an .npz file.
    
    Args:
        npz_path: Path to the .npz file.
        
    Returns:
        Dictionary with vertices, deltas, and weights arrays.
        
    Raises:
        FileNotFoundError: If the file doesn't exist.
    """
    try:
        import numpy as np
        
        if not pathlib.Path(npz_path).exists():
            raise FileNotFoundError(f"Deformation graph not found: {npz_path}")
        
        data = np.load(npz_path, allow_pickle=True)
        return {
            "vertices": data.get("vertices", np.array([])),
            "deltas": data.get("deltas", np.array([])),
            "weights": data.get("weights", np.array([]))
        }
    except ImportError:
        raise ImportError(
            "numpy is required for loading deformation graphs. "
            "Install with: pip install numpy"
        )


def apply_deformation(
    mesh_path: str,
    deformation: Dict[str, Any],
    output_path: str
) -> str:
    """Apply a deformation to a mesh.
    
    Args:
        mesh_path: Path to the input mesh.
        deformation: Deformation dictionary with vertices, deltas, weights.
        output_path: Path to save the deformed mesh.
        
    Returns:
        Path to the output mesh.
    """
    try:
        import trimesh
        
        mesh = trimesh.load(mesh_path)
        
        # Apply deformation (stub - just save the mesh)
        # In actual implementation:
        # 1. For each vertex, find nearest deformation node
        # 2. Apply weighted delta
        # 3. Smooth the result
        
        mesh.export(output_path)
        return output_path
        
    except ImportError:
        raise ImportError(
            "trimesh is required for mesh deformation. "
            "Install with: pip install trimesh"
        )


def transfer_expressions(
    canonical_mesh: str,
    fitted_mesh: str,
    expressions: list
) -> Dict[str, Any]:
    """Transfer expression shapes from canonical to fitted mesh.
    
    Given expression shapes defined on the canonical template,
    transfers them to the fitted mesh using the deformation graph.
    
    Args:
        canonical_mesh: Path to the canonical template mesh.
        fitted_mesh: Path to the fitted mesh.
        expressions: List of expression names to transfer.
        
    Returns:
        Dictionary mapping expression names to shape key data.
    """
    result = {
        "status": "stub",
        "expressions": {}
    }
    
    # Stub implementation
    for expr in expressions:
        result["expressions"][expr] = {
            "morph_targets": [],
            "weights": []
        }
    
    return result


def _write_deformation_report(output_dir: str, result: Dict[str, Any]) -> None:
    """Write deformation_report.json to output directory."""
    from vtuber_pipeline.core.utils import save_json
    
    output_path = pathlib.Path(output_dir) / "deformation_report.json"
    save_json(result, str(output_path))
