"""Accessory pipeline public API."""

from vtuber_pipeline.accessory.reconstruction import reconstruct_accessories
from vtuber_pipeline.accessory.normalize import normalize_glb
from vtuber_pipeline.accessory.anchors import generate_anchor_manifest, ANCHOR_POINTS
from vtuber_pipeline.accessory.fitting import fit_accessory
from vtuber_pipeline.accessory.collision import check_collision, resolve_collision
from vtuber_pipeline.accessory.bake import bake_accessories
from vtuber_pipeline.accessory.build import AccessoryPipeline

__all__ = [
    "reconstruct_accessories",
    "normalize_glb",
    "generate_anchor_manifest",
    "ANCHOR_POINTS",
    "fit_accessory",
    "check_collision",
    "resolve_collision",
    "bake_accessories",
    "AccessoryPipeline",
]
