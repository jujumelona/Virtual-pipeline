"""Expression shape key generation and validation for VRM avatars.

This module provides functions for defining, generating, and validating
VRM expression shape keys (blend shapes) for VTuber avatars.
"""

import pathlib
from typing import Dict, Any, List, Optional


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
    """
    result = {
        "status": "stub",
        "expressions": {},
        "mesh_path": mesh_path
    }
    
    # Initialize with empty morph targets
    for expr in REQUIRED_EXPRESSIONS:
        result["expressions"][expr] = {
            "morph_targets": [],
            "weights": [],
            "status": "stub"
        }
    
    result["warning"] = "Expression generation not implemented, using stub values"
    
    return result


def _write_expression_report(output_dir: str, result: Dict[str, Any]) -> None:
    """Write expression_report.json to output directory."""
    from vtuber_pipeline.core.utils import save_json
    
    pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)
    output_path = pathlib.Path(output_dir) / "expression_report.json"
    save_json(result, str(output_path))
