"""Separate re-riggable hairstyles added to a neutral head/body rig."""
from __future__ import annotations
from tools.modular_avatar_pack import inspect_image,build_modular_2d_assets

def inspect_hair_image(filename:str)->dict:
    return inspect_image(filename,"hair")

def build_haired_2d_assets(base_zip:str,hair_png:str,output_dir:str,
                           *, neural:bool=True,upscaler=None,
                           outfit_png:str|None=None)->dict:
    return build_modular_2d_assets(
        base_zip,output_dir,hair_png=hair_png,outfit_png=outfit_png,
        neural=neural,upscaler=upscaler
    )
