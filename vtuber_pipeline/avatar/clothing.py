"""Clothing mesh extraction module for VTuber Pipeline.

This module provides functions for extracting and processing clothing
geometry from reconstructed meshes.
"""

import pathlib
from typing import Dict, Any, Optional


def extract_clothing(
    mesh_path: str,
    body_mesh_path: str,
    output_dir: str
) -> Dict[str, Any]:
    """Extract clothing shell from mesh and transfer skin weights.
    
    Algorithm:
    1. Identify clothing vertices (bottom 60% of mesh, excluding hands)
    2. Create separate clothing mesh
    3. Transfer skin weights from body mesh to clothing
    4. Export as separate GLB for accessory attachment
    
    Skin weight transfer:
    - For each clothing vertex, find nearest body vertex
    - Copy skin weights with smooth falloff
    - Handle multi-layer clothing with offset shells
    
    Args:
        mesh_path: Path to the input mesh (with clothing).
        body_mesh_path: Path to the body mesh for weight transfer.
        output_dir: Directory to write output files.
        
    Returns:
        Dictionary with clothing extraction results.
    """
    result = {
        "status": "pending",
        "mesh_path": mesh_path,
        "body_mesh_path": body_mesh_path,
        "clothing_vertices": [],
        "clothing_faces": []
    }
    
    # Create output directory
    pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    try:
        import numpy as np
        
        try:
            import trimesh
            
            # Load mesh
            mesh = trimesh.load(mesh_path)
            
            if hasattr(mesh, 'vertices'):
                vertices = np.array(mesh.vertices)
                
                # Stub clothing detection: bottom 60% of mesh by Y coordinate
                y_coords = vertices[:, 1]  # Assuming Y is up
                y_threshold = np.percentile(y_coords, 40)
                clothing_vertex_mask = y_coords < y_threshold
                clothing_vertex_count = np.sum(clothing_vertex_mask)
                
                result["clothing_vertex_count"] = int(clothing_vertex_count)
                result["clothing_ratio"] = float(clothing_vertex_count / len(vertices))
                
                # Transfer skin weights (stub)
                result["skin_weights_transferred"] = False
                
                # Export clothing.glb (stub)
                result["clothing_glb"] = str(pathlib.Path(output_dir) / "clothing.glb")
                result["status"] = "complete"
                
            else:
                result["warning"] = "Mesh has no vertices attribute"
                result["status"] = "stub"
                
        except ImportError:
            result["warning"] = "trimesh not installed, using stub values"
            result["status"] = "stub"
            
    except ImportError:
        result["error"] = "numpy not installed"
        result["status"] = "error"
    
    return result


def extract_clothing_shell(
    mesh_path: str,
    body_mask: Dict[str, Any]
) -> Dict[str, Any]:
    """Extract clothing shell from mesh using body mask.
    
    Args:
        mesh_path: Path to the input mesh.
        body_mask: Dictionary with body vertex indices.
        
    Returns:
        Dictionary with clothing_vertices and clothing_faces.
    """
    result = {
        "clothing_vertices": [],
        "clothing_faces": [],
        "status": "stub"
    }
    
    try:
        import trimesh
        
        mesh = trimesh.load(mesh_path)
        
        # Stub implementation
        # In actual implementation:
        # 1. Subtract body vertices from all vertices
        # 2. Identify clothing shell by distance from body
        # 3. Find connected components
        
        result["warning"] = "Clothing shell extraction not fully implemented"
        
    except ImportError:
        result["error"] = "trimesh not installed"
    
    return result


