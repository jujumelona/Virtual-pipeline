"""Template fitting module for VTuber Pipeline.

This module provides the fit_template function for fitting a canonical
VTuber template mesh to an input reference mesh using landmark constraints.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple
import pathlib
import numpy as np


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
        if reference_mesh_path:
            reference_path = pathlib.Path(reference_mesh_path)
            if not reference_path.is_file():
                raise FileNotFoundError(
                    f"Reference mesh is required for production fitting: {reference_mesh_path}"
                )
            ref_mesh = trimesh.load(reference_mesh_path)
            if isinstance(ref_mesh, trimesh.Scene):
                geometries = list(ref_mesh.geometry.values())
                if not geometries:
                    raise ValueError("Reference mesh scene contains no geometry")
                ref_mesh = trimesh.util.concatenate(geometries)
            reference_vertices = np.asarray(ref_mesh.vertices, dtype=float)
            if len(reference_vertices) == 0:
                raise ValueError("Reference mesh has no vertices")
            reference_tree = KDTree(reference_vertices)
            result["reference_vertex_count"] = len(reference_vertices)
        
        # Build Laplacian matrix for smoothness regularization
        laplacian_matrix = _build_laplacian_matrix(mesh)
        
        # Normalize image landmarks against an actual front-face projection.
        # Image coordinates are X-right/Y-down; mesh coordinates are X-right/Y-up.
        def face_candidate_indices(points):
            pts = np.asarray(points, dtype=float)
            pmin = pts.min(axis=0)
            pmax = pts.max(axis=0)
            height = max(float(pmax[1] - pmin[1]), 1e-8)
            head_mask = pts[:, 1] >= pmin[1] + 0.68 * height
            z_center = float((pmin[2] + pmax[2]) * 0.5)
            # Canonical VRM coordinates use +Z as the model's front.
            front_mask = (pts[:, 2] - z_center) >= 0.0
            indices = np.flatnonzero(head_mask & front_mask)
            if len(indices) < 16:
                indices = np.flatnonzero(head_mask)
            if len(indices) < 16:
                indices = np.arange(len(pts))
            return indices

        def normalize_landmarks_to_projection(projected, landmarks):
            projected = np.asarray(projected, dtype=float)
            lm = np.asarray(landmarks, dtype=float)
            if lm.ndim != 2 or lm.shape[1] < 2 or len(lm) == 0:
                return np.empty((0, 2), dtype=float)
            lm = lm[:, :2].copy()
            proj_center = projected.mean(axis=0)
            lm_center = lm.mean(axis=0)
            proj_centered = projected - proj_center
            lm_centered = lm - lm_center
            # Flip image Y-down into mesh Y-up before scale matching.
            lm_centered[:, 1] *= -1.0
            proj_scale = float(np.sqrt(np.mean(np.sum(proj_centered ** 2, axis=1))))
            lm_scale = float(np.sqrt(np.mean(np.sum(lm_centered ** 2, axis=1))))
            if proj_scale <= 1e-10 or lm_scale <= 1e-10:
                raise ValueError("degenerate landmark/projection scale")
            return lm_centered * (proj_scale / lm_scale) + proj_center

        def fit_region_weights(points):
            """Smoothly select head/central upper torso for reference fitting.

            Arms and lower body stay close to the canonical VRM rest pose.
            """
            pts = np.asarray(points, dtype=float)
            pmin = pts.min(axis=0)
            pmax = pts.max(axis=0)
            height = max(float(pmax[1] - pmin[1]), 1e-8)
            center_x = float((pmin[0] + pmax[0]) * 0.5)

            y_norm = (pts[:, 1] - pmin[1]) / height
            x_norm = np.abs(pts[:, 0] - center_x) / height

            # Vertical ramp: no surface fitting below mid torso.
            y_weight = np.clip((y_norm - 0.48) / 0.16, 0.0, 1.0)
            y_weight = y_weight * y_weight * (3.0 - 2.0 * y_weight)

            # Central-body ramp excludes T-pose arms while keeping head/torso.
            x_weight = np.clip((0.24 - x_norm) / 0.08, 0.0, 1.0)
            x_weight = x_weight * x_weight * (3.0 - 2.0 * x_weight)

            return y_weight * x_weight

        # Full energy minimization with a 7-DOF rigid phase.
        def energy_function(params):
            scale = params[0]
            rx, ry, rz = params[1:4]
            tx, ty, tz = params[4:7]

            cos_x, sin_x = np.cos(rx), np.sin(rx)
            Rx = np.array([[1, 0, 0], [0, cos_x, -sin_x], [0, sin_x, cos_x]])
            cos_y, sin_y = np.cos(ry), np.sin(ry)
            Ry = np.array([[cos_y, 0, sin_y], [0, 1, 0], [-sin_y, 0, cos_y]])
            cos_z, sin_z = np.cos(rz), np.sin(rz)
            Rz = np.array([[cos_z, -sin_z, 0], [sin_z, cos_z, 0], [0, 0, 1]])
            R = Rz @ Ry @ Rx
            transformed = (scale * (R @ original_vertices.T)).T + np.array([tx, ty, tz])

            e_landmark = 0.0
            if len(landmarks_2d) > 0:
                face_idx = face_candidate_indices(transformed)
                projected = transformed[face_idx][:, [0, 1]]
                normalized_lm = normalize_landmarks_to_projection(projected, landmarks_2d)
                for lm in normalized_lm:
                    e_landmark += float(np.linalg.norm(projected - lm, axis=1).min())
                e_landmark /= max(len(normalized_lm), 1)

            e_surface = 0.0
            if reference_tree is not None:
                region = fit_region_weights(transformed)
                active = region > 1e-4
                if np.any(active):
                    surface_distances, _ = reference_tree.query(
                        transformed[active]
                    )
                    weights = region[active]
                    e_surface = float(
                        np.sum(surface_distances * weights)
                        / max(float(np.sum(weights)), 1e-8)
                    )

            e_laplacian = 0.0
            if laplacian_matrix is not None:
                lap_coords = laplacian_matrix @ transformed
                e_laplacian = float(np.mean(np.linalg.norm(lap_coords, axis=1)))

            e_symmetry = 0.0
            x_center = float(np.median(transformed[:, 0]))
            left_mask = transformed[:, 0] > x_center
            right_mask = transformed[:, 0] < x_center
            if np.any(left_mask) and np.any(right_mask):
                left_center = transformed[left_mask].mean(axis=0)
                right_center = transformed[right_mask].mean(axis=0)
                e_symmetry = float(
                    abs(left_center[1] - right_center[1]) +
                    abs(left_center[2] - right_center[2])
                )

            return objective.compute_total(
                e_landmark, e_surface, e_laplacian, e_symmetry
            )

        # PHASE 1: initialize from actual template/reference extents instead of
        # assuming both meshes already share units.
        coarse = coarse_similarity_transform(template_path, reference_mesh_path) if reference_mesh_path else {
            "status": "complete", "scale": 1.0, "translation": [0.0, 0.0, 0.0]
        }
        if coarse.get("status") != "complete":
            raise RuntimeError(coarse.get("error", "coarse similarity alignment failed"))
        coarse_scale = float(coarse["scale"])
        coarse_translation = np.asarray(coarse["translation"], dtype=float)
        reference_extent = (
            np.ptp(reference_vertices, axis=0)
            if reference_vertices is not None
            else np.ptp(original_vertices, axis=0) * coarse_scale
        )
        max_extent = max(float(np.max(reference_extent)), 1e-3)

        initial_params = [
            coarse_scale, 0.0, 0.0, 0.0,
            float(coarse_translation[0]),
            float(coarse_translation[1]),
            float(coarse_translation[2]),
        ]
        bounds = [
            (max(coarse_scale * 0.25, 1e-6), coarse_scale * 4.0),
            (-0.5, 0.5),
            (-0.5, 0.5),
            (-0.5, 0.5),
            (coarse_translation[0] - 2.0 * max_extent, coarse_translation[0] + 2.0 * max_extent),
            (coarse_translation[1] - 2.0 * max_extent, coarse_translation[1] + 2.0 * max_extent),
            (coarse_translation[2] - 2.0 * max_extent, coarse_translation[2] + 2.0 * max_extent),
        ]

        opt_result = minimize(
            energy_function,
            initial_params,
            method="L-BFGS-B",
            bounds=bounds,
            options={"maxiter": 100},
        )
        if not np.all(np.isfinite(opt_result.x)):
            raise RuntimeError("rigid fitting produced non-finite parameters")
        if not bool(opt_result.success):
            raise RuntimeError(
                f"rigid fitting did not converge: {opt_result.message}"
            )

        params = opt_result.x
        scale = params[0]
        rx, ry, rz = params[1:4]
        tx, ty, tz = params[4:7]

        cos_x, sin_x = np.cos(rx), np.sin(rx)
        Rx = np.array([[1, 0, 0], [0, cos_x, -sin_x], [0, sin_x, cos_x]])
        cos_y, sin_y = np.cos(ry), np.sin(ry)
        Ry = np.array([[cos_y, 0, sin_y], [0, 1, 0], [-sin_y, 0, cos_y]])
        cos_z, sin_z = np.cos(rz), np.sin(rz)
        Rz = np.array([[cos_z, -sin_z, 0], [sin_z, cos_z, 0], [0, 0, 1]])
        R = Rz @ Ry @ Rx
        rigid_transformed = (scale * (R @ original_vertices.T)).T + np.array([tx, ty, tz])

        # PHASE 2: sparse deformation graph. Landmark constraints act on X/Y
        # independently, while reference-surface constraints act on all 3 axes.
        n_vertices = len(original_vertices)
        n_graph_nodes = min(200, n_vertices)
        graph_node_indices = select_deformation_graph_nodes(
            rigid_transformed, n_graph_nodes
        )
        graph_positions = rigid_transformed[graph_node_indices]
        n_graph = len(graph_node_indices)
        if n_graph < 2:
            raise RuntimeError("deformation graph has fewer than two nodes")
        result["deformation_graph_nodes"] = n_graph

        from scipy import sparse as sp
        from scipy.sparse.linalg import spsolve
        from scipy.spatial import cKDTree

        graph_tree = cKDTree(graph_positions)
        k_neighbors = min(6, n_graph - 1)
        _, neighbor_indices = graph_tree.query(
            graph_positions, k=k_neighbors + 1
        )

        row = []
        col = []
        data = []
        for i in range(n_graph):
            neighbors = np.atleast_1d(neighbor_indices[i])[1:]
            if len(neighbors) == 0:
                continue
            row.extend([i] * len(neighbors))
            col.extend([int(n) for n in neighbors])
            data.extend([-1.0 / len(neighbors)] * len(neighbors))
            row.append(i)
            col.append(i)
            data.append(1.0)
        L = sp.coo_matrix((data, (row, col)), shape=(n_graph, n_graph)).tocsr()
        LTL = L.T @ L

        graph_displacements = np.zeros((n_graph, 3), dtype=float)

        # Surface targets only affect the head/central upper torso. The
        # canonical T-pose arms and lower body receive a zero-displacement
        # preservation constraint instead.
        surface_weight = fit_region_weights(graph_positions)
        if reference_tree is not None and reference_vertices is not None:
            _, nearest_ref_idx = reference_tree.query(graph_positions)
            surface_delta = (
                reference_vertices[np.asarray(nearest_ref_idx, dtype=int)]
                - graph_positions
            )
        else:
            surface_delta = np.zeros((n_graph, 3), dtype=float)
        preserve_weight = 1.0 - surface_weight
        result["surface_fit_graph_nodes"] = int(
            np.count_nonzero(surface_weight > 0.1)
        )
        result["preserved_graph_nodes"] = int(
            np.count_nonzero(preserve_weight > 0.9)
        )

        # Landmark constraints are attached only to front/head graph nodes.
        C = None
        landmark_delta = None
        if len(landmarks_2d) > 0:
            face_local = face_candidate_indices(graph_positions)
            face_graph = graph_positions[face_local]
            projected_face = face_graph[:, [0, 1]]
            normalized_lm = normalize_landmarks_to_projection(
                projected_face, landmarks_2d
            )
            constraint_nodes = []
            landmark_delta = np.zeros((len(normalized_lm), 2), dtype=float)
            for i, lm in enumerate(normalized_lm):
                nearest_local = int(
                    np.argmin(np.linalg.norm(projected_face - lm, axis=1))
                )
                node_idx = int(face_local[nearest_local])
                constraint_nodes.append(node_idx)
                landmark_delta[i, 0] = lm[0] - graph_positions[node_idx, 0]
                landmark_delta[i, 1] = lm[1] - graph_positions[node_idx, 1]
            C = sp.coo_matrix(
                (
                    np.ones(len(constraint_nodes), dtype=float),
                    (np.arange(len(constraint_nodes)), constraint_nodes),
                ),
                shape=(len(constraint_nodes), n_graph),
            ).tocsr()

        lambda_surface = max(float(objective.lambda_surface), 1e-6)
        lambda_landmark = max(float(objective.lambda_landmark) * 10.0, 1e-6)
        lambda_preserve = max(lambda_surface * 8.0, 1.0)
        surface_diag = sp.diags(surface_weight, format="csr")
        preserve_diag = sp.diags(preserve_weight, format="csr")

        for dim in range(3):
            A = (
                LTL
                + lambda_surface * surface_diag
                + lambda_preserve * preserve_diag
            )
            b = lambda_surface * surface_weight * surface_delta[:, dim]
            if C is not None and dim in (0, 1):
                A = A + lambda_landmark * (C.T @ C)
                b = b + lambda_landmark * (C.T @ landmark_delta[:, dim])
            solved = spsolve(A.tocsr(), b)
            if not np.all(np.isfinite(solved)):
                raise RuntimeError(
                    f"non-rigid sparse solve produced non-finite values on axis {dim}"
                )
            graph_displacements[:, dim] = solved

        result["sparse_solve_success"] = True
        final_displacements = interpolate_displacements(
            rigid_transformed, graph_node_indices, graph_displacements
        )
        vertex_fit_weight = fit_region_weights(rigid_transformed)
        final_displacements *= vertex_fit_weight[:, None]
        fitted_vertices = rigid_transformed + final_displacements
        result["fitted_vertex_count"] = int(
            np.count_nonzero(vertex_fit_weight > 0.1)
        )
        result["preserved_vertex_count"] = int(
            np.count_nonzero(vertex_fit_weight <= 0.1)
        )
        result["graph_displacement_norm"] = float(np.linalg.norm(graph_displacements))
        result["final_displacement_norm"] = float(np.linalg.norm(final_displacements))

        result["nonrigid_method"] = "sparse_laplacian"
        
        # Sparse solve doesn't have iterations like L-BFGS-B, use rigid phase results
        # objective_value will be computed after delta_norm is available
        result["iterations"] = int(opt_result.nit)
        result["converged"] = bool(opt_result.success) and result.get("sparse_solve_success", False)
        result["optimized_params"] = {
            "scale": float(scale),
            "rotation": [float(rx), float(ry), float(rz)],
            "translation": [float(tx), float(ty), float(tz)]
        }
        
        # Compute actual final energy terms rather than reporting the lambdas.
        final_face_idx = face_candidate_indices(fitted_vertices)
        final_projected = fitted_vertices[final_face_idx][:, [0, 1]]
        final_landmarks = normalize_landmarks_to_projection(
            final_projected, landmarks_2d
        )
        if len(final_landmarks):
            result["energy_landmark"] = float(np.mean([
                np.linalg.norm(final_projected - lm, axis=1).min()
                for lm in final_landmarks
            ]))
        else:
            result["energy_landmark"] = 0.0

        if reference_tree is not None:
            final_region = fit_region_weights(fitted_vertices)
            active = final_region > 1e-4
            if np.any(active):
                final_surface_dist, _ = reference_tree.query(
                    fitted_vertices[active]
                )
                weights = final_region[active]
                result["energy_surface"] = float(
                    np.sum(final_surface_dist * weights)
                    / max(float(np.sum(weights)), 1e-8)
                )
            else:
                result["energy_surface"] = 0.0
        else:
            result["energy_surface"] = 0.0

        if laplacian_matrix is not None:
            final_lap = laplacian_matrix @ fitted_vertices
            result["energy_laplacian"] = float(
                np.mean(np.linalg.norm(final_lap, axis=1))
            )
        else:
            result["energy_laplacian"] = 0.0

        x_center = float(np.median(fitted_vertices[:, 0]))
        left_mask = fitted_vertices[:, 0] > x_center
        right_mask = fitted_vertices[:, 0] < x_center
        if np.any(left_mask) and np.any(right_mask):
            left_center = fitted_vertices[left_mask].mean(axis=0)
            right_center = fitted_vertices[right_mask].mean(axis=0)
            result["energy_symmetry"] = float(
                abs(left_center[1] - right_center[1])
                + abs(left_center[2] - right_center[2])
            )
        else:
            result["energy_symmetry"] = 0.0
        
        # Save fit.npz with deformation field (includes non-rigid displacements)
        deltas = fitted_vertices - original_vertices
        fit_path = pathlib.Path(output_dir) / "fit.npz"
        np.savez(
            fit_path,
            vertices=fitted_vertices,
            original_vertices=original_vertices,
            rigid_transformed=rigid_transformed,
            deltas=deltas,
            nonrigid_displacements=final_displacements,
            objective_weights=result["objective_weights"],
            optimized_params=result["optimized_params"]
        )
        result["fit_npz"] = str(fit_path)
        result["delta_norm"] = float(np.linalg.norm(deltas))
        
        # Compute objective value from rigid phase and non-rigid displacement
        # Using opt_result.fun if available, otherwise estimate from delta_norm
        if hasattr(opt_result, 'fun') and opt_result.fun is not None:
            result["objective_value"] = float(opt_result.fun) + result["delta_norm"] * 0.01
        else:
            result["objective_value"] = float(result["delta_norm"])
        
        # 피팅된 메시 저장
        fitted_mesh = trimesh.Trimesh(vertices=fitted_vertices, faces=mesh.faces)
        fitted_path = pathlib.Path(output_dir) / "fitted.glb"
        fitted_mesh.export(str(fitted_path))
        if not fitted_path.is_file() or fitted_path.stat().st_size == 0:
            raise RuntimeError("Fitted mesh export produced no artifact")
        reloaded = trimesh.load(str(fitted_path))
        if isinstance(reloaded, trimesh.Scene):
            reload_geometries = list(reloaded.geometry.values())
            if not reload_geometries:
                raise RuntimeError("Fitted GLB re-import contains no geometry")
        elif len(reloaded.vertices) == 0:
            raise RuntimeError("Fitted GLB re-import contains no vertices")
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
    target_mesh: str,
) -> Dict[str, Any]:
    """Align canonical/reference using upper-head scale, not total body height.

    This keeps the standardized VRM body proportion stable for bust-up inputs.
    """
    result: Dict[str, Any] = {"status": "pending"}
    try:
        import numpy as np
        import trimesh

        def as_mesh(path: str):
            loaded = trimesh.load(path, process=False)
            if isinstance(loaded, trimesh.Scene):
                geometries = list(loaded.geometry.values())
                if not geometries:
                    raise ValueError(f"mesh scene has no geometry: {path}")
                loaded = trimesh.util.concatenate(geometries)
            vertices = np.asarray(loaded.vertices, dtype=float)
            if len(vertices) == 0 or not np.all(np.isfinite(vertices)):
                raise ValueError(f"mesh has no finite vertices: {path}")
            return vertices

        def head_region(vertices: np.ndarray) -> np.ndarray:
            pmin = vertices.min(axis=0)
            pmax = vertices.max(axis=0)
            height = max(float(pmax[1] - pmin[1]), 1e-8)
            mask = vertices[:, 1] >= pmin[1] + 0.72 * height
            region = vertices[mask]
            if len(region) < 32:
                order = np.argsort(vertices[:, 1])
                region = vertices[order[-min(len(vertices), 256):]]
            return region

        source_vertices = as_mesh(source_mesh)
        target_vertices = as_mesh(target_mesh)
        source_head = head_region(source_vertices)
        target_head = head_region(target_vertices)

        source_extent = np.ptp(source_head, axis=0)
        target_extent = np.ptp(target_head, axis=0)

        # Prefer horizontal/depth head dimensions. Vertical target extent is
        # unreliable for cropped/bust-up references.
        ratios = []
        for axis in (0, 2):
            if source_extent[axis] > 1e-8 and target_extent[axis] > 1e-8:
                ratios.append(target_extent[axis] / source_extent[axis])
        if not ratios:
            valid = source_extent > 1e-8
            ratios = (
                target_extent[valid] / source_extent[valid]
            ).tolist()
        if not ratios:
            raise ValueError("unable to estimate canonical/reference scale")

        scale = float(np.median(np.asarray(ratios, dtype=float)))
        if not np.isfinite(scale) or scale <= 0.0:
            raise ValueError(f"invalid similarity scale: {scale}")

        source_head_center = source_head.mean(axis=0)
        target_head_center = target_head.mean(axis=0)
        translation = target_head_center - source_head_center * scale

        result.update({
            "status": "complete",
            "scale": scale,
            "rotation": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            "translation": translation.tolist(),
            "scale_basis": "head_xz",
        })
    except Exception as exc:
        result["status"] = "error"
        result["error"] = str(exc)
    return result


# Landmark names for semantic correspondence
LANDMARK_NAMES = [
    "right_eye_outer_corner",
    "right_eye_inner_corner", 
    "left_eye_inner_corner",
    "left_eye_outer_corner",
    "nose_tip",
    "nose_bridge",
    "mouth_right_corner",
    "mouth_left_corner",
    "mouth_upper_lip_center",
    "mouth_lower_lip_center",
    "chin",
    "right_eyebrow_outer",
    "right_eyebrow_inner",
    "left_eyebrow_inner",
    "left_eyebrow_outer",
]


def normalize_landmarks(
    landmarks_2d: List[List[float]],
    image_shape: tuple,
    template_bbox: Dict[str, List[float]]
) -> List[List[float]]:
    """Normalize 2D image landmarks to template mesh coordinate space.
    
    Transforms pixel coordinates from image space to template mesh space (meters).
    
    Steps:
    1. Scale image pixels to [0, 1] using image_shape
    2. Scale to template bounding box extent
    3. Offset by template_bbox origin
    
    Args:
        landmarks_2d: List of [x, y] pixel coordinates from face detector.
        image_shape: (height, width) of the input image.
        template_bbox: Dictionary with 'min' and 'max' keys defining the
                       template mesh bounding box in meters.
                       Example: {'min': [-0.1, 0.0, -0.1], 'max': [0.1, 0.3, 0.1]}
                       
    Returns:
        List of [x, y] landmarks in template space (meters), ready for 3D projection.
    """
    if not landmarks_2d:
        return []
    
    import numpy as np
    
    img_h, img_w = image_shape[:2]
    
    # Template bounding box extent
    bbox_min = np.array(template_bbox.get('min', [-0.1, 0.0, -0.1]))
    bbox_max = np.array(template_bbox.get('max', [0.1, 0.3, 0.1]))
    bbox_extent = bbox_max - bbox_min
    
    # Template center for alignment
    bbox_center = (bbox_min + bbox_max) / 2
    
    normalized = []
    for lm in landmarks_2d:
        if len(lm) >= 2:
            x, y = lm[0], lm[1]
            
            # Step 1: Scale to [0, 1]
            x_norm = x / img_w
            y_norm = y / img_h
            
            # Step 2: Scale to template bbox extent
            # X: map to template X range (mirror for correct orientation)
            x_template = bbox_extent[0] * (1.0 - x_norm) + bbox_min[0]
            
            # Y: map to template Y range (flip Y axis - image Y is top-down)
            y_template = bbox_extent[1] * (1.0 - y_norm) + bbox_min[1]
            
            normalized.append([x_template, y_template])
    
    return normalized


def build_semantic_correspondence(
    landmarks_2d: List[List[float]],
    template,
    landmarks_json: Optional[Dict[str, Any]] = None
) -> List[tuple]:
    """Build correspondence pairs between image landmarks and template vertices.
    
    Uses vertex_groups from landmarks_json to find the center vertex for each
    landmark region (e.g., eye corners, nose tip, mouth corners).
    
    Args:
        landmarks_2d: Normalized 2D landmarks in template space.
        template: Template mesh object with vertices attribute.
        landmarks_json: Optional dictionary with 'vertex_groups' mapping
                        landmark names to vertex indices.
                        Example: {'vertex_groups': {'left_eye': [1, 2, 3]}}
                        
    Returns:
        List of (image_landmark_2d, template_vertex_3d) correspondence pairs.
        Each pair is ([x, y], [vx, vy, vz]).
    """
    import numpy as np
    
    correspondences = []
    
    if not landmarks_2d:
        return correspondences
    
    # Get template vertices
    if hasattr(template, 'vertices'):
        template_vertices = np.array(template.vertices)
    else:
        return correspondences
    
    # If vertex_groups available, use them for precise correspondence
    if landmarks_json and 'vertex_groups' in landmarks_json:
        vertex_groups = landmarks_json['vertex_groups']
        
        for i, lm_name in enumerate(LANDMARK_NAMES):
            if i >= len(landmarks_2d):
                break
            
            # Find vertex group for this landmark
            group_key = lm_name.lower().replace('_', '')
            matching_key = None
            
            for vg_name in vertex_groups.keys():
                if group_key in vg_name.lower().replace('_', '').replace('-', ''):
                    matching_key = vg_name
                    break
            
            if matching_key:
                # Get center of vertex group
                group_indices = vertex_groups[matching_key]
                if isinstance(group_indices, list) and len(group_indices) > 0:
                    group_vertices = template_vertices[group_indices]
                    center_vertex = group_vertices.mean(axis=0)
                    correspondences.append((landmarks_2d[i], center_vertex.tolist()))
    
    # Fallback: use distance-based matching for remaining landmarks
    if not correspondences and len(landmarks_2d) > 0:
        # Project template vertices to 2D (front view: X, Y plane)
        template_2d = template_vertices[:, [0, 1]]
        
        for lm in landmarks_2d:
            lm_arr = np.array(lm[:2])
            
            # Find closest template vertex in 2D
            distances = np.linalg.norm(template_2d - lm_arr, axis=1)
            closest_idx = np.argmin(distances)
            
            correspondences.append((lm, template_vertices[closest_idx].tolist()))
    
    return correspondences


def estimate_rigid_transform(
    source_points: List[List[float]],
    target_points: List[List[float]]
) -> Dict[str, Any]:
    """Estimate rigid transform (scale, rotation, translation) between point sets.
    
    Uses Procrustes analysis to find the optimal 7-DOF rigid transformation
    that aligns source points to target points.
    
    Args:
        source_points: Source point coordinates.
        target_points: Target point coordinates.
        
    Returns:
        Dictionary with 'scale', 'rotation' (Euler angles), and 'translation'.
    """
    import numpy as np
    
    if len(source_points) < 3 or len(target_points) < 3:
        return {"scale": 1.0, "rotation": [0.0, 0.0, 0.0], "translation": [0.0, 0.0, 0.0]}
    
    src = np.array(source_points)
    tgt = np.array(target_points)
    
    # Compute centroids
    src_centroid = src.mean(axis=0)
    tgt_centroid = tgt.mean(axis=0)
    
    # Center the points
    src_centered = src - src_centroid
    tgt_centered = tgt - tgt_centroid
    
    # Compute scale
    src_scale = np.linalg.norm(src_centered)
    tgt_scale = np.linalg.norm(tgt_centered)
    scale = tgt_scale / src_scale if src_scale > 1e-10 else 1.0
    
    # Scale source
    src_centered_scaled = src_centered * scale
    
    # Compute rotation using SVD (Kabsch algorithm)
    H = src_centered_scaled.T @ tgt_centered
    U, _, Vt = np.linalg.svd(H)
    R = Vt.T @ U.T
    
    # Ensure proper rotation (det = 1)
    if np.linalg.det(R) < 0:
        Vt[-1, :] *= -1
        R = Vt.T @ U.T
    
    # Convert rotation matrix to Euler angles
    # Using ZYX order (yaw, pitch, roll)
    rx = np.arctan2(R[2, 1], R[2, 2])
    ry = np.arctan2(-R[2, 0], np.sqrt(R[2, 1]**2 + R[2, 2]**2))
    rz = np.arctan2(R[1, 0], R[0, 0])
    
    # Compute translation
    translation = tgt_centroid - scale * R @ src_centroid
    
    return {
        "scale": float(scale),
        "rotation": [float(rx), float(ry), float(rz)],
        "translation": translation.tolist()
    }


def apply_rigid_transform(
    vertices: np.ndarray,
    scale: float,
    rotation: List[float],
    translation: List[float]
) -> np.ndarray:
    """Apply rigid transformation to vertices.
    
    Args:
        vertices: (N, 3) array of vertex positions.
        scale: Uniform scale factor.
        rotation: Euler angles [rx, ry, rz] in radians.
        translation: Translation vector [tx, ty, tz].
        
    Returns:
        Transformed vertices array.
    """
    rx, ry, rz = rotation
    tx, ty, tz = translation
    
    # Build rotation matrix
    cos_x, sin_x = np.cos(rx), np.sin(rx)
    Rx = np.array([[1, 0, 0], [0, cos_x, -sin_x], [0, sin_x, cos_x]])
    
    cos_y, sin_y = np.cos(ry), np.sin(ry)
    Ry = np.array([[cos_y, 0, sin_y], [0, 1, 0], [-sin_y, 0, cos_y]])
    
    cos_z, sin_z = np.cos(rz), np.sin(rz)
    Rz = np.array([[cos_z, -sin_z, 0], [sin_z, cos_z, 0], [0, 0, 1]])
    
    R = Rz @ Ry @ Rx
    
    # Apply transformation
    transformed = (scale * (R @ vertices.T)).T + np.array([tx, ty, tz])
    
    return transformed


def select_deformation_graph_nodes(
    vertices: np.ndarray,
    n_nodes: int = 200
) -> np.ndarray:
    """Select deformation graph nodes using farthest point sampling.
    
    Creates a sparse set of control nodes for Laplacian deformation.
    
    Args:
        vertices: (N, 3) array of mesh vertices.
        n_nodes: Target number of deformation graph nodes.
        
    Returns:
        Array of vertex indices for the selected nodes.
    """
    import numpy as np
    
    n_vertices = len(vertices)
    if n_vertices <= n_nodes:
        return np.arange(n_vertices)
    
    # Farthest point sampling
    selected = [0]  # Start with first vertex
    
    for _ in range(n_nodes - 1):
        # Find the vertex farthest from all selected vertices
        selected_vertices = vertices[selected]
        min_distances = np.full(n_vertices, np.inf)
        
        for sv in selected_vertices:
            distances = np.linalg.norm(vertices - sv, axis=1)
            min_distances = np.minimum(min_distances, distances)
        
        # Select the vertex with maximum minimum distance
        farthest_idx = np.argmax(min_distances)
        selected.append(int(farthest_idx))
    
    return np.array(selected)


def interpolate_displacements(
    vertices: np.ndarray,
    graph_nodes: np.ndarray,
    graph_displacements: np.ndarray
) -> np.ndarray:
    """Interpolate graph node displacements to all vertices.
    
    Uses barycentric weights based on distance to graph nodes.
    
    Args:
        vertices: (N, 3) array of all mesh vertices.
        graph_nodes: Indices of deformation graph nodes.
        graph_displacements: (M, 3) displacements for graph nodes.
        
    Returns:
        (N, 3) interpolated displacements for all vertices.
    """
    import numpy as np
    
    graph_positions = vertices[graph_nodes]
    displacements = np.zeros_like(vertices)
    
    # For each vertex, compute weighted average of nearby graph node displacements
    n_neighbors = min(4, len(graph_nodes))
    
    for i, v in enumerate(vertices):
        # Find nearest graph nodes
        distances = np.linalg.norm(graph_positions - v, axis=1)
        nearest_indices = np.argsort(distances)[:n_neighbors]
        nearest_distances = distances[nearest_indices]
        
        # Compute weights (inverse distance)
        if nearest_distances[0] < 1e-10:
            # Vertex coincides with a graph node
            weights = np.zeros(n_neighbors)
            weights[0] = 1.0
        else:
            weights = 1.0 / (nearest_distances + 1e-10)
            weights = weights / weights.sum()
        
        # Interpolate displacement
        for j, idx in enumerate(nearest_indices):
            displacements[i] += weights[j] * graph_displacements[idx]
    
    return displacements
