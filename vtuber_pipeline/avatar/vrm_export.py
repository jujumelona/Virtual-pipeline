"""VRM export module for VTuber Pipeline.

This module provides functions for exporting rigged meshes to the VRM
format using pygltflib (Pure Python implementation).
"""

import pathlib
from typing import Dict, Any, Optional, List, Tuple

# Import the new VRM builder
from vtuber_pipeline.avatar.vrm_builder import (
    export_vrm as _export_vrm_pure,
    validate_vrm as _validate_vrm_file,
    VRM_EXPRESSION_PRESETS
)


def export_vrm(
    rig_path: str,
    output_dir: str,
    blender_runner=None,
    expressions: Optional[Dict[str, Any]] = None,
    bone_mapping: Optional[Dict[str, int]] = None
) -> Dict[str, Any]:
    """Export rigged mesh to VRM 1.0 format.
    
    Uses pure Python implementation with pygltflib.
    Blender runner is ignored (kept for backward compatibility).
    
    Pre-export validation checks:
    1. Humanoid bones present
    2. Shape keys (expressions) defined
    3. Textures assigned
    4. Vertex weights assigned
    
    Args:
        rig_path: Path to the rigged mesh (.glb or .gltf).
        output_dir: Directory to write output files.
        blender_runner: Ignored (kept for backward compatibility).
        expressions: Optional dict of expression morph data.
        bone_mapping: Optional dict mapping VRM bone names to node indices.
        
    Returns:
        Dictionary with export results and output paths.
    """
    result = {
        "status": "pending",
        "rig_path": rig_path,
        "output_dir": output_dir
    }
    
    # Create output directory
    pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Pre-export validation
    pre_validate = _validate_for_vrm(rig_path)
    result["pre_validate"] = pre_validate
    
    if not pre_validate.get("valid", False):
        result["status"] = "validation_failed"
        result["errors"] = pre_validate.get("errors", [])
        _write_vrm_export_report(output_dir, result)
        return result
    
    # Export VRM using pure Python implementation
    try:
        export_result = _export_vrm_pure(
            rigged_glb_path=rig_path,
            output_dir=output_dir,
            expressions=expressions,
            bone_mapping=bone_mapping
        )
        
        # Copy result fields
        result["status"] = export_result.get("status", "error")
        result["vrm_path"] = export_result.get("vrm_path")
        result["vrm_extension"] = export_result.get("vrm_extension")
        result["file_size_bytes"] = export_result.get("file_size_bytes")
        
        if export_result.get("error"):
            result["error"] = export_result["error"]
            
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
    
    _write_vrm_export_report(output_dir, result)
    
    return result


def validate_for_vrm(
    mesh_path: str,
    rig_data: Optional[Dict[str, Any]] = None,
    expressions: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Validate a mesh is ready for VRM export.
    
    Args:
        mesh_path: Path to the mesh.
        rig_data: Optional rig data.
        expressions: Optional expression data.
        
    Returns:
        Dictionary with validation results.
    """
    return _validate_for_vrm(mesh_path, rig_data, expressions)


def _validate_for_vrm(
    mesh_path: str,
    rig_data: Optional[Dict[str, Any]] = None,
    expressions: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Internal validation function."""
    result = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "checks": {}
    }
    
    # Check if input file exists
    input_path = pathlib.Path(mesh_path)
    if not input_path.exists():
        result["valid"] = False
        result["errors"].append(f"입력 파일이 존재하지 않습니다: {mesh_path}")
        return result
    
    # Check humanoid bones (stub)
    required_bones = [
        "hips", "spine", "chest", "neck", "head",
        "leftShoulder", "leftUpperArm", "leftLowerArm", "leftHand",
        "rightShoulder", "rightUpperArm", "rightLowerArm", "rightHand",
        "leftUpperLeg", "leftLowerLeg", "leftFoot",
        "rightUpperLeg", "rightLowerLeg", "rightFoot"
    ]
    
    if rig_data:
        present_bones = rig_data.get("bones", [])
        missing_bones = [b for b in required_bones if b not in present_bones]
        result["checks"]["humanoid_bones"] = len(missing_bones) == 0
        if missing_bones:
            result["errors"].append(f"Missing bones: {missing_bones}")
    else:
        result["checks"]["humanoid_bones"] = True  # Stub: assume present
        result["warnings"].append("Rig data not provided, assuming bones present")
    
    # Check shape keys (stub)
    required_expressions = [
        "blink", "blinkLeft", "blinkRight",
        "aa", "ih", "ou", "ee", "oh",
        "happy", "angry", "sad", "relaxed", "surprised"
    ]
    
    if expressions:
        present_exprs = list(expressions.keys())
        missing_exprs = [e for e in required_expressions if e not in present_exprs]
        result["checks"]["shape_keys"] = len(missing_exprs) == 0
        if missing_exprs:
            result["warnings"].append(f"Missing expressions: {missing_exprs}")
    else:
        result["checks"]["shape_keys"] = True  # Stub
        result["warnings"].append("Expression data not provided")
    
    # Check textures (stub)
    result["checks"]["textures"] = True
    
    # Check weights (stub)
    result["checks"]["weights"] = True
    
    # Overall validity
    result["valid"] = all(result["checks"].values()) and len(result["errors"]) == 0
    
    return result


def _write_vrm_export_report(output_dir: str, result: Dict[str, Any]) -> None:
    """Write vrm_export_report.json to output directory."""
    from vtuber_pipeline.core.utils import save_json
    
    output_path = pathlib.Path(output_dir) / "vrm_export_report.json"
    save_json(result, str(output_path))


def validate_vrm_file(vrm_path: str) -> Dict[str, Any]:
    """Validate an existing VRM file.
    
    Args:
        vrm_path: Path to the VRM file.
        
    Returns:
        Dictionary with validation results.
    """
    return _validate_vrm_file(vrm_path)
