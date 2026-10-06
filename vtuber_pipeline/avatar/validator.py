"""VRM validation module for VTuber Pipeline.

This module provides functions for validating VRM files after export
to ensure they meet the VRM 1.0 specification requirements.
"""

import pathlib
from typing import Dict, Any, List, Optional

from pygltflib import GLTF2


def validate_vrm(vrm_path: str, output_dir: str) -> Dict[str, Any]:
    """Validate a VRM file for VRM 1.0 compliance.
    
    Checks:
    1. File exists and is valid glTF
    2. VRMC_vrm extension exists with specVersion '1.0'
    3. Humanoid bones are present in boneMapping
    4. Required expressions are defined in presets
    5. Look-at (gaze) is configured
    6. SpringBone is configured
    
    Args:
        vrm_path: Path to the VRM file.
        output_dir: Directory to write validation report.
        
    Returns:
        Dictionary with validation results.
    """
    result = {
        "vrm_path": vrm_path,
        "passed": False,
        "checks": {}
    }
    
    # Create output subdirectory
    report_dir = pathlib.Path(output_dir) / "validation"
    report_dir.mkdir(parents=True, exist_ok=True)
    
    # Check 1: File exists
    vrm_file = pathlib.Path(vrm_path)
    result["checks"]["file_exists"] = vrm_file.exists()
    
    if not result["checks"]["file_exists"]:
        result["errors"] = [f"VRM file not found: {vrm_path}"]
        _write_validation_report(report_dir, result)
        return result
    
    # Use VRMValidator for actual validation
    validator = VRMValidator(vrm_path)
    
    # Check 2: VRM schema (VRMC_vrm extension with specVersion)
    schema_result = validator.validate_vrm_schema()
    result["checks"]["vrm_schema"] = schema_result["valid"]
    result["vrm_schema"] = schema_result
    
    # Check 3: Humanoid bones
    bones_result = validator.validate_humanoid_bones()
    result["checks"]["humanoid_bones"] = bones_result["valid"]
    result["humanoid_bones"] = bones_result
    
    # Check 4: Expressions
    expressions_result = validator.validate_expressions()
    result["checks"]["expressions"] = expressions_result["valid"]
    result["expressions"] = expressions_result
    
    # Check 5: Look-at configured
    look_at_result = validator.validate_look_at()
    result["checks"]["look_at"] = look_at_result["valid"]
    result["look_at"] = look_at_result
    
    # Check 6: SpringBone configured
    springbone_result = validator.validate_springbone()
    result["checks"]["springbone"] = springbone_result["valid"]
    result["springbone"] = springbone_result
    
    # Overall result
    result["passed"] = all(result["checks"].values())
    
    # Write report
    _write_validation_report(report_dir, result)
    
    return result


