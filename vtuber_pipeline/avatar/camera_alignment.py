"""Camera estimation from 2D-3D correspondences.

This module provides the align_camera function for estimating camera
parameters from 2D landmarks and corresponding 3D positions.
"""

from typing import Dict, Any, List, Optional


def align_camera(landmarks_2d: List[List[float]], landmarks_3d: List[List[float]]) -> Dict[str, Any]:
    """Estimate camera pose from 2D-3D landmark correspondences.
    
    Uses solvePnP (if OpenCV available) to estimate rotation and translation
    that projects 3D landmarks to 2D positions.
    
    Args:
        landmarks_2d: List of 2D landmark points [[x, y], ...].
        landmarks_3d: List of corresponding 3D landmark points [[x, y, z], ...].
        
    Returns:
        Dictionary with:
        - rotation_matrix: 3x3 rotation matrix (identity if stub)
        - translation: 3D translation vector [x, y, z]
        - fov_deg: Field of view in degrees
    """
    result = {
        "rotation_matrix": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        "translation": [0.0, 0.0, 0.0],
        "fov_deg": 45.0
    }
    
    if len(landmarks_2d) < 6 or len(landmarks_3d) < 6:
        # Need at least 6 points for solvePnP
        result["warning"] = "Insufficient landmarks for solvePnP, using identity"
        return result
    
    if len(landmarks_2d) != len(landmarks_3d):
        result["warning"] = "Landmark count mismatch, using identity"
        return result
    
    try:
        import numpy as np
        
        try:
            import cv2
            
            # Convert to numpy arrays
            points_2d = np.array(landmarks_2d, dtype=np.float32)
            points_3d = np.array(landmarks_3d, dtype=np.float32)
            
            # Estimate image center and focal length
            max_x = np.max(points_2d[:, 0])
            max_y = np.max(points_2d[:, 1])
            
            # Camera matrix (assume centered, estimate focal length)
            focal_length = max(max_x, max_y)
            cx = max_x / 2
            cy = max_y / 2
            
            camera_matrix = np.array([
                [focal_length, 0, cx],
                [0, focal_length, cy],
                [0, 0, 1]
            ], dtype=np.float32)
            
            dist_coeffs = None  # Assume no distortion
            
            # Solve PnP
            success, rvec, tvec = cv2.solvePnP(
                points_3d, points_2d, camera_matrix, dist_coeffs
            )
            
            if success:
                # Convert rotation vector to matrix
                rotation_matrix, _ = cv2.Rodrigues(rvec)
                result["rotation_matrix"] = rotation_matrix.tolist()
                result["translation"] = tvec.flatten().tolist()
                
                # Estimate FOV from focal length
                fov_rad = 2 * np.arctan(max(max_x, max_y) / (2 * focal_length))
                result["fov_deg"] = float(np.degrees(fov_rad))
                
                result["status"] = "complete"
            else:
                result["status"] = "solvepnp_failed"
                result["warning"] = "solvePnP failed, using identity"
                
        except ImportError:
            result["status"] = "stub"
            result["warning"] = "OpenCV not installed, using identity transform"
            
    except ImportError:
        result["status"] = "error"
        result["error"] = "numpy not installed"
    
    return result


def estimate_camera_extrinsics(
    landmarks_2d: List[List[float]],
    landmarks_3d: List[List[float]],
    image_size: tuple
) -> Dict[str, Any]:
    """Estimate full camera extrinsics including camera matrix.
    
    Args:
        landmarks_2d: List of 2D landmark points.
        landmarks_3d: List of corresponding 3D landmark points.
        image_size: Tuple of (width, height).
        
    Returns:
        Dictionary with rotation_vector, translation_vector, camera_matrix.
    """
    result = align_camera(landmarks_2d, landmarks_3d)
    
    # Flatten rotation matrix to rotation vector (stub)
    result["rotation_vector"] = [0.0, 0.0, 0.0]
    result["camera_matrix"] = [
        [1000.0, 0.0, image_size[0] / 2],
        [0.0, 1000.0, image_size[1] / 2],
        [0.0, 0.0, 1.0]
    ]
    
    return result
