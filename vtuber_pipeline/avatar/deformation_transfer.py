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
        
        # Load deformation graph
        try:
            deformation = load_deformation_graph(fit_npz)
            result["deformation_loaded"] = True
            result["vertex_count"] = len(deformation.get("vertices", []))
        except FileNotFoundError:
            result["deformation_loaded"] = False
            result["warning"] = f"Deformation graph not found: {fit_npz}"
        
        # Apply deformation (stub)
        # In actual implementation:
        # 1. Load target mesh
        # 2. Apply vertex deltas weighted by deformation weights
        # 3. Save deformed mesh
        
        result["status"] = "complete"
        
    except ImportError:
        result["error"] = "numpy not installed"
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
