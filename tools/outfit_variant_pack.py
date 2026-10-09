"""Separate detachable outfit for a permanent hair/outfit-free base.

Public compatibility facade. The actual deterministic assembler is shared
with hair variants in tools.modular_avatar_pack.
"""
from __future__ import annotations
from tools.modular_avatar_pack import inspect_image,build_modular_2d_assets

def inspect_garment_image(filename: str)->dict:
    return inspect_image(filename,"outfit")

def build_dressed_2d_assets(
    base_zip: str, outfit_png: str, output_dir: str,
    *, neural: bool=True,upscaler=None,hair_png: str|None=None
)->dict:
    return build_modular_2d_assets(
        base_zip,output_dir,hair_png=hair_png,outfit_png=outfit_png,
        neural=neural,upscaler=upscaler
    )
