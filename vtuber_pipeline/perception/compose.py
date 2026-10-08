"""Deterministic z-order composition of original canvas RGBA parts."""
from PIL import Image
from vtuber_pipeline.common.schemas import PartsDocument

def compose_layers(parts: PartsDocument, output_path: str) -> str:
    base = Image.new("RGBA", (parts.width, parts.height))
    for part in sorted(parts.parts, key=lambda x: x.z_order):
        im = Image.open(part.rgba_png).convert("RGBA")
        if im.size != base.size:
            raise ValueError("part canvas size mismatch")
        base.alpha_composite(im)
    base.save(output_path)
    return output_path