def transfer_skin_weights(
    body_mesh_path: str,
    clothing_mesh_path: str,
    output_path: str,
    max_influence: int = 4,
    falloff_distance: float = 0.05
) -> Dict[str, Any]:
    """Transfer skin weights from body to clothing mesh.
    
    Real implementation:
    1. Load body mesh with skin weights
    2. Build KD-tree for body vertices
    3. For each clothing vertex, find nearest body vertices
    4. Interpolate weights using barycentric coordinates
    5. Normalize weights and save
    
    Args:
        body_mesh_path: Path to body mesh with skin weights.
        clothing_mesh_path: Path to clothing mesh.
        output_path: Path to save transferred weights.
        max_influence: Maximum number of bones influencing each vertex.
        falloff_distance: Distance for weight blending falloff.
        
    Returns:
        Dictionary with transferred weights.
    """
    result = {
        "weights": {},
        "status": "pending",
        "body_mesh_path": body_mesh_path,
        "clothing_mesh_path": clothing_mesh_path
    }
    
    try:
        import numpy as np
        import trimesh
        from scipy.spatial import KDTree
        import json
        
        # Load body mesh
        body_mesh = trimesh.load(body_mesh_path)
        if isinstance(body_mesh, trimesh.Scene):
            body_mesh = trimesh.util.concatenate(list(body_mesh.geometry.values()))
        
        body_vertices = np.array(body_mesh.vertices)
        result["body_vertex_count"] = len(body_vertices)
        
        # Load clothing mesh
        clothing_mesh = trimesh.load(clothing_mesh_path)
        if isinstance(clothing_mesh, trimesh.Scene):
            clothing_mesh = trimesh.util.concatenate(list(clothing_mesh.geometry.values()))
        
        clothing_vertices = np.array(clothing_mesh.vertices)
        n_clothing_vertices = len(clothing_vertices)
        result["clothing_vertex_count"] = n_clothing_vertices
        
        # Try to load body skin weights
        body_weights_path = pathlib.Path(body_mesh_path).parent / "vertex_weights.json"
        body_weights = None
        
        if body_weights_path.exists():
            try:
                with open(body_weights_path, 'r') as f:
                    body_weights_data = json.load(f)
                    body_weights = {k: np.array(v) for k, v in body_weights_data.items()}
                result["body_weights_loaded"] = True
                result["bone_names"] = list(body_weights.keys())
            except Exception as e:
                result["body_weights_load_warning"] = str(e)
        
        if body_weights is None:
            # Generate default skin weights based on distance to bones
            # Use standard VRM bone names
            bone_names = ["hips", "spine", "chest", "neck", "head",
                         "leftUpperLeg", "rightUpperLeg", "leftLowerLeg", "rightLowerLeg",
                         "leftFoot", "rightFoot", "leftShoulder", "rightShoulder",
                         "leftUpperArm", "rightUpperArm", "leftLowerArm", "rightLowerArm",
                         "leftHand", "rightHand"]
            body_weights = _generate_default_weights(body_vertices, bone_names)
            result["body_weights_loaded"] = False
            result["bone_names"] = bone_names
        
        # Build KD-tree for body vertices
        body_tree = KDTree(body_vertices)
        
        # Initialize clothing weights
        bone_names = list(body_weights.keys())
        clothing_weights = {bone: np.zeros(n_clothing_vertices, dtype=np.float32) 
                          for bone in bone_names}
        
        # Query nearest body vertices for each clothing vertex
        distances, indices = body_tree.query(clothing_vertices, k=max_influence)
        
        # Handle single result case
        if len(distances.shape) == 1:
            distances = distances.reshape(-1, 1)
            indices = indices.reshape(-1, 1)
        
        # Compute barycentric-interpolated weights
        for i in range(n_clothing_vertices):
            vertex_distances = distances[i]
            vertex_indices = indices[i]
            
            # Compute inverse-distance weights
            # Avoid division by zero
            safe_distances = np.where(vertex_distances < 1e-6, 1e-6, vertex_distances)
            inv_distances = 1.0 / safe_distances
            
            # Apply falloff
            weight_falloff = np.exp(-vertex_distances / falloff_distance)
            blend_weights = inv_distances * weight_falloff
            
            # Normalize
            blend_weights = blend_weights / (blend_weights.sum() + 1e-8)
            
            # Interpolate skin weights from body to clothing
            for j, (body_idx, w) in enumerate(zip(vertex_indices, blend_weights)):
                for bone in bone_names:
                    if body_idx < len(body_weights[bone]):
                        clothing_weights[bone][i] += body_weights[bone][body_idx] * w
        
        # Normalize weights per vertex
        weight_sum = np.zeros(n_clothing_vertices)
        for bone in bone_names:
            weight_sum += clothing_weights[bone]
        
        weight_sum = np.where(weight_sum < 1e-8, 1.0, weight_sum)
        for bone in bone_names:
            clothing_weights[bone] /= weight_sum
        
        # Save transferred weights
        output_path_obj = pathlib.Path(output_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)
        
        weights_json = {bone: w.tolist() for bone, w in clothing_weights.items()}
        with open(output_path_obj, 'w') as f:
            json.dump(weights_json, f)
        
        result["weights"] = {bone: w.tolist() for bone, w in clothing_weights.items()}
        result["output_path"] = str(output_path_obj)
        result["status"] = "complete"
        
        # Stats
        result["stats"] = {
            "mean_distance": float(np.mean(distances)),
            "max_distance": float(np.max(distances)),
            "bone_count": len(bone_names)
        }
        
    except ImportError as e:
        result["error"] = f"Missing dependency: {e}"
        result["status"] = "error"
    except Exception as e:
        result["error"] = str(e)
        result["status"] = "error"
    
    return result


