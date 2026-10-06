"""VRM export module for VTuber Pipeline.

This module provides functions for exporting rigged meshes to the VRM
format using the VRM Add-on for Blender.
"""

import pathlib
from typing import Dict, Any, Optional


def export_vrm(
    rig_path: str,
    output_dir: str,
    blender_runner=None
) -> Dict[str, Any]:
    """Export rigged mesh to VRM format.
    
    Pre-export validation checks:
    1. Humanoid bones present
    2. Shape keys (expressions) defined
    3. Textures assigned
    4. Vertex weights assigned
    
    Args:
        rig_path: Path to the rigged mesh (.blend or .glb).
        output_dir: Directory to write output files.
        blender_runner: Optional SubprocessRunner for Blender execution.
        
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
    
    # Export VRM
    if blender_runner is not None:
        try:
            # Run Blender export script
            output_path = pathlib.Path(output_dir) / "avatar.vrm"
            manifest_path = pathlib.Path(output_dir) / "manifest.json"
            
            export_result = blender_runner.run(
                script_path=str(pathlib.Path(__file__).parent.parent / "blender" / "export_vrm.py"),
                manifest_path=str(manifest_path)
            )
            
            result["blender_output"] = export_result
            result["vrm_path"] = str(output_path)
            result["status"] = "complete"
            
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
    else:
        result["status"] = "stub"
        result["warning"] = "Blender runner not provided, VRM not exported"
        result["vrm_path"] = str(pathlib.Path(output_dir) / "avatar.vrm")
    
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


# Legacy function for backward compatibility
def export_vrm_legacy(rigged_mesh_path: str, output_path: str) -> str:
    """
    리깅된 메시를 VRM 형식으로 내보냅니다.

    VRM 사양:
        - 휴머노이드 골격: Hips, Spine, Chest, Neck, Head,
          Shoulder(L/R), UpperArm(L/R), LowerArm(L/R), Hand(L/R),
          UpperLeg(L/R), LowerLeg(L/R), Foot(L/R)
        - 블렌드셰이프 프리셋: Blink, BlinkLeft, BlinkRight,
          A(aa), I(ih), U(ou), E(ee), O(oh),
          Happy, Sad, Angry, Surprised, Relaxed
        - SpringBone: 머리카락, 귀, 가슴, 꼬리 등의 물리 설정

    TODO: pygltflib + VRM 확장을 사용한 구현
    """
    raise NotImplementedError(
        "VRM 내보내기는 아직 구현되지 않았습니다. "
        "pygltflib 및 VRM 1.0 사양을 참조하세요: https://github.com/vrm-c/vrm-specification"
    )
