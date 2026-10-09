"""Render one official FREE/PRO prompt bundle for external-image AI from Colab.

Do not duplicate the prompts here; vtuber_pipeline.vts_modes owns the contract.
"""
from __future__ import annotations

def prepare_vts_notebook_brief(*, edition, scope, hair_color, hairstyle, eyes,
                               face, outfit, accessories, destination):
    from vtuber_pipeline.prompt_contract import Identity
    from vtuber_pipeline.vts_modes import build_vts_brief, write_vts_brief_package
    identity = Identity(hair_color=hair_color, hairstyle=hairstyle,
                        eye_color=eyes, face_description=face,
                        outfit=outfit, accessories=accessories)
    brief = build_vts_brief(edition, scope, identity)
    path = write_vts_brief_package(brief, destination)
    return brief, path
