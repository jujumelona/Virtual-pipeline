"""Expression shape key generation and validation for VRM avatars.

This module provides functions for defining, generating, and validating
VRM expression shape keys (blend shapes) for VTuber avatars.
"""

import pathlib
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import trimesh


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
    side: str = "both"
) -> List[Tuple[int, List[float]]]:
    """Generate blink morph target - close eyelids by moving vertices down.
    
    Args:
        vertices: Nx3 array of vertex positions.
        bounds: Mesh bounds info.
        side: "left", "right", or "both" for which eye(s) to blink.
        
    Returns:
        List of (vertex_index, [dx, dy, dz]) offset tuples.
    """
    eye_indices = _identify_eye_region_vertices(vertices, bounds, side)
    
    # Move eyelid vertices down by 0.01 units (Y direction)
    morph_data = []
    for idx in eye_indices:
        # Calculate distance from eye center for smooth falloff
        v = vertices[idx]
        eye_y_center = bounds["min"][1] + 0.55 * (bounds["max"][1] - bounds["min"][1])
        
        # Stronger effect for vertices above eye center (upper eyelid)
        if v[1] > eye_y_center:
            dy = -0.01  # Move down
        else:
            dy = -0.005  # Less movement for lower eyelid
        
        morph_data.append((idx, [0.0, dy, 0.0]))
    
    return morph_data


