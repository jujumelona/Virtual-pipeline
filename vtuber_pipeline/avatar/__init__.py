"""Avatar subpackage for VTuber Pipeline."""

from vtuber_pipeline.avatar.face_detector import AnimeFaceDetector
from vtuber_pipeline.avatar.reconstruction import reconstruct_avatar
from vtuber_pipeline.avatar.template_fitting import fit_template
from vtuber_pipeline.avatar.rigging import rig_avatar
from vtuber_pipeline.avatar.vrm_export import export_vrm

__all__ = [
    "AnimeFaceDetector",
    "reconstruct_avatar",
    "fit_template",
    "rig_avatar",
    "export_vrm",
]
