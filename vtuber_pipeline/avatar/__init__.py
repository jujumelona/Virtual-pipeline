"""Public avatar pipeline API."""

from vtuber_pipeline.avatar.face_detector import AnimeFaceDetector
from vtuber_pipeline.avatar.reconstruction import reconstruct_avatar
from vtuber_pipeline.avatar.template_fitting import fit_template, FittingObjective
from vtuber_pipeline.avatar.template_mesh import get_template_path, create_canonical_template_from_makehuman
from vtuber_pipeline.avatar.texture_transfer import transfer_texture
from vtuber_pipeline.avatar.rigging import rig_avatar
from vtuber_pipeline.avatar.expressions import generate_expressions, validate_expressions, REQUIRED_EXPRESSIONS
from vtuber_pipeline.avatar.gaze import configure_gaze, GazeConfig
from vtuber_pipeline.avatar.springbone import generate_springbone_config, SPRING_BONE_PRESETS
from vtuber_pipeline.avatar.vrm_export import export_vrm
from vtuber_pipeline.avatar.validator import validate_vrm, VRMValidator
from vtuber_pipeline.avatar.build import AvatarPipeline, build_avatar

__all__ = [
    "AnimeFaceDetector", "reconstruct_avatar", "fit_template", "FittingObjective",
    "get_template_path", "create_canonical_template_from_makehuman",
    "transfer_texture", "rig_avatar", "generate_expressions",
    "validate_expressions", "REQUIRED_EXPRESSIONS", "configure_gaze", "GazeConfig",
    "generate_springbone_config", "SPRING_BONE_PRESETS", "export_vrm",
    "validate_vrm", "VRMValidator", "AvatarPipeline", "build_avatar",
]
