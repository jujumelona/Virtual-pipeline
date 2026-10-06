"""Accessory subpackage for VTuber Pipeline.

This module provides utilities for processing and attaching accessories
to VTuber avatars.
"""

from vtuber_pipeline.accessory.reconstruction import reconstruct_accessories
from vtuber_pipeline.accessory.attachment import generate_attachment_config
from vtuber_pipeline.accessory.batch import batch_reconstruct_accessories
from vtuber_pipeline.accessory.normalize import normalize_glb
from vtuber_pipeline.accessory.anchors import generate_anchor_manifest, ANCHOR_POINTS
from vtuber_pipeline.accessory.fitting import fit_accessory
from vtuber_pipeline.accessory.collision import check_collision
from vtuber_pipeline.accessory.physics import add_physics_chain
from vtuber_pipeline.accessory.bake import bake_accessories
from vtuber_pipeline.accessory.build import AccessoryPipeline

__all__ = [
    "reconstruct_accessories",
    "generate_attachment_config",
    "batch_reconstruct_accessories",
    "normalize_glb",
    "generate_anchor_manifest",
    "ANCHOR_POINTS",
    "fit_accessory",
    "check_collision",
    "add_physics_chain",
    "bake_accessories",
    "AccessoryPipeline",
]
