"""Avatar subpackage for VTuber Pipeline.

This module provides the complete avatar creation pipeline from input
image validation through VRM export and validation.
"""

from vtuber_pipeline.avatar.face_detector import AnimeFaceDetector
from vtuber_pipeline.avatar.reconstruction import reconstruct_avatar
from vtuber_pipeline.avatar.template_fitting import fit_template, FittingObjective
from vtuber_pipeline.avatar.rigging import rig_avatar
from vtuber_pipeline.avatar.vrm_export import export_vrm, validate_for_vrm
from vtuber_pipeline.avatar.input_gate import validate_input
from vtuber_pipeline.avatar.reference_analysis import analyze_reference
from vtuber_pipeline.avatar.camera_alignment import align_camera
from vtuber_pipeline.avatar.deformation_transfer import transfer_deformation
from vtuber_pipeline.avatar.texture_transfer import transfer_texture
from vtuber_pipeline.avatar.hair import extract_hair
from vtuber_pipeline.avatar.clothing import extract_clothing
from vtuber_pipeline.avatar.expressions import validate_expressions, REQUIRED_EXPRESSIONS
from vtuber_pipeline.avatar.gaze import configure_gaze, GazeConfig
from vtuber_pipeline.avatar.springbone import generate_springbone_config, SPRING_BONE_PRESETS
from vtuber_pipeline.avatar.materials import configure_materials, MATERIAL_GROUPS
from vtuber_pipeline.avatar.validator import validate_vrm, VRMValidator
from vtuber_pipeline.avatar.build import AvatarPipeline, build_avatar

__all__ = [
    "AnimeFaceDetector",
    "reconstruct_avatar",
    "fit_template",
    "FittingObjective",
    "rig_avatar",
    "export_vrm",
    "validate_for_vrm",
    "validate_input",
    "analyze_reference",
    "align_camera",
    "transfer_deformation",
    "transfer_texture",
    "extract_hair",
    "extract_clothing",
    "validate_expressions",
    "REQUIRED_EXPRESSIONS",
    "configure_gaze",
    "GazeConfig",
    "generate_springbone_config",
    "SPRING_BONE_PRESETS",
    "configure_materials",
    "MATERIAL_GROUPS",
    "validate_vrm",
    "VRMValidator",
    "AvatarPipeline",
    "build_avatar",
]
