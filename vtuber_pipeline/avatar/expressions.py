"""Expression shape key generation and validation for VRM avatars.

This module provides functions for defining, generating, and validating
VRM expression shape keys (blend shapes) for VTuber avatars.
"""

import json
import pathlib
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import trimesh


def load_vertex_groups(landmarks_path: Optional[str] = None) -> Dict[str, List[int]]:
    """Load an explicitly supplied topology-specific vertex-group map.

    Production does not silently load the repository legacy index map because
    the canonical MakeHuman-derived topology can differ from that historical
    procedural template. When no explicit map is supplied, groups are derived
    directly from the current mesh geometry.
    """
    if landmarks_path is None:
        return {}
    path = pathlib.Path(landmarks_path)
    try:
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
        groups = data.get("vertex_groups", {})
        return groups if isinstance(groups, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


# Required VRM 1.0 expression presets
REQUIRED_EXPRESSIONS = [
    "blink",
    "blinkLeft",
    "blinkRight",
    "aa",  # A mouth shape
    "ih",  # I mouth shape
    "ou",  # U mouth shape
    "ee",  # E mouth shape
    "oh",  # O mouth shape
    "happy",
    "angry",
    "sad",
    "relaxed",
    "surprised"
]


def _load_mesh_vertices(mesh_path: str) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Load mesh and extract vertex positions.
    
    Args:
        mesh_path: Path to the mesh file (GLB/GLTF/OBJ).
        
    Returns:
        Tuple of (vertices array, mesh bounds info).
    """
    # Try pygltflib first for GLB files (handles skinned meshes better)
    if mesh_path.lower().endswith(('.glb', '.gltf', '.vrm')):
        try:
            from pygltflib import GLTF2
            gltf = GLTF2().load(mesh_path)
            
            # Find the first mesh with POSITION attribute
            for mesh in gltf.meshes:
                for primitive in mesh.primitives:
                    if primitive.attributes.POSITION is not None:
                        acc = gltf.accessors[primitive.attributes.POSITION]
                        bv = gltf.bufferViews[acc.bufferView]
                        blob = gltf.binary_blob()
                        
                        offset = bv.byteOffset if bv.byteOffset else 0
                        data = blob[offset:offset + bv.byteLength]
                        vertices = np.frombuffer(data, dtype=np.float32).reshape(-1, 3)
                        
                        bounds = {
                            "min": np.array(acc.min) if acc.min else vertices.min(axis=0),
                            "max": np.array(acc.max) if acc.max else vertices.max(axis=0),
                            "center": vertices.mean(axis=0),
                            "vertex_count": len(vertices)
                        }
                        
                        return vertices, bounds
        except Exception:
            pass  # Fall through to trimesh
    
    # Fallback to trimesh for OBJ and other formats
    mesh = trimesh.load(mesh_path)
    
    # Get vertices - handle Scene vs Mesh
    if isinstance(mesh, trimesh.Scene):
        # Get the first mesh from the scene
        mesh = list(mesh.geometry.values())[0]
    
    vertices = np.array(mesh.vertices)
    
    # Calculate bounding box info
    bounds = {
        "min": vertices.min(axis=0),
        "max": vertices.max(axis=0),
        "center": vertices.mean(axis=0),
        "vertex_count": len(vertices)
    }
    
    return vertices, bounds


def derive_expression_vertex_groups(
    vertices: np.ndarray,
    bounds: Dict[str, Any],
) -> Dict[str, List[int]]:
    """Derive facial semantic groups from the current fitted/rigged mesh.

    The selector is topology-agnostic: it first isolates the upper-body head
    region, infers the forward Z direction from head depth asymmetry, then
    selects front-surface vertices nearest normalized eye, brow and mouth
    targets. This avoids carrying vertex indices across unrelated topologies.
    """
    vertices = np.asarray(vertices, dtype=float)
    if len(vertices) < 32:
        raise ValueError("mesh has too few vertices for facial regions")

    pmin = np.asarray(bounds["min"], dtype=float)
    pmax = np.asarray(bounds["max"], dtype=float)
    height = max(float(pmax[1] - pmin[1]), 1e-8)
    head_mask = vertices[:, 1] >= pmin[1] + 0.68 * height
    head_idx = np.flatnonzero(head_mask)
    if len(head_idx) < 24:
        raise ValueError("unable to isolate a usable head region")
    head = vertices[head_idx]
    hmin = head.min(axis=0)
    hmax = head.max(axis=0)
    hcenter = (hmin + hmax) * 0.5
    hwidth = max(float(hmax[0] - hmin[0]), 1e-8)
    hheight = max(float(hmax[1] - hmin[1]), 1e-8)

    z_center = float(np.median(head[:, 2]))
    pos_extent = float(hmax[2] - z_center)
    neg_extent = float(z_center - hmin[2])
    front_sign = 1.0 if pos_extent >= neg_extent else -1.0
    front_depth = front_sign * (head[:, 2] - z_center)
    depth_cut = float(np.quantile(front_depth, 0.55))
    front_local = np.flatnonzero(front_depth >= depth_cut)
    if len(front_local) < 24:
        front_local = np.arange(len(head))
    front_idx = head_idx[front_local]
    front = vertices[front_idx]

    x_norm = (front[:, 0] - hcenter[0]) / (0.5 * hwidth)
    y_norm = (front[:, 1] - hmin[1]) / hheight

    def nearest(target_x: float, target_y: float, count: int) -> List[int]:
        dist = (x_norm - target_x) ** 2 + 1.6 * (y_norm - target_y) ** 2
        order = np.argsort(dist)[:max(1, min(count, len(front_idx)))]
        return [int(front_idx[i]) for i in order]

    def split_vertical(indices: List[int]) -> tuple[List[int], List[int]]:
        if not indices:
            return [], []
        ys = vertices[indices, 1]
        mid = float(np.median(ys))
        upper = [int(i) for i in indices if vertices[i, 1] >= mid]
        lower = [int(i) for i in indices if vertices[i, 1] < mid]
        return upper or indices[:1], lower or indices[-1:]

    left_eye_all = nearest(+0.32, 0.56, 18)
    right_eye_all = nearest(-0.32, 0.56, 18)
    upper_l, lower_l = split_vertical(left_eye_all)
    upper_r, lower_r = split_vertical(right_eye_all)

    mouth_all = nearest(0.0, 0.28, 28)
    upper_lip, lower_lip = split_vertical(mouth_all)
    mouth_sorted = sorted(
        mouth_all,
        key=lambda i: abs((vertices[i, 0] - hcenter[0]) / (0.5 * hwidth)),
        reverse=True,
    )
    mouth_corners = mouth_sorted[:max(2, min(8, len(mouth_sorted)))]

    left_brow = nearest(+0.32, 0.70, 14)
    right_brow = nearest(-0.32, 0.70, 14)

    groups = {
        "upper_eyelid_L": upper_l,
        "lower_eyelid_L": lower_l,
        "upper_eyelid_R": upper_r,
        "lower_eyelid_R": lower_r,
        "upper_lip": upper_lip,
        "lower_lip": lower_lip,
        "mouth_corners": mouth_corners,
        "left_eyebrow": left_brow,
        "right_eyebrow": right_brow,
    }
    if any(len(values) == 0 for values in groups.values()):
        raise ValueError("derived facial vertex group is empty")
    return groups

def _identify_eye_region_vertices(
    vertices: np.ndarray,
    bounds: Dict[str, Any],
    side: str = "both"
) -> List[int]:
    """Identify eye region vertex indices using bounding box heuristics.
    
    Eyes are typically in the upper portion of the face, 
    on either side of the center line.
    
    Args:
        vertices: Nx3 array of vertex positions.
        bounds: Mesh bounds info from _load_mesh_vertices.
        side: "left", "right", or "both" to select which eye(s).
        
    Returns:
        List of vertex indices in the eye region.
    """
    min_b = bounds["min"]
    max_b = bounds["max"]
    center = bounds["center"]
    
    # Eye region heuristics (based on typical humanoid proportions)
    # Y: upper 40-70% of face height
    y_min = min_b[1] + 0.40 * (max_b[1] - min_b[1])
    y_max = min_b[1] + 0.70 * (max_b[1] - min_b[1])
    
    # Z: front 60% of depth (eyes are on the front of face)
    z_min = max_b[2] - 0.60 * (max_b[2] - min_b[2])
    z_max = max_b[2]
    
    # X: depends on which eye
    indices = []
    for i, v in enumerate(vertices):
        if not (y_min <= v[1] <= y_max):
            continue
        if not (z_min <= v[2] <= z_max):
            continue
            
        # Check X position based on side
        if side == "left":
            # Left eye: negative X (left side of face)
            if v[0] < center[0] - 0.1 * (max_b[0] - min_b[0]):
                if v[0] > min_b[0] + 0.1 * (max_b[0] - min_b[0]):  # Not too far left
                    indices.append(i)
        elif side == "right":
            # Right eye: positive X (right side of face)
            if v[0] > center[0] + 0.1 * (max_b[0] - min_b[0]):
                if v[0] < max_b[0] - 0.1 * (max_b[0] - min_b[0]):  # Not too far right
                    indices.append(i)
        else:  # both
            if abs(v[0] - center[0]) > 0.1 * (max_b[0] - min_b[0]):
                indices.append(i)
    
    return indices


def _identify_eyebrow_region_vertices(
    vertices: np.ndarray,
    bounds: Dict[str, Any],
    side: str = "both"
) -> List[int]:
    """Identify eyebrow region vertex indices using bounding box heuristics.
    
    Eyebrows are above the eyes, typically 70-80% of face height.
    
    Args:
        vertices: Nx3 array of vertex positions.
        bounds: Mesh bounds info from _load_mesh_vertices.
        side: "left", "right", or "both" to select which eyebrow(s).
        
    Returns:
        List of vertex indices in the eyebrow region.
    """
    min_b = bounds["min"]
    max_b = bounds["max"]
    center = bounds["center"]
    
    # Eyebrow region heuristics
    # Y: 70-85% of face height (above eyes)
    y_min = min_b[1] + 0.70 * (max_b[1] - min_b[1])
    y_max = min_b[1] + 0.85 * (max_b[1] - min_b[1])
    
    # Z: front 50% of depth
    z_min = max_b[2] - 0.50 * (max_b[2] - min_b[2])
    z_max = max_b[2]
    
    indices = []
    for i, v in enumerate(vertices):
        if not (y_min <= v[1] <= y_max):
            continue
        if not (z_min <= v[2] <= z_max):
            continue
            
        if side == "left":
            if v[0] < center[0] - 0.1 * (max_b[0] - min_b[0]):
                if v[0] > min_b[0] + 0.1 * (max_b[0] - min_b[0]):
                    indices.append(i)
        elif side == "right":
            if v[0] > center[0] + 0.1 * (max_b[0] - min_b[0]):
                if v[0] < max_b[0] - 0.1 * (max_b[0] - min_b[0]):
                    indices.append(i)
        else:
            if abs(v[0] - center[0]) > 0.1 * (max_b[0] - min_b[0]):
                indices.append(i)
    
    return indices


def _identify_mouth_region_vertices(
    vertices: np.ndarray,
    bounds: Dict[str, Any]
) -> List[int]:
    """Identify mouth region vertex indices using bounding box heuristics.
    
    Mouth is typically in the lower third of the face, centered.
    
    Args:
        vertices: Nx3 array of vertex positions.
        bounds: Mesh bounds info from _load_mesh_vertices.
        
    Returns:
        List of vertex indices in the mouth region.
    """
    min_b = bounds["min"]
    max_b = bounds["max"]
    center = bounds["center"]
    
    # Mouth region heuristics
    # Y: 15-45% of face height (wider range for anime-style faces)
    y_min = min_b[1] + 0.15 * (max_b[1] - min_b[1])
    y_max = min_b[1] + 0.45 * (max_b[1] - min_b[1])
    
    # Z: front 80% of depth (wider range for visibility)
    z_min = max_b[2] - 0.80 * (max_b[2] - min_b[2])
    z_max = max_b[2]
    
    # X: center 50% of width (wider for anime-style mouths)
    x_range = max_b[0] - min_b[0]
    x_min = center[0] - 0.25 * x_range
    x_max = center[0] + 0.25 * x_range
    
    indices = []
    for i, v in enumerate(vertices):
        if not (y_min <= v[1] <= y_max):
            continue
        if not (z_min <= v[2] <= z_max):
            continue
        if not (x_min <= v[0] <= x_max):
            continue
        indices.append(i)
    
    return indices


def _identify_lip_region_vertices(
    vertices: np.ndarray,
    bounds: Dict[str, Any],
    part: str = "upper"
) -> List[int]:
    """Identify upper or lower lip vertex indices.
    
    Args:
        vertices: Nx3 array of vertex positions.
        bounds: Mesh bounds info from _load_mesh_vertices.
        part: "upper" or "lower" lip.
        
    Returns:
        List of vertex indices in the lip region.
    """
    min_b = bounds["min"]
    max_b = bounds["max"]
    center = bounds["center"]
    
    # Mouth/lip Y range - center at 30% height
    y_center = min_b[1] + 0.30 * (max_b[1] - min_b[1])
    y_half = 0.08 * (max_b[1] - min_b[1])  # Wider range for lips
    
    if part == "upper":
        y_min = y_center - y_half
        y_max = y_center
    else:  # lower
        y_min = y_center
        y_max = y_center + y_half
    
    # Z: front 80% of depth
    z_min = max_b[2] - 0.80 * (max_b[2] - min_b[2])
    z_max = max_b[2]
    
    # X: center 50% of width
    x_range = max_b[0] - min_b[0]
    x_min = center[0] - 0.25 * x_range
    x_max = center[0] + 0.25 * x_range
    
    indices = []
    for i, v in enumerate(vertices):
        if not (y_min <= v[1] <= y_max):
            continue
        if not (z_min <= v[2] <= z_max):
            continue
        if not (x_min <= v[0] <= x_max):
            continue
        indices.append(i)
    
    return indices


def generate_blink_morph(
    vertices: np.ndarray,
    bounds: Dict[str, Any],
    side: str = "both",
    vertex_groups: Optional[Dict[str, List[int]]] = None
) -> List[Tuple[int, List[float]]]:
    """Generate blink morph target - close eyelids by moving vertices down.
    
    Args:
        vertices: Nx3 array of vertex positions.
        bounds: Mesh bounds info.
        side: "left", "right", or "both" for which eye(s) to blink.
        vertex_groups: Optional dict of vertex group name -> indices.
        
    Returns:
        List of (vertex_index, [dx, dy, dz]) offset tuples.
    """
    morph_data = []
    used_vertex_groups = False
    
    # Try to use vertex_groups if available
    if vertex_groups:
        upper_eyelid_L = vertex_groups.get("upper_eyelid_L", [])
        lower_eyelid_L = vertex_groups.get("lower_eyelid_L", [])
        upper_eyelid_R = vertex_groups.get("upper_eyelid_R", [])
        lower_eyelid_R = vertex_groups.get("lower_eyelid_R", [])
        
        # Filter out-of-range indices
        n_vertices = len(vertices)
        upper_eyelid_L = [i for i in upper_eyelid_L if i < n_vertices]
        lower_eyelid_L = [i for i in lower_eyelid_L if i < n_vertices]
        upper_eyelid_R = [i for i in upper_eyelid_R if i < n_vertices]
        lower_eyelid_R = [i for i in lower_eyelid_R if i < n_vertices]
        
        # Check if we have valid vertex groups
        if (side in ["left", "both"] and (upper_eyelid_L or lower_eyelid_L)) or \
           (side in ["right", "both"] and (upper_eyelid_R or lower_eyelid_R)):
            used_vertex_groups = True
            
            # Left eye
            if side in ["left", "both"]:
                # Upper eyelid moves down (close)
                for idx in upper_eyelid_L:
                    morph_data.append((idx, [0.0, -0.01, 0.0]))
                # Lower eyelid moves up slightly
                for idx in lower_eyelid_L:
                    morph_data.append((idx, [0.0, 0.005, 0.0]))
            
            # Right eye
            if side in ["right", "both"]:
                # Upper eyelid moves down (close)
                for idx in upper_eyelid_R:
                    morph_data.append((idx, [0.0, -0.01, 0.0]))
                # Lower eyelid moves up slightly
                for idx in lower_eyelid_R:
                    morph_data.append((idx, [0.0, 0.005, 0.0]))
    
    # Fall back to bounding-box heuristics if vertex_groups not available or empty
    if not used_vertex_groups:
        eye_indices = _identify_eye_region_vertices(vertices, bounds, side)
        
        for idx in eye_indices:
            v = vertices[idx]
            eye_y_center = bounds["min"][1] + 0.55 * (bounds["max"][1] - bounds["min"][1])
            
            if v[1] > eye_y_center:
                dy = -0.01
            else:
                dy = -0.005
            
            morph_data.append((idx, [0.0, dy, 0.0]))
    
    return morph_data


def generate_viseme_morphs(
    vertices: np.ndarray,
    bounds: Dict[str, Any],
    vertex_groups: Optional[Dict[str, List[int]]] = None
) -> Dict[str, List[Tuple[int, List[float]]]]:
    """Generate viseme (mouth shape) morph targets.
    
    VRM standard visemes:
    - aa: Open mouth (like saying "ah")
    - ih: Slight smile shape ("ih" sound)
    - ou: Rounded mouth ("oh" sound)
    - ee: Wide mouth ("ee" sound)
    - oh: O-shaped mouth ("oh" sound)
    
    Args:
        vertices: Nx3 array of vertex positions.
        bounds: Mesh bounds info.
        vertex_groups: Optional dict of vertex group name -> indices.
        
    Returns:
        Dictionary mapping viseme names to morph data.
    """
    visemes = {}
    center = bounds["center"]
    x_range = bounds["max"][0] - bounds["min"][0]
    n_vertices = len(vertices)
    
    # Try to use vertex_groups if available
    used_vertex_groups = False
    upper_lip_indices = []
    lower_lip_indices = []
    mouth_corner_indices = []
    
    if vertex_groups:
        upper_lip_indices = [i for i in vertex_groups.get("upper_lip", []) if i < n_vertices]
        lower_lip_indices = [i for i in vertex_groups.get("lower_lip", []) if i < n_vertices]
        mouth_corner_indices = [i for i in vertex_groups.get("mouth_corners", []) if i < n_vertices]
        
        if upper_lip_indices or lower_lip_indices or mouth_corner_indices:
            used_vertex_groups = True
    
    if used_vertex_groups:
        # aa: Open mouth - move upper lip up, lower lip down
        aa_morph = []
        for idx in upper_lip_indices:
            aa_morph.append((idx, [0.0, 0.008, 0.0]))  # Upper lip up
        for idx in lower_lip_indices:
            aa_morph.append((idx, [0.0, -0.008, 0.0]))  # Lower lip down
        visemes["aa"] = aa_morph
        
        # ih: Slight smile - pull mouth corners outward and slightly up
        ih_morph = []
        for idx in mouth_corner_indices:
            v = vertices[idx]
            dx = 0.003 if v[0] > center[0] else -0.003
            ih_morph.append((idx, [dx, 0.002, 0.0]))
        visemes["ih"] = ih_morph
        
        # ou: Rounded mouth - push lips forward, narrow horizontally
        ou_morph = []
        for idx in upper_lip_indices + lower_lip_indices:
            v = vertices[idx]
            dx = -0.002 if v[0] > center[0] else 0.002
            ou_morph.append((idx, [dx, 0.0, 0.005]))
        visemes["ou"] = ou_morph
        
        # ee: Wide mouth - pull corners outward
        ee_morph = []
        for idx in mouth_corner_indices:
            v = vertices[idx]
            dx = 0.006 if v[0] > center[0] else -0.006
            ee_morph.append((idx, [dx, 0.002, 0.0]))
        visemes["ee"] = ee_morph
        
        # oh: O-shaped mouth - narrow and round
        oh_morph = []
        for idx in upper_lip_indices + lower_lip_indices:
            v = vertices[idx]
            dx = -0.004 if v[0] > center[0] else 0.004
            oh_morph.append((idx, [dx, 0.0, 0.004]))
        visemes["oh"] = oh_morph
    else:
        # Fall back to bounding-box heuristics
        mouth_indices = _identify_mouth_region_vertices(vertices, bounds)
        upper_lip_indices = _identify_lip_region_vertices(vertices, bounds, "upper")
        lower_lip_indices = _identify_lip_region_vertices(vertices, bounds, "lower")
        
        # aa: Open mouth
        aa_morph = []
        for idx in upper_lip_indices:
            aa_morph.append((idx, [0.0, 0.008, 0.0]))
        for idx in lower_lip_indices:
            aa_morph.append((idx, [0.0, -0.008, 0.0]))
        visemes["aa"] = aa_morph
        
        # ih: Slight smile
        ih_morph = []
        for idx in mouth_indices:
            v = vertices[idx]
            dx = 0.003 if v[0] > center[0] else -0.003
            dy = 0.002 if abs(v[0] - center[0]) > 0.1 * x_range else 0.0
            ih_morph.append((idx, [dx, dy, 0.0]))
        visemes["ih"] = ih_morph
        
        # ou: Rounded mouth
        ou_morph = []
        for idx in mouth_indices:
            v = vertices[idx]
            dx = -0.002 if v[0] > center[0] else 0.002
            ou_morph.append((idx, [dx, 0.0, 0.005]))
        visemes["ou"] = ou_morph
        
        # ee: Wide mouth
        ee_morph = []
        for idx in mouth_indices:
            v = vertices[idx]
            dx = 0.006 if v[0] > center[0] else -0.006
            dy = 0.002 if abs(v[0] - center[0]) > 0.08 * x_range else 0.0
            ee_morph.append((idx, [dx, dy, 0.0]))
        visemes["ee"] = ee_morph
        
        # oh: O-shaped mouth
        oh_morph = []
        for idx in mouth_indices:
            v = vertices[idx]
            dx = -0.004 if v[0] > center[0] else 0.004
            oh_morph.append((idx, [dx, 0.0, 0.004]))
        visemes["oh"] = oh_morph
    
    return visemes


def generate_emotion_morphs(
    vertices: np.ndarray,
    bounds: Dict[str, Any],
    vertex_groups: Optional[Dict[str, List[int]]] = None
) -> Dict[str, List[Tuple[int, List[float]]]]:
    """Generate emotion morph targets with eyebrow and mouth changes.
    
    Args:
        vertices: Nx3 array of vertex positions.
        bounds: Mesh bounds info.
        vertex_groups: Optional dict of vertex group name -> indices.
        
    Returns:
        Dictionary mapping emotion names to morph data.
    """
    emotions = {}
    center = bounds["center"]
    n_vertices = len(vertices)
    
    # Prefer topology-specific/dynamically-derived brow groups.
    left_brow = [
        i for i in (vertex_groups or {}).get("left_eyebrow", [])
        if 0 <= i < n_vertices
    ]
    right_brow = [
        i for i in (vertex_groups or {}).get("right_eyebrow", [])
        if 0 <= i < n_vertices
    ]
    if not left_brow:
        left_brow = _identify_eyebrow_region_vertices(vertices, bounds, "left")
    if not right_brow:
        right_brow = _identify_eyebrow_region_vertices(vertices, bounds, "right")
    
    # Try to use vertex_groups for mouth
    mouth_indices = []
    mouth_corner_indices = []
    upper_lip_indices = []
    lower_lip_indices = []
    
    if vertex_groups:
        mouth_corner_indices = [i for i in vertex_groups.get("mouth_corners", []) if i < n_vertices]
        upper_lip_indices = [i for i in vertex_groups.get("upper_lip", []) if i < n_vertices]
        lower_lip_indices = [i for i in vertex_groups.get("lower_lip", []) if i < n_vertices]
        mouth_indices = mouth_corner_indices + upper_lip_indices + lower_lip_indices
    
    # Fall back to bounding-box if no valid vertex groups for mouth
    if not mouth_indices:
        mouth_indices = _identify_mouth_region_vertices(vertices, bounds)
    
    # happy: Eyebrows slightly raised, mouth corners up
    happy_morph = []
    for idx in left_brow + right_brow:
        dy = 0.005
        happy_morph.append((idx, [0.0, dy, 0.0]))
    
    if mouth_corner_indices:
        # Use mouth corners for smile
        for idx in mouth_corner_indices:
            v = vertices[idx]
            dx = 0.004 if v[0] > center[0] else -0.004
            happy_morph.append((idx, [dx, 0.006, 0.0]))
    else:
        for idx in mouth_indices:
            v = vertices[idx]
            dx = 0.004 if v[0] > center[0] else -0.004
            dy = 0.006 if abs(v[0] - center[0]) > 0.05 else 0.0
            happy_morph.append((idx, [dx, dy, 0.0]))
    emotions["happy"] = happy_morph
    
    # angry: Eyebrows drawn together and down, mouth tense
    angry_morph = []
    for idx in left_brow:
        dx = 0.004
        dy = -0.008
        angry_morph.append((idx, [dx, dy, 0.0]))
    for idx in right_brow:
        dx = -0.004
        dy = -0.008
        angry_morph.append((idx, [dx, dy, 0.0]))
    for idx in mouth_indices:
        v = vertices[idx]
        dx = -0.002 if v[0] > center[0] else 0.002
        angry_morph.append((idx, [dx, 0.0, 0.0]))
    emotions["angry"] = angry_morph
    
    # sad: Inner eyebrows raised, outer eyebrows down, mouth corners down
    sad_morph = []
    for idx in left_brow:
        v = vertices[idx]
        if abs(v[0] - center[0]) > 0.04:
            dy = -0.006
        else:
            dy = 0.004
        sad_morph.append((idx, [0.0, dy, 0.0]))
    for idx in right_brow:
        v = vertices[idx]
        if abs(v[0] - center[0]) > 0.04:
            dy = -0.006
        else:
            dy = 0.004
        sad_morph.append((idx, [0.0, dy, 0.0]))
    
    if mouth_corner_indices:
        for idx in mouth_corner_indices:
            sad_morph.append((idx, [0.0, -0.004, 0.0]))
    else:
        for idx in mouth_indices:
            v = vertices[idx]
            dx = -0.002 if v[0] > center[0] else 0.002
            dy = -0.004 if abs(v[0] - center[0]) > 0.05 else 0.0
            sad_morph.append((idx, [dx, dy, 0.0]))
    emotions["sad"] = sad_morph
    
    # relaxed: Slight smile, neutral brows
    relaxed_morph = []
    if mouth_corner_indices:
        for idx in mouth_corner_indices:
            v = vertices[idx]
            dx = 0.002 if v[0] > center[0] else -0.002
            relaxed_morph.append((idx, [dx, 0.003, 0.0]))
    else:
        for idx in mouth_indices:
            v = vertices[idx]
            dx = 0.002 if v[0] > center[0] else -0.002
            dy = 0.003 if abs(v[0] - center[0]) > 0.06 else 0.0
            relaxed_morph.append((idx, [dx, dy, 0.0]))
    emotions["relaxed"] = relaxed_morph
    
    # surprised: Eyebrows raised high, eyes wide, mouth open
    surprised_morph = []
    for idx in left_brow + right_brow:
        dy = 0.012
        surprised_morph.append((idx, [0.0, dy, 0.0]))
    
    if upper_lip_indices and lower_lip_indices:
        for idx in upper_lip_indices:
            surprised_morph.append((idx, [0.0, 0.004, 0.0]))
        for idx in lower_lip_indices:
            surprised_morph.append((idx, [0.0, -0.006, 0.0]))
    else:
        for idx in mouth_indices:
            v = vertices[idx]
            if v[1] < center[1]:
                dy = -0.006
            else:
                dy = 0.004
            surprised_morph.append((idx, [0.0, dy, 0.0]))
    emotions["surprised"] = surprised_morph
    
    return emotions


def validate_expressions(
    shape_keys: Dict[str, Any],
    output_dir: str,
) -> Dict[str, Any]:
    """Validate required morph contracts without fabricating geometry checks."""
    result = {
        "status": "pending",
        "required_expressions": REQUIRED_EXPRESSIONS,
        "present_expressions": [],
        "missing_expressions": [],
        "invalid_expressions": [],
        "validation": {},
    }

    for expr in REQUIRED_EXPRESSIONS:
        item = shape_keys.get(expr)
        if item is None:
            result["missing_expressions"].append(expr)
            result["validation"][expr] = {"present": False, "valid_morph": False}
            continue

        result["present_expressions"].append(expr)
        morphs = item.get("morph_targets", []) if isinstance(item, dict) else item
        valid = isinstance(morphs, list) and len(morphs) > 0
        if valid:
            for morph in morphs:
                if not isinstance(morph, (list, tuple)) or len(morph) != 2:
                    valid = False
                    break
                vertex_index, delta = morph
                if not isinstance(vertex_index, (int, np.integer)) or int(vertex_index) < 0:
                    valid = False
                    break
                if not isinstance(delta, (list, tuple, np.ndarray)) or len(delta) != 3:
                    valid = False
                    break
                try:
                    delta_arr = np.asarray(delta, dtype=float)
                    if not np.all(np.isfinite(delta_arr)) or np.linalg.norm(delta_arr) <= 0.0:
                        valid = False
                        break
                except Exception:
                    valid = False
                    break

        if not valid:
            result["invalid_expressions"].append(expr)
        result["validation"][expr] = {
            "present": True,
            "valid_morph": bool(valid),
            "morph_count": len(morphs) if isinstance(morphs, list) else 0,
        }

    result["all_present"] = not result["missing_expressions"]
    result["pass"] = result["all_present"] and not result["invalid_expressions"]
    result["status"] = "complete" if result["pass"] else "error"
    _write_expression_report(output_dir, result)
    return result

def generate_expressions(
    mesh_path: str,
    template_expressions: Optional[Dict[str, Any]] = None,
    landmarks_path: Optional[str] = None
) -> Dict[str, Any]:
    """Generate expression shape keys for a mesh.
    
    Transfers expressions from a canonical template to the fitted mesh,
    or generates new expressions using landmark analysis.
    
    Args:
        mesh_path: Path to the mesh.
        template_expressions: Optional expression data from template.
        landmarks_path: Optional path to landmarks.json for vertex groups.
        
    Returns:
        Dictionary mapping expression names to morph target data.
        Each morph target contains:
        - "morph_targets": List of (vertex_index, [dx, dy, dz]) offsets
        - "vertex_count": Number of affected vertices
        - "status": "generated" or "from_template"
    """
    result = {
        "status": "generated",
        "expressions": {},
        "mesh_path": mesh_path
    }
    
    # Load mesh first; production vertex groups are derived from this exact
    # topology unless an explicit topology-specific map is supplied.
    try:
        vertices, bounds = _load_mesh_vertices(mesh_path)
        result["vertex_count"] = len(vertices)
        result["mesh_bounds"] = {
            "min": bounds["min"].tolist(),
            "max": bounds["max"].tolist()
        }
        vertex_groups = load_vertex_groups(landmarks_path)
        if vertex_groups:
            invalid = [
                idx
                for values in vertex_groups.values()
                for idx in values
                if not isinstance(idx, int) or idx < 0 or idx >= len(vertices)
            ]
            if invalid:
                raise ValueError("explicit expression vertex map does not match current topology")
            result["vertex_group_source"] = "explicit"
        else:
            vertex_groups = derive_expression_vertex_groups(vertices, bounds)
            result["vertex_group_source"] = "derived_current_mesh"
        result["vertex_groups_loaded"] = list(vertex_groups.keys())
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        # Return empty expressions on error
        for expr in REQUIRED_EXPRESSIONS:
            result["expressions"][expr] = {
                "morph_targets": [],
                "vertex_count": 0,
                "status": "error"
            }
        return result
    
    # Generate blink morphs
    blink_data = generate_blink_morph(vertices, bounds, "both", vertex_groups)
    result["expressions"]["blink"] = {
        "morph_targets": blink_data,
        "vertex_count": len(blink_data),
        "status": "generated"
    }
    
    blink_left_data = generate_blink_morph(vertices, bounds, "left", vertex_groups)
    result["expressions"]["blinkLeft"] = {
        "morph_targets": blink_left_data,
        "vertex_count": len(blink_left_data),
        "status": "generated"
    }
    
    blink_right_data = generate_blink_morph(vertices, bounds, "right", vertex_groups)
    result["expressions"]["blinkRight"] = {
        "morph_targets": blink_right_data,
        "vertex_count": len(blink_right_data),
        "status": "generated"
    }
    
    # Generate viseme morphs
    visemes = generate_viseme_morphs(vertices, bounds, vertex_groups)
    for viseme_name, morph_data in visemes.items():
        result["expressions"][viseme_name] = {
            "morph_targets": morph_data,
            "vertex_count": len(morph_data),
            "status": "generated"
        }
    
    # Generate emotion morphs
    emotions = generate_emotion_morphs(vertices, bounds, vertex_groups)
    for emotion_name, morph_data in emotions.items():
        result["expressions"][emotion_name] = {
            "morph_targets": morph_data,
            "vertex_count": len(morph_data),
            "status": "generated"
        }
    
    return result


def _write_expression_report(output_dir: str, result: Dict[str, Any]) -> None:
    """Write expression_report.json to output directory."""
    from vtuber_pipeline.core.utils import save_json
    
    pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)
    output_path = pathlib.Path(output_dir) / "expression_report.json"
    save_json(result, str(output_path))