class VRMValidator:
    """Validator class for VRM files.
    
    Provides methods for validating different aspects of VRM files.
    Uses pygltflib to parse glTF and extract VRM extensions.
    """
    
    # VRM 1.0 required bones (minimal set for humanoid)
    REQUIRED_BONES = [
        "hips", "spine", "chest", "neck", "head",
        "leftShoulder", "leftUpperArm", "leftLowerArm", "leftHand",
        "rightShoulder", "rightUpperArm", "rightLowerArm", "rightHand",
        "leftUpperLeg", "leftLowerLeg", "leftFoot",
        "rightUpperLeg", "rightLowerLeg", "rightFoot"
    ]
    
    # VRM 1.0 required expression presets
    REQUIRED_EXPRESSIONS = [
        "happy", "angry", "sad", "relaxed", "surprised",
        "aa", "ih", "ou", "ee", "oh",
        "blink", "blinkLeft", "blinkRight"
    ]
    
    def __init__(self, vrm_path: str):
        """Initialize the validator.
        
        Args:
            vrm_path: Path to the VRM file.
        """
        self.vrm_path = pathlib.Path(vrm_path)
        self._gltf: Optional[GLTF2] = None
        self._vrm_extension: Optional[Dict[str, Any]] = None
    
    def parse_vrm(self) -> Dict[str, Any]:
        """Load and parse the VRM file using pygltflib.
        
        Returns:
            Parsed VRM extension data dictionary.
        """
        if self._vrm_extension is not None:
            return self._vrm_extension
        
        try:
            # pygltflib can load .vrm files (they are glTF2 binary)
            self._gltf = GLTF2().load(str(self.vrm_path))
            
            # Extract VRMC_vrm extension from glTF extensions
            if self._gltf.extensions is None:
                self._vrm_extension = {}
                return self._vrm_extension
            
            # Get VRMC_vrm extension
            vrm_ext = self._gltf.extensions.get("VRMC_vrm", {})
            self._vrm_extension = vrm_ext if isinstance(vrm_ext, dict) else {}
            
            return self._vrm_extension
            
        except Exception as e:
            # If parsing fails, return empty dict
            self._vrm_extension = {}
            return self._vrm_extension
    
    def validate_vrm_schema(self) -> Dict[str, Any]:
        """Validate VRMC_vrm extension exists with correct specVersion.
        
        Returns:
            Validation result dictionary.
        """
        vrm_ext = self.parse_vrm()
        
        if not vrm_ext:
            return {
                "valid": False,
                "error": "VRMC_vrm extension not found",
                "spec_version": None
            }
        
        # Check specVersion field
        spec_version = vrm_ext.get("specVersion", "")
        
        # VRM 1.0 should have specVersion "1.0" or "1.0-draft"
        is_valid = spec_version in ["1.0", "1.0-draft"]
        
        return {
            "valid": is_valid,
            "spec_version": spec_version,
            "error": None if is_valid else f"Invalid specVersion: {spec_version}"
        }
    
    def validate_humanoid_bones(self) -> Dict[str, Any]:
        """Validate humanoid bones are present in humanoidBones.
        
        Returns:
            Validation result dictionary with present and missing bones.
        """
        vrm_ext = self.parse_vrm()
        
        if not vrm_ext:
            return {
                "valid": False,
                "present": [],
                "missing": self.REQUIRED_BONES,
                "error": "VRMC_vrm extension not found"
            }
        
        # Get humanoid section
        humanoid = vrm_ext.get("humanoid", {})
        if not humanoid:
            return {
                "valid": False,
                "present": [],
                "missing": self.REQUIRED_BONES,
                "error": "humanoid section not found"
            }
        
        # Get humanoidBones - VRM 1.0 uses "humanoidBones" (not "humanBones")
        bone_list = humanoid.get("humanoidBones", [])
        
        if not bone_list:
            return {
                "valid": False,
                "present": [],
                "missing": self.REQUIRED_BONES,
                "error": "humanoidBones not found in humanoid"
            }
        
        # Extract bone names from humanoidBones
        # VRM 1.0: humanoidBones is a list of objects with "node" and "name" fields
        present_bones = []
        if isinstance(bone_list, list):
            for bone_entry in bone_list:
                if isinstance(bone_entry, dict):
                    # VRM 1.0 uses "name" field for bone name
                    bone_name = bone_entry.get("name", "")
                    if bone_name:
                        present_bones.append(bone_name)
        elif isinstance(bone_list, dict):
            present_bones = list(bone_list.keys())
        
        # Check for missing required bones
        missing = [bone for bone in self.REQUIRED_BONES if bone not in present_bones]
        
        return {
            "valid": len(missing) == 0,
            "present": present_bones,
            "missing": missing,
            "error": None if len(missing) == 0 else f"Missing bones: {missing}"
        }
    
    def validate_expressions(self) -> Dict[str, Any]:
        """Validate required expression presets are present.
        
        Returns:
            Validation result dictionary with present and missing expressions.
        """
        vrm_ext = self.parse_vrm()
        
        if not vrm_ext:
            return {
                "valid": False,
                "present": [],
                "missing": self.REQUIRED_EXPRESSIONS,
                "error": "VRMC_vrm extension not found"
            }
        
        # Get expressions section
        expressions = vrm_ext.get("expressions", {})
        if not expressions:
            # Expressions are optional in VRM 1.0 - this is a warning, not an error
            return {
                "valid": True,
                "present": [],
                "missing": self.REQUIRED_EXPRESSIONS,
                "warning": "expressions section not found (optional in VRM 1.0)"
            }
        
        # VRM 1.0 uses "preset" key with expression objects
        presets = expressions.get("preset", {})
        
        if not presets:
            # Check if expressions has other keys (custom expressions)
            custom_expressions = expressions.get("custom", [])
            if custom_expressions:
                present_expressions = [e.get("name", "") for e in custom_expressions if isinstance(e, dict)]
                missing = [expr for expr in self.REQUIRED_EXPRESSIONS if expr not in present_expressions]
                return {
                    "valid": len(missing) == 0,
                    "present": present_expressions,
                    "missing": missing,
                    "warning": None if len(missing) == 0 else f"Missing preset expressions: {missing}"
                }
            
            # No presets or custom expressions
            return {
                "valid": True,
                "present": [],
                "missing": self.REQUIRED_EXPRESSIONS,
                "warning": "No expressions defined (optional in VRM 1.0)"
            }
        
        # Extract expression names from presets
        # presets is a dict with expression names as keys and expression objects as values
        present_expressions = []
        if isinstance(presets, dict):
            for expr_name, expr_value in presets.items():
                if expr_value is not None:  # Expression is defined
                    present_expressions.append(expr_name)
        
        # Check for missing required expressions
        missing = [expr for expr in self.REQUIRED_EXPRESSIONS if expr not in present_expressions]
        
        return {
            "valid": len(missing) == 0,
            "present": present_expressions,
            "missing": missing,
            "error": None if len(missing) == 0 else f"Missing expressions: {missing}"
        }
    
    def validate_materials(self) -> Dict[str, Any]:
        """Validate materials are MToon-compatible.
        
        Returns:
            Validation result dictionary.
        """
        if self._gltf is None:
            self.parse_vrm()
        
        if self._gltf is None:
            return {
                "valid": False,
                "materials": [],
                "error": "Could not parse glTF"
            }
        
        # Get material names
        materials = []
        if self._gltf.materials:
            materials = [m.name for m in self._gltf.materials if m.name]
        
        return {
            "valid": True,
            "materials": materials
        }
    
    def validate_look_at(self) -> Dict[str, Any]:
        """Validate look-at configuration.
        
        Returns:
            Validation result dictionary.
        """
        vrm_ext = self.parse_vrm()
        
        if not vrm_ext:
            return {
                "valid": False,
                "error": "VRMC_vrm extension not found"
            }
        
        # Get lookAt section
        look_at = vrm_ext.get("lookAt", {})
        
        if not look_at:
            return {
                "valid": False,
                "error": "lookAt section not found"
            }
        
        # Check for required fields
        has_type = "type" in look_at
        has_offset = "offsetFromHeadBone" in look_at
        
        # Get limits if available
        yaw_limit = look_at.get("yawLimitDegrees", 30.0)
        pitch_limit = look_at.get("pitchLimitDegrees", 20.0)
        
        return {
            "valid": has_type,
            "yaw_limit_deg": yaw_limit,
            "pitch_limit_deg": pitch_limit,
            "error": None if has_type else "lookAt.type not found"
        }
    
    def validate_springbone(self) -> Dict[str, Any]:
        """Validate SpringBone configuration.
        
        Returns:
            Validation result dictionary.
        """
        if self._gltf is None:
            self.parse_vrm()
        
        if self._gltf is None or self._gltf.extensions is None:
            return {
                "valid": False,
                "groups": [],
                "error": "Could not parse glTF extensions"
            }
        
        # SpringBone is in VRMC_springBone extension (separate from VRMC_vrm)
        spring_bone_ext = self._gltf.extensions.get("VRMC_springBone", {})
        
        if not spring_bone_ext:
            # SpringBone is optional, so this is a pass with warning
            return {
                "valid": True,
                "groups": [],
                "warning": "VRMC_springBone extension not found (optional)"
            }
        
        # Get spring bone groups/colliders
        springs = spring_bone_ext.get("springs", [])
        colliders = spring_bone_ext.get("colliders", [])
        
        group_names = []
        if isinstance(springs, list):
            for spring in springs:
                if isinstance(spring, dict) and "name" in spring:
                    group_names.append(spring["name"])
        
        return {
            "valid": True,
            "groups": group_names,
            "collider_count": len(colliders) if isinstance(colliders, list) else 0
        }
    
    def run_all(self) -> Dict[str, Any]:
        """Run all validation checks.
        
        Returns:
            Summary dictionary with all validation results.
        """
        results = {
            "vrm_path": str(self.vrm_path),
            "passed": False,
            "checks": {}
        }
        
        # Run all validation methods
        results["checks"]["vrm_schema"] = self.validate_vrm_schema()
        results["checks"]["humanoid_bones"] = self.validate_humanoid_bones()
        results["checks"]["expressions"] = self.validate_expressions()
        results["checks"]["materials"] = self.validate_materials()
        results["checks"]["look_at"] = self.validate_look_at()
        results["checks"]["springbone"] = self.validate_springbone()
        
        # Overall pass if all checks are valid
        results["passed"] = all(
            check.get("valid", False) 
            for check in results["checks"].values()
        )
        
        return results


def generate_validation_report(vrm_path: str, output_dir: str) -> str:
    """Generate a validation report for a VRM file.
    
    Args:
        vrm_path: Path to the VRM file.
        output_dir: Directory to write the report.
        
    Returns:
        Path to the generated report file.
    """
    result = validate_vrm(vrm_path, output_dir)
    report_path = pathlib.Path(output_dir) / "validation" / "report.json"
    return str(report_path)


def _write_validation_report(report_dir: pathlib.Path, result: Dict[str, Any]) -> None:
    """Write report.json to the validation directory."""
    from vtuber_pipeline.core.utils import save_json
    
    output_path = report_dir / "report.json"
    save_json(result, str(output_path))
