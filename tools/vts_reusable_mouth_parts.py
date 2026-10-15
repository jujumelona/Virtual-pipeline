"""Conservative reusable procedural mouth ART for BODY handoff.

Produces standalone full-canvas RGBA PNGs; does not silently composite them
over the closed neutral portrait or assert native Cubism keyforms were bound.
No vendor image is copied. Shape reuse was informed by the MIT-licensed
Amoner/lipsync-engine SVG renderer and PSD2Live mouth tag specification:
https://github.com/Amoner/lipsync-engine
https://github.com/tsunehimatoi/psd2live/blob/master/docs/en/spec/PSD_LAYER_SPEC.md
"""
from __future__ import annotations

from io import BytesIO
import json
import re

from PIL import Image, ImageDraw

PARTS = ("mouth_open", "tooth_t", "tongue")


def _tokens(name: str) -> set[str]:
    return set(filter(None, re.split(r"[.\s_\\-]+", name.casefold())))


def _is_mouth(name: str) -> bool:
    tokens = _tokens(name)
    return "mouth" in tokens or bool({"tooth", "teeth", "tongue"} & tokens)


def _why_not(layers, canvas):
    """Refuse to place generic artwork without identifiable original anatomy."""
    if len(canvas) != 2 or min(canvas) < 64:
        return "invalid_canvas", None
    # A named open mouth/teeth/tongue is already authored. Replacing or
    # duplicating it would lose style and/or render two mouths.
    if any(_is_mouth(layer["name"]) and
           _tokens(layer["name"]) & {"inside", "inner", "open", "opened",
                                   "teeth", "tooth", "tongue"}
           for layer in layers):
        return "existing_open_mouth_or_internals_preserved", None
    mouth = [layer for layer in layers if
             "mouth" in _tokens(layer["name"]) and
             not _tokens(layer["name"]) & {"pass2", "q", "upper", "lower",
                                            "top", "bottom", "lip"}]
    if len(mouth) != 1:
        return "no_unique_closed_mouth_layer", None
    base = mouth[0]["image"].convert("RGBA")
    box = base.getchannel("A").getbbox()
    if not box:
        return "closed_mouth_empty", None
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    if (w < max(10, min(canvas) * 0.008)
            or w > canvas[0] * 0.25 or h > w * 0.42
            or x0 < 0 or y0 < 0):
        return "closed_mouth_geometry_ambiguous", None
    faces = [layer for layer in layers if
             _tokens(layer["name"]) & {"face"} and
             not _tokens(layer["name"]) & {"pass2", "detail", "blush"}]
    if len(faces) != 1:
        return "no_unique_face_anchor", None
    fb = faces[0]["image"].getchannel("A").getbbox()
    if fb is None:
        return "face_anchor_empty", None
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    if (not fb[0] <= cx <= fb[2] or
            not fb[1] + (fb[3] - fb[1]) * .42 <= cy <= fb[3] - 3):
        return "mouth_outside_lower_face", None
    open_h = max(13, round(w * .54))
    open_top = round(cy - open_h * .26)
    open_bottom = open_top + open_h
    if (open_top < fb[1] or open_bottom > fb[3] + 0.03 * (fb[3] - fb[1])
            or open_bottom >= canvas[1]):
        return "open_mouth_would_exceed_face", None
    return None, {"closed_layer": mouth[0]["name"],
                  "closed_bbox_xyxy": list(box), "face_bbox_xyxy": list(fb),
                  "open_bbox_xyxy": [x0, open_top, x1, open_bottom]}


def _antialiased_part(canvas: tuple[int, int], box: tuple[int, int, int, int],
                      kind: str) -> Image.Image:
    """Draw at fourfold resolution, then register to the original canvas."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    scale = 4
    layer = Image.new("RGBA", (w * scale, h * scale))
    draw = ImageDraw.Draw(layer)
    def pt(x, y):
        return round(x * w * scale), round(y * h * scale)
    def oval(coords, fill, outline=None, width=1):
        (a, b), (c, d) = coords
        draw.ellipse([pt(a, b), pt(c, d)], fill=fill, outline=outline,
                     width=max(1, width * scale))
    if kind == "mouth_open":
        # The dark cavity includes a thin dark edge, not a second skin lip.
        oval(((.025, .025), (.975, .965)), (61, 22, 39, 255),
             (91, 36, 52, 255), width=1)
    elif kind == "tooth_t":
        # Teeth are intentionally smaller than the cavity. Independent alpha.
        oval(((.19, .14), (.81, .405)), (245, 241, 233, 255),
             (216, 208, 204, 255), width=1)
    elif kind == "tongue":
        oval(((.225, .575), (.775, .925)), (209, 103, 125, 255),
             (169, 73, 101, 255), width=1)
    else:
        raise ValueError("unsupported_mouth_part: " + kind)
    tile = layer.resize((w, h), Image.Resampling.LANCZOS)
    result = Image.new("RGBA", canvas)
    result.paste(tile, (x0, y0))
    return result


def generate_reusable_mouth_assets(layers: list[dict],
                                   canvas: tuple[int, int]):
    """Return independent PNG bytes and factual skip diagnostics.

    These supplemental artwork variants are *not* added to the visible
    neutral PSD. Binding to PSD2Live opacity keys requires a separate
    native integration gate; never equate ZIP files with rigging success.
    """
    reason, info = _why_not(layers, canvas)
    report = {
        "schema": "vtuber/reusable-mouth-art-v1",
        "asset": "body",
        "method": "procedural_vector_shape_rasterization",
        "license_of_our_implementation": "repository_project_license",
        "upstream_inspiration": "Amoner/lipsync-engine (MIT); no copied graphics",
        "parts_as_separate_png": [],
        "native_psd2live_keyform_binding_verified": False,
        "appended_to_neutral_psd": False,
        "original_visible_artwork_unchanged": True,
        "integration_stage": "source_assets_only_not_native_rig",
        "status": "skipped" if reason else "generated",
        "reason": reason,
    }
    if reason:
        return [], report
    box = tuple(info["open_bbox_xyxy"])
    outputs = []
    for kind in PARTS:
        part = _antialiased_part(canvas, box, kind)
        stream = BytesIO()
        part.save(stream, format="PNG")
        dest = "reusable_parts/mouth/" + kind + ".png"
        outputs.append((dest, stream.getvalue()))
        report["parts_as_separate_png"].append({
            "name": kind, "path": dest, "canvas": list(canvas),
            "alpha_bbox_xyxy": list(part.getchannel("A").getbbox()),
            "for_psd2live": {"mouth_open": "MOUTH_OPEN",
                              "tooth_t": "TOOTH_T",
                              "tongue": "TONGUE"}[kind],
        })
    report["anchor"] = info
    return outputs, report