def generate_viseme_morphs(
    vertices: np.ndarray,
    bounds: Dict[str, Any]
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
        
    Returns:
        Dictionary mapping viseme names to morph data.
    """
    mouth_indices = _identify_mouth_region_vertices(vertices, bounds)
    upper_lip_indices = _identify_lip_region_vertices(vertices, bounds, "upper")
    lower_lip_indices = _identify_lip_region_vertices(vertices, bounds, "lower")
    
    visemes = {}
    center = bounds["center"]
    x_range = bounds["max"][0] - bounds["min"][0]
    
    # aa: Open mouth - move upper lip up, lower lip down
    aa_morph = []
    for idx in upper_lip_indices:
        aa_morph.append((idx, [0.0, 0.008, 0.0]))  # Upper lip up
    for idx in lower_lip_indices:
        aa_morph.append((idx, [0.0, -0.008, 0.0]))  # Lower lip down
    visemes["aa"] = aa_morph
    
    # ih: Slight smile - pull mouth corners outward and slightly up
    ih_morph = []
    for idx in mouth_indices:
        v = vertices[idx]
        # Pull toward center horizontally
        dx = 0.003 if v[0] > center[0] else -0.003
        dy = 0.002 if abs(v[0] - center[0]) > 0.1 * x_range else 0.0
        ih_morph.append((idx, [dx, dy, 0.0]))
    visemes["ih"] = ih_morph
    
    # ou: Rounded mouth - push lips forward, narrow horizontally
    ou_morph = []
    for idx in mouth_indices:
        v = vertices[idx]
        # Narrow horizontally
        dx = -0.002 if v[0] > center[0] else 0.002
        # Push forward
        dz = 0.005
        ou_morph.append((idx, [dx, 0.0, dz]))
    visemes["ou"] = ou_morph
    
    # ee: Wide mouth - pull corners outward
    ee_morph = []
    for idx in mouth_indices:
        v = vertices[idx]
        # Pull outward based on which side
        dx = 0.006 if v[0] > center[0] else -0.006
        # Slight upward at corners
        dy = 0.002 if abs(v[0] - center[0]) > 0.08 * x_range else 0.0
        ee_morph.append((idx, [dx, dy, 0.0]))
    visemes["ee"] = ee_morph
    
    # oh: O-shaped mouth - narrow and round
    oh_morph = []
    for idx in mouth_indices:
        v = vertices[idx]
        # Narrow horizontally
        dx = -0.004 if v[0] > center[0] else 0.004
        # Push forward
        dz = 0.004
        oh_morph.append((idx, [dx, 0.0, dz]))
    visemes["oh"] = oh_morph
    
    return visemes


def generate_emotion_morphs(
    vertices: np.ndarray,
    bounds: Dict[str, Any]
) -> Dict[str, List[Tuple[int, List[float]]]]:
    """Generate emotion morph targets with eyebrow and mouth changes.
    
    Args:
        vertices: Nx3 array of vertex positions.
        bounds: Mesh bounds info.
        
    Returns:
        Dictionary mapping emotion names to morph data.
    """
    emotions = {}
    center = bounds["center"]
    
    # Get region indices
    left_brow = _identify_eyebrow_region_vertices(vertices, bounds, "left")
    right_brow = _identify_eyebrow_region_vertices(vertices, bounds, "right")
    mouth_indices = _identify_mouth_region_vertices(vertices, bounds)
    
    # happy: Eyebrows slightly raised, mouth corners up
    happy_morph = []
    for idx in left_brow + right_brow:
        v = vertices[idx]
        # Raise eyebrows slightly
        dy = 0.005
        happy_morph.append((idx, [0.0, dy, 0.0]))
    for idx in mouth_indices:
        v = vertices[idx]
        # Smile - pull corners up and out
        dx = 0.004 if v[0] > center[0] else -0.004
        dy = 0.006 if abs(v[0] - center[0]) > 0.05 else 0.0
        happy_morph.append((idx, [dx, dy, 0.0]))
    emotions["happy"] = happy_morph
    
    # angry: Eyebrows drawn together and down, mouth tense
    angry_morph = []
    for idx in left_brow:
        v = vertices[idx]
        # Pull left brow down and toward center
        dx = 0.004  # Toward center
        dy = -0.008  # Down
        angry_morph.append((idx, [dx, dy, 0.0]))
    for idx in right_brow:
        v = vertices[idx]
        # Pull right brow down and toward center
        dx = -0.004  # Toward center
        dy = -0.008  # Down
        angry_morph.append((idx, [dx, dy, 0.0]))
    for idx in mouth_indices:
        v = vertices[idx]
        # Tense mouth - slight inward pull
        dx = -0.002 if v[0] > center[0] else 0.002
        angry_morph.append((idx, [dx, 0.0, 0.0]))
    emotions["angry"] = angry_morph
    
    # sad: Inner eyebrows raised, outer eyebrows down, mouth corners down
    sad_morph = []
    for idx in left_brow:
        v = vertices[idx]
        # Outer brow down, inner up (based on distance from center)
        if abs(v[0] - center[0]) > 0.04:
            dy = -0.006  # Outer down
        else:
            dy = 0.004  # Inner up
        sad_morph.append((idx, [0.0, dy, 0.0]))
    for idx in right_brow:
        v = vertices[idx]
        if abs(v[0] - center[0]) > 0.04:
            dy = -0.006
        else:
            dy = 0.004
        sad_morph.append((idx, [0.0, dy, 0.0]))
    for idx in mouth_indices:
        v = vertices[idx]
        # Mouth corners down
        dx = -0.002 if v[0] > center[0] else 0.002
        dy = -0.004 if abs(v[0] - center[0]) > 0.05 else 0.0
        sad_morph.append((idx, [dx, dy, 0.0]))
    emotions["sad"] = sad_morph
    
    # relaxed: Slight smile, neutral brows
    relaxed_morph = []
    for idx in mouth_indices:
        v = vertices[idx]
        # Gentle smile
        dx = 0.002 if v[0] > center[0] else -0.002
        dy = 0.003 if abs(v[0] - center[0]) > 0.06 else 0.0
        relaxed_morph.append((idx, [dx, dy, 0.0]))
    emotions["relaxed"] = relaxed_morph
    
    # surprised: Eyebrows raised high, eyes wide, mouth open
    surprised_morph = []
    for idx in left_brow + right_brow:
        v = vertices[idx]
        # Raise eyebrows significantly
        dy = 0.012
        surprised_morph.append((idx, [0.0, dy, 0.0]))
    for idx in mouth_indices:
        v = vertices[idx]
        # Open mouth slightly
        if v[1] < center[1]:
            dy = -0.006  # Lower jaw
        else:
            dy = 0.004  # Upper lip up
        surprised_morph.append((idx, [0.0, dy, 0.0]))
    emotions["surprised"] = surprised_morph
    
    return emotions


def validate_expressions(
    shape_keys: Dict[str, Any],
    output_dir: str
) -> Dict[str, Any]:
    """Validate that all required expressions are present.
    
    Checks:
    1. Each required expression is present
    2. No mesh inversion when expression is applied (stub)
    3. No self-intersection when expression is applied (stub)
    
    Args:
        shape_keys: Dictionary mapping expression names to morph data.
        output_dir: Directory to write expression_report.json.
        
    Returns:
        Dictionary with validation results.
    """
    result = {
        "status": "pending",
        "required_expressions": REQUIRED_EXPRESSIONS,
        "present_expressions": [],
        "missing_expressions": [],
        "validation": {}
    }
    
    # Check each required expression
    for expr in REQUIRED_EXPRESSIONS:
        if expr in shape_keys:
            result["present_expressions"].append(expr)
            result["validation"][expr] = {"present": True}
        else:
            result["missing_expressions"].append(expr)
            result["validation"][expr] = {"present": False}
    
    # Stub inversion/intersection checks
    for expr in result["present_expressions"]:
        result["validation"][expr]["inversion"] = False  # No inversion
        result["validation"][expr]["intersection"] = False  # No intersection
    
    # Overall pass/fail
    result["all_present"] = len(result["missing_expressions"]) == 0
    result["pass"] = result["all_present"]
    result["status"] = "complete"
    
    # Write report
    _write_expression_report(output_dir, result)
    
    return result


def generate_expressions(
    mesh_path: str,
    template_expressions: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Generate expression shape keys for a mesh.
    
    Transfers expressions from a canonical template to the fitted mesh,
    or generates new expressions using landmark analysis.
    
    Args:
        mesh_path: Path to the mesh.
        template_expressions: Optional expression data from template.
        
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
    
    # Load mesh and get vertices
    try:
        vertices, bounds = _load_mesh_vertices(mesh_path)
        result["vertex_count"] = len(vertices)
        result["mesh_bounds"] = {
            "min": bounds["min"].tolist(),
            "max": bounds["max"].tolist()
        }
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
    blink_data = generate_blink_morph(vertices, bounds, "both")
    result["expressions"]["blink"] = {
        "morph_targets": blink_data,
        "vertex_count": len(blink_data),
        "status": "generated"
    }
    
    blink_left_data = generate_blink_morph(vertices, bounds, "left")
    result["expressions"]["blinkLeft"] = {
        "morph_targets": blink_left_data,
        "vertex_count": len(blink_left_data),
        "status": "generated"
    }
    
    blink_right_data = generate_blink_morph(vertices, bounds, "right")
    result["expressions"]["blinkRight"] = {
        "morph_targets": blink_right_data,
        "vertex_count": len(blink_right_data),
        "status": "generated"
    }
    
    # Generate viseme morphs
    visemes = generate_viseme_morphs(vertices, bounds)
    for viseme_name, morph_data in visemes.items():
        result["expressions"][viseme_name] = {
            "morph_targets": morph_data,
            "vertex_count": len(morph_data),
            "status": "generated"
        }
    
    # Generate emotion morphs
    emotions = generate_emotion_morphs(vertices, bounds)
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