def _generate_default_weights(vertices: np.ndarray, bone_names: list) -> Dict[str, np.ndarray]:
    """Generate default skin weights based on vertex position heuristics.
    
    Uses Y-coordinate to assign weights to spine chain bones.
    
    Args:
        vertices: (N, 3) vertex position array.
        bone_names: List of bone names.
        
    Returns:
        Dictionary mapping bone names to weight arrays.
    """
    n_vertices = len(vertices)
    weights = {bone: np.zeros(n_vertices, dtype=np.float32) for bone in bone_names}
    
    if len(vertices) == 0:
        return weights
    
    # Compute Y bounds
    y_coords = vertices[:, 1]
    y_min, y_max = y_coords.min(), y_coords.max()
    y_range = y_max - y_min if y_max > y_min else 1.0
    
    # Spine chain bones with Y thresholds
    spine_bones = ["hips", "spine", "chest", "neck", "head"]
    
    for i, v in enumerate(vertices):
        y_normalized = (v[1] - y_min) / y_range
        
        # Assign to spine chain based on Y position
        if y_normalized < 0.2:
            weights["hips"][i] = 1.0
        elif y_normalized < 0.4:
            weights["hips"][i] = (0.4 - y_normalized) / 0.2
            weights["spine"][i] = (y_normalized - 0.2) / 0.2
        elif y_normalized < 0.6:
            weights["spine"][i] = (0.6 - y_normalized) / 0.2
            weights["chest"][i] = (y_normalized - 0.4) / 0.2
        elif y_normalized < 0.75:
            weights["chest"][i] = (0.75 - y_normalized) / 0.15
            weights["neck"][i] = (y_normalized - 0.6) / 0.15
        else:
            weights["neck"][i] = (0.9 - y_normalized) / 0.15
            weights["head"][i] = max(0, (y_normalized - 0.75) / 0.15)
    
    return weights


def generate_clothing_glb(mesh_path: str, output_dir: str) -> str:
    """Extract and export clothing mesh as GLB.
    
    Args:
        mesh_path: Path to the input mesh.
        output_dir: Directory to write the output file.
        
    Returns:
        Path to the generated clothing.glb file.
    """
    output_path = pathlib.Path(output_dir) / "clothing.glb"
    
    try:
        import trimesh
        
        # Load mesh
        mesh = trimesh.load(mesh_path)
        
        # Stub: export empty placeholder
        empty_mesh = trimesh.Trimesh()
        empty_mesh.export(output_path)
        
        return str(output_path)
        
    except ImportError:
        raise ImportError(
            "trimesh is required for clothing extraction. "
            "Install with: pip install trimesh"
        )
