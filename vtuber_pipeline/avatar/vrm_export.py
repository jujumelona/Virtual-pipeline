"""VRM export module for VTuber Pipeline.

This module provides functions for exporting rigged meshes to the VRM
format using pygltflib (Pure Python implementation).
"""

import pathlib
from typing import Dict, Any, Optional

# Import the new VRM builder
from vtuber_pipeline.avatar.vrm_builder import export_vrm as _export_vrm_pure


def export_vrm(
    rig_path: str,
    output_dir: str,
    expressions: Optional[Dict[str, Any]] = None,
    bone_mapping: Optional[Dict[str, int]] = None,
    commercial_usage: str = "corporation",
    springbone_config: Optional[Dict[str, Any]] = None,
    gaze_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Export rigged mesh to VRM 1.0 format.
    
    Uses pure Python implementation with pygltflib.
    Pre-export validation checks:
    1. Humanoid bones present
    2. Shape keys (expressions) defined
    3. Textures assigned
    4. Vertex weights assigned
    
    Args:
        rig_path: Path to the rigged mesh (.glb or .gltf).
        output_dir: Directory to write output files.
        expressions: Optional dict of expression morph data.
        bone_mapping: Optional dict mapping VRM bone names to node indices.
        commercial_usage: VRM 1.0 commercial usage policy.
        springbone_config: Optional normalized VRMC_springBone config.
        gaze_config: Optional VRM look-at configuration.
        
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
    pre_validate = _validate_for_vrm(rig_path, expressions=expressions)
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
            bone_mapping=bone_mapping,
            commercial_usage=commercial_usage,
            springbone_config=springbone_config,
            look_at_config=gaze_config,
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
    expressions: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Validate the actual rigged GLB before VRM extension injection."""
    result = {"valid": True, "errors": [], "warnings": [], "checks": {}}
    path = pathlib.Path(mesh_path)
    if not path.is_file() or path.stat().st_size == 0:
        result["valid"] = False
        result["errors"].append(f"Rigged GLB missing or empty: {mesh_path}")
        return result

    try:
        from pygltflib import GLTF2
        gltf = GLTF2().load(str(path))
        node_names = {node.name for node in (gltf.nodes or []) if node.name}
        required_bones = {
            "hips", "spine", "chest", "neck", "head",
            "leftShoulder", "leftUpperArm", "leftLowerArm", "leftHand",
            "rightShoulder", "rightUpperArm", "rightLowerArm", "rightHand",
            "leftUpperLeg", "leftLowerLeg", "leftFoot",
            "rightUpperLeg", "rightLowerLeg", "rightFoot",
        }
        missing = sorted(required_bones - node_names)
        result["checks"]["humanoid_bones"] = not missing
        if missing:
            result["errors"].append(f"Missing bones: {missing}")

        has_skin = bool(gltf.skins)
        result["checks"]["skin"] = has_skin
        if not has_skin:
            result["errors"].append("Rigged GLB has no skin")

        primitives = [
            primitive
            for mesh in (gltf.meshes or [])
            for primitive in (mesh.primitives or [])
        ]
        has_joint_weights = any(
            getattr(p.attributes, "JOINTS_0", None) is not None and
            getattr(p.attributes, "WEIGHTS_0", None) is not None
            for p in primitives
        )
        result["checks"]["weights"] = has_joint_weights
        if not has_joint_weights:
            result["errors"].append("Rigged GLB has no JOINTS_0/WEIGHTS_0 attributes")

        has_texture = bool(gltf.images and gltf.textures and gltf.materials)
        result["checks"]["textures"] = has_texture
        if not has_texture:
            result["errors"].append("Rigged GLB has no embedded avatar texture/material")

        required_expr = {
            "blink", "blinkLeft", "blinkRight",
            "aa", "ih", "ou", "ee", "oh",
            "happy", "angry", "sad", "relaxed", "surprised",
        }
        present_expr = set((expressions or {}).keys())
        missing_expr = sorted(required_expr - present_expr)
        result["checks"]["expressions"] = not missing_expr
        if missing_expr:
            result["errors"].append(f"Missing expressions: {missing_expr}")

    except Exception as exc:
        result["valid"] = False
        result["errors"].append(f"Failed to inspect rigged GLB: {exc}")
        return result

    result["valid"] = all(result["checks"].values()) and not result["errors"]
    return result

def _write_vrm_export_report(output_dir: str, result: Dict[str, Any]) -> None:
    """Write vrm_export_report.json to output directory."""
    from vtuber_pipeline.core.utils import save_json
    
    output_path = pathlib.Path(output_dir) / "vrm_export_report.json"
    save_json(result, str(output_path))
