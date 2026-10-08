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


def masked_repair(original_rgba, generated_rgb, fill_mask):
    """Copy generated pixels only into the explicit fill region; preserve all others."""
    import numpy as np
    original = np.asarray(original_rgba)
    generated = np.asarray(generated_rgb)
    mask = np.asarray(fill_mask)
    if original.ndim != 3 or original.shape[2] != 4:
        raise ValueError('repair source must be RGBA')
    if generated.shape != original.shape[:2] + (3,) or mask.shape != original.shape[:2]:
        raise ValueError('repair inputs must share the original canvas')
    if any(a.dtype != np.uint8 for a in (original, generated, mask)):
        raise ValueError('repair inputs must use uint8 pixels')
    repaired = original.copy()
    selected = mask > 0
    repaired[selected, :3] = generated[selected]
    repaired[selected, 3] = np.maximum(original[selected, 3], mask[selected])
    return repaired
