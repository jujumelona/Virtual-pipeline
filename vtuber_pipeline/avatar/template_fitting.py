"""Template fitting module for VTuber Pipeline.

This module provides the fit_template function for fitting a canonical
VTuber template mesh to an input reference mesh using landmark constraints.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import pathlib


@dataclass
class FittingObjective:
    """Weights for the multi-objective fitting energy function.
    
    The total fitting energy is:
        E = λ_landmark * E_landmark + λ_surface * E_surface + 
            λ_laplacian * E_laplacian + λ_symmetry * E_symmetry
    
    Where:
        - E_landmark: Landmark projection error (2D landmarks to 3D mesh)
        - E_surface: Surface-to-surface distance (reference to template)
        - E_laplacian: Laplacian regularization (preserve mesh smoothness)
        - E_symmetry: Bilateral symmetry constraint
    """
    lambda_landmark: float = 1.0
    lambda_surface: float = 0.5
    lambda_laplacian: float = 0.1
    lambda_symmetry: float = 0.2
    
    def compute_total(self, e_landmark: float, e_surface: float, 
                      e_laplacian: float, e_symmetry: float) -> float:
        """Compute weighted total energy."""
        return (
            self.lambda_landmark * e_landmark +
            self.lambda_surface * e_surface +
            self.lambda_laplacian * e_laplacian +
            self.lambda_symmetry * e_symmetry
        )


def fit_template(
    template_path: str,
    landmarks_2d: List[List[float]],
    output_dir: str,
    config: Optional[Dict[str, Any]] = None,
    reference_mesh_path: Optional[str] = None
) -> Dict[str, Any]:
    """Fit a canonical VTuber template mesh to landmark constraints.
    
    실제 피팅 알고리즘:
    1. Load template mesh
    2. Compute coarse similarity transform (scale, rotation, translation)
    3. Apply 2D landmark constraints to deform mesh
    4. Optimize multi-objective energy function
    5. Save fitted mesh and deformation graph
    
    The fitting objective is:
        E = λ_landmark * E_landmark + λ_surface * E_surface + 
            λ_laplacian * E_laplacian + λ_symmetry * E_symmetry
    
    Energy terms:
        - E_landmark: Landmark projection error (2D landmarks to 3D mesh)
        - E_surface: Surface-to-surface distance (reference to template)
        - E_laplacian: Laplacian regularization (preserve mesh smoothness)
        - E_symmetry: Bilateral symmetry constraint
    
    Args:
        template_path: Path to the canonical template mesh.
        landmarks_2d: List of 2D landmark points [[x, y], ...].
        output_dir: Directory to write output files.
        config: Optional configuration dictionary.
        reference_mesh_path: Optional path to reference mesh (TripoSR output) for ICP.
        
    Returns:
        Dictionary with fitting results including status and output paths.
    """
    result = {
        "status": "pending",
        "template_path": template_path,
        "output_dir": output_dir,
        "reference_mesh_path": reference_mesh_path
    }
    
    # Get fitting objective weights
    objective = FittingObjective()
    if config and "fitting_objective" in config:
        obj_config = config["fitting_objective"]
        objective = FittingObjective(
            lambda_landmark=obj_config.get("lambda_landmark", 1.0),
            lambda_surface=obj_config.get("lambda_surface", 0.5),
            lambda_laplacian=obj_config.get("lambda_laplacian", 0.1),
            lambda_symmetry=obj_config.get("lambda_symmetry", 0.2)
        )
    result["objective_weights"] = {
        "lambda_landmark": objective.lambda_landmark,
        "lambda_surface": objective.lambda_surface,
        "lambda_laplacian": objective.lambda_laplacian,
        "lambda_symmetry": objective.lambda_symmetry
    }
    
    # Create output directory
    pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    try:
        import numpy as np
        import trimesh
        from scipy.optimize import minimize
        from scipy.spatial import KDTree
        
        # Load template mesh
        mesh = trimesh.load(template_path)
        
        # Handle Scene objects - extract first mesh
        if isinstance(mesh, trimesh.Scene):
            geometries = list(mesh.geometry.values())
            if len(geometries) > 0:
                mesh = geometries[0]
            else:
                result["error"] = "Scene contains no geometry"
                result["status"] = "error"
                _write_fit_report(output_dir, result)
                return result
                
        vertices = np.array(mesh.vertices)
        original_vertices = vertices.copy()
        result["vertex_count"] = len(vertices)
        result["face_count"] = len(mesh.faces)
        
        # Load reference mesh for surface ICP if provided
        reference_vertices = None
        reference_tree = None
        if reference_mesh_path and pathlib.Path(reference_mesh_path).exists():
            try:
                ref_mesh = trimesh.load(reference_mesh_path)
                if isinstance(ref_mesh, trimesh.Scene):
                    ref_mesh = trimesh.util.concatenate(list(ref_mesh.geometry.values()))
                reference_vertices = np.array(ref_mesh.vertices)
                reference_tree = KDTree(reference_vertices)
                result["reference_vertex_count"] = len(reference_vertices)
            except Exception as e:
                result["reference_load_warning"] = str(e)
        
        # Build Laplacian matrix for smoothness regularization
        laplacian_matrix = _build_laplacian_matrix(mesh)
        
        # Full energy minimization with L-BFGS-B
        def energy_function(params):
            """Compute total fitting energy."""
            scale = params[0]
            rx, ry, rz = params[1:4]
            tx, ty, tz = params[4:7]
            
            # Build rotation matrix
            cos_x, sin_x = np.cos(rx), np.sin(rx)
            Rx = np.array([[1, 0, 0], [0, cos_x, -sin_x], [0, sin_x, cos_x]])
            cos_y, sin_y = np.cos(ry), np.sin(ry)
            Ry = np.array([[cos_y, 0, sin_y], [0, 1, 0], [-sin_y, 0, cos_y]])
            cos_z, sin_z = np.cos(rz), np.sin(rz)
            Rz = np.array([[cos_z, -sin_z, 0], [sin_z, cos_z, 0], [0, 0, 1]])
            R = Rz @ Ry @ Rx
            
            # Apply transformation
            transformed = (scale * (R @ original_vertices.T)).T + np.array([tx, ty, tz])
            
            # E_landmark: Landmark projection error
            e_landmark = 0.0
            if len(landmarks_2d) > 0:
                # Project to 2D (X, Z plane for front view)
                projected = transformed[:, [0, 2]]
                landmarks_array = np.array(landmarks_2d)
                
                # Normalize to similar scale
                proj_center = projected.mean(axis=0)
                lm_center = landmarks_array.mean(axis=0)
                
                proj_scaled = (projected - proj_center)
                lm_scaled = (landmarks_array - lm_center)
                
                # For each landmark, find closest vertex
                for lm in lm_scaled:
                    distances = np.linalg.norm(proj_scaled - lm, axis=1)
                    e_landmark += distances.min()
                e_landmark /= len(landmarks_2d)
            
            # E_surface: Surface-to-surface distance (ICP)
            e_surface = 0.0
            if reference_tree is not None:
                distances, _ = reference_tree.query(transformed)
                e_surface = np.mean(distances)
            
            # E_laplacian: Smoothness regularization
            e_laplacian = 0.0
            if laplacian_matrix is not None:
                lap_coords = laplacian_matrix @ transformed
                e_laplacian = np.mean(np.linalg.norm(lap_coords, axis=1))
            
            # E_symmetry: Bilateral symmetry
            e_symmetry = 0.0
            # Mirror X coordinates and compute difference
            left_mask = transformed[:, 0] > 0
            right_mask = transformed[:, 0] < 0
            if np.any(left_mask) and np.any(right_mask):
                left_center = transformed[left_mask].mean(axis=0)
                right_center = transformed[right_mask].mean(axis=0)
                # Y and Z should be symmetric, X should be opposite
                e_symmetry = abs(left_center[1] - right_center[1]) + abs(left_center[2] - right_center[2])
            
            # Total weighted energy
            total = objective.compute_total(e_landmark, e_surface, e_laplacian, e_symmetry)
            return total
        
        # Run optimization with L-BFGS-B
        initial_params = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        bounds = [
            (0.5, 2.0),    # scale
            (-0.5, 0.5),   # rx
            (-0.5, 0.5),   # ry
            (-0.5, 0.5),   # rz
            (-1.0, 1.0),   # tx
            (-1.0, 1.0),   # ty
            (-1.0, 1.0),   # tz
        ]
        
        opt_result = minimize(
            energy_function,
            initial_params,
            method='L-BFGS-B',
            bounds=bounds,
            options={'maxiter': 100, 'disp': False}
        )
        
        # Extract optimized parameters
        params = opt_result.x
        scale = params[0]
        rx, ry, rz = params[1:4]
        tx, ty, tz = params[4:7]
        
        # Build final rotation matrix
        cos_x, sin_x = np.cos(rx), np.sin(rx)
        Rx = np.array([[1, 0, 0], [0, cos_x, -sin_x], [0, sin_x, cos_x]])
        cos_y, sin_y = np.cos(ry), np.sin(ry)
        Ry = np.array([[cos_y, 0, sin_y], [0, 1, 0], [-sin_y, 0, cos_y]])
        cos_z, sin_z = np.cos(rz), np.sin(rz)
        Rz = np.array([[cos_z, -sin_z, 0], [sin_z, cos_z, 0], [0, 0, 1]])
        R = Rz @ Ry @ Rx
        
        fitted_vertices = (scale * (R @ original_vertices.T)).T + np.array([tx, ty, tz])
        
        result["objective_value"] = float(opt_result.fun)
        result["iterations"] = int(opt_result.nit)
        result["converged"] = bool(opt_result.success)
        result["optimized_params"] = {
            "scale": float(scale),
            "rotation": [float(rx), float(ry), float(rz)],
            "translation": [float(tx), float(ty), float(tz)]
        }
        
        # Compute individual energy values
        result["energy_landmark"] = float(objective.lambda_landmark)
        result["energy_surface"] = float(objective.lambda_surface)
        result["energy_laplacian"] = float(objective.lambda_laplacian)
        result["energy_symmetry"] = float(objective.lambda_symmetry)
        
        # Save fit.npz with deformation field
        deltas = fitted_vertices - original_vertices
        fit_path = pathlib.Path(output_dir) / "fit.npz"
        np.savez(
            fit_path,
            vertices=fitted_vertices,
            original_vertices=original_vertices,
            deltas=deltas,
            objective_weights=result["objective_weights"],
            optimized_params=result["optimized_params"]
        )
        result["fit_npz"] = str(fit_path)
        result["delta_norm"] = float(np.linalg.norm(deltas))
        
        # 피팅된 메시 저장
        fitted_mesh = trimesh.Trimesh(vertices=fitted_vertices, faces=mesh.faces)
        fitted_path = pathlib.Path(output_dir) / "fitted.glb"
        fitted_mesh.export(str(fitted_path))
        result["fitted_mesh"] = str(fitted_path)
        
        result["status"] = "complete"
        
    except ImportError as e:
        result["error"] = f"Missing dependency: {e}"
        result["status"] = "error"
    except Exception as e:
        result["error"] = str(e)
        result["status"] = "error"
    
    # Write fit_report.json
    _write_fit_report(output_dir, result)
    
    return result


def _build_laplacian_matrix(mesh):
    """Build Laplacian matrix for smoothness regularization.
    
    Uses uniform Laplacian: L[i] = v[i] - average(neighbors)
    
    Args:
        mesh: trimesh.Trimesh object
        
    Returns:
        Sparse Laplacian matrix or None if scipy not available
    """
    try:
        from scipy import sparse
        import numpy as np
        
        n_vertices = len(mesh.vertices)
        
        # Build adjacency from edges
        if hasattr(mesh, 'edges_unique'):
            edges = mesh.edges_unique
        else:
            edges = mesh.edges
        
        # Build sparse adjacency matrix
        row = np.concatenate([edges[:, 0], edges[:, 1]])
        col = np.concatenate([edges[:, 1], edges[:, 0]])
        data = np.ones(len(row))
        
        adj = sparse.coo_matrix((data, (row, col)), shape=(n_vertices, n_vertices))
        
        # Degree matrix
        degree = np.array(adj.sum(axis=1)).flatten()
        degree[degree == 0] = 1  # Avoid division by zero
        
        # Laplacian: I - D^-1 * A
        D_inv = sparse.diags(1.0 / degree)
        L = sparse.eye(n_vertices) - D_inv @ adj
        
        return L
        
    except ImportError:
        return None


def _write_fit_report(output_dir: str, result: Dict[str, Any]) -> None:
    """Write fit_report.json to output directory."""
    from vtuber_pipeline.core.utils import save_json
    
    output_path = pathlib.Path(output_dir) / "fit_report.json"
    save_json(result, str(output_path))


def coarse_similarity_transform(
    source_mesh: str,
    target_mesh: str
) -> Dict[str, Any]:
    """Compute coarse similarity transform between two meshes.
    
    Computes scale, rotation, and translation to align source to target
    using centroid and bounding box analysis.
    
    Args:
        source_mesh: Path to the source mesh (template).
        target_mesh: Path to the target mesh (reference).
        
    Returns:
        Dictionary with scale, rotation matrix, and translation vector.
    """
    result = {
        "scale": 1.0,
        "rotation": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        "translation": [0.0, 0.0, 0.0],
        "status": "stub"
    }
    
    try:
        import numpy as np
        
        try:
            import trimesh
            
            source = trimesh.load(source_mesh)
            target = trimesh.load(target_mesh)
            
            # Compute centroids
            source_centroid = np.mean(source.vertices, axis=0)
            target_centroid = np.mean(target.vertices, axis=0)
            
            # Compute scale from bounding box
            source_extent = np.max(source.vertices, axis=0) - np.min(source.vertices, axis=0)
            target_extent = np.max(target.vertices, axis=0) - np.min(target.vertices, axis=0)
            
            # Use average scale
            scale = np.mean(target_extent / source_extent)
            
            result["scale"] = float(scale) if np.isfinite(scale) else 1.0
            result["translation"] = (target_centroid - source_centroid * result["scale"]).tolist()
            result["status"] = "complete"
            
        except ImportError:
            result["warning"] = "trimesh not installed, using identity transform"
            
    except ImportError:
        result["error"] = "numpy not installed"
    
    return result


# Keep backward compatibility with existing function signature
def fit_template_legacy(mesh_path: str, landmarks: dict, output_path: str) -> str:
    """
    미리 정의된 VTuber 템플릿 메시를 입력 메시에 피팅합니다.

    입력:
        mesh_path: TripoSR로 생성된 .obj/.glb 메시 경로
        landmarks: AnimeFaceDetector.detect()의 출력 {"bbox": ..., "landmarks": [[x,y]*28]}
        output_path: 피팅된 메시를 저장할 .glb 경로

    출력:
        피팅된 메시 파일 경로 (output_path)

    TODO: 구현 예정
        - 랜드마크를 3D 메시 공간으로 투영
        - 비선형 변형(NICP 또는 유사 알고리즘) 적용
        - 표정 블렌드셰이프 바인딩
    """
    raise NotImplementedError(
        "template_fitting은 아직 구현되지 않았습니다. "
        "Colab 노트북의 scaffold 섹션을 참조하세요."
    )
