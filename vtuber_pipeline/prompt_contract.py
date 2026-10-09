"""Deterministic external-image generation briefs; no planning LLM required.

The user supplies the character identity, and this module emits an explicit
per-image prompt plus a machine-checkable manifest. Pixels and precise
registration are verified at upload/build time, never *assumed* from prompts.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import re

CANVAS_2D = (2048, 3072)
CANVAS_3D = (2048, 3072)
CANVAS_FACE = (2048, 2048)

# Filenames are direct semantic keys read by two_d.build.KNOWN. Variants are
# supplied independently; every file is a full-canvas RGBA image.
LAYER_PARTS = (
    ("body", "Unclothed neutral covered body/undersuit base only. Never bake the removable garment into anatomy."),
    ("neck", "Entire neck from jaw to collar, even under chin and garment."),
    ("ear_left", "Character's left ear, fully drawn behind hair."),
    ("ear_right", "Character's right ear, fully drawn behind hair."),
    ("face", "Full facial skin and jaw without eyes, brows, lips or bangs; include covered forehead."),
    ("eye_left_white", "Left eye sclera and complete outline footprint."),
    ("eye_left_iris", "Left iris and pupil colored surface, fully drawn circular disc."),
    ("eye_left_lid", "Left top and bottom visible eyelids with blink-ready closed lid geometry."),
    ("eye_right_white", "Right eye sclera and complete outline footprint."),
    ("eye_right_iris", "Right iris and pupil colored surface, fully drawn circular disc."),
    ("eye_right_lid", "Right top and bottom visible eyelids with blink-ready closed lid geometry."),
    ("brow_left", "Whole left eyebrow including segment hidden by bangs."),
    ("brow_right", "Whole right eyebrow including segment hidden by bangs."),
    ("nose", "Nose line and shadow on transparent canvas; only nose pixels."),
    ("mouth_closed", "Closed mouth lip outline in resting pose."),
    ("mouth_open", "Open mouth shape including teeth, tongue and interior; separate animation variant."),
    ("arm_left", "Complete character-left neutral base arm with body-hidden shoulder. No removable sleeves or clothing cuffs."),
    ("arm_right", "Complete character-right neutral base arm with body-hidden shoulder. No removable sleeves or clothing cuffs."),
    ("hand_left", "Character-left hand, fully modeled even when sleeve obscures wrist."),
    ("hand_right", "Character-right hand, fully modeled even when sleeve obscures wrist."),
)
REQUIRED_2D = (
    "body", "face", "eye_left_white",
    "eye_left_iris", "eye_right_white", "eye_right_iris",
    "brow_left", "brow_right", "mouth_closed", "mouth_open",
    "neck", "arm_left", "arm_right",
)
OPTIONAL_VARIANTS = frozenset(("mouth_open",))
VIEWS_3D = (
    ("front", "Entire character facing camera, feet to crown, straight orthographic front."),
    ("back", "Same character rotated exactly 180 degrees, rear orthographic view."),
    ("left", "Same character rotated 90 degrees to character-left, left side orthographic."),
    ("right", "Same character rotated 90 degrees to character-right, right side orthographic."),
    ("face", "Front orthographic close-up of the same head and facial features, no perspective."),
)


@dataclass(frozen=True)
class Identity:
    hair_color: str
    hairstyle: str
    eye_color: str
    face_description: str
    outfit: str
    gender: str = ""
    palette: str = ""
    accessories: str = ""
    extra: str = ""

    def describe(self) -> str:
        data = {
            "gender": self.gender,
            "hair_color": self.hair_color, "hairstyle": self.hairstyle,
            "eye_color": self.eye_color, "face_description": self.face_description,
            "neutral_underlayer": self.outfit, "palette": self.palette,
            "accessories": self.accessories, "extra": self.extra,
        }
        for name in ("hair_color", "hairstyle", "eye_color", "face_description"):
            if not data[name].strip():
                raise ValueError("Character identity field missing: " + name)
        return "\n".join(f"{key}: {value.strip()}" for key, value in data.items()
                         if value.strip())


def _common(identity: Identity) -> str:
    return (
        "CRITICAL IDENTITY LOCK: Keep a SINGLE identical original anime VTuber "
        "character across ALL outputs. Same proportions, line thickness, color "
        "swatches, hairstyle, neutral base anatomy, facial features and lighting. "
        "Use the supplied front_master.png as the exact pixel-coordinate "
        "reference for ALL subsequent layer images; do not redesign.\n"
        + identity.describe() + "\n"
        "ONE IMAGE PER REQUEST, NO MULTIPANEL CHARACTER SHEET, NO TEXT, "
        "NO BORDER, NO LABELS, NO WATERMARKS. DO NOT MIRROR OR RESIZE THE "
        "CHARACTER BETWEEN FILES."
    )


def build_prompts(mode: str, identity: Identity) -> dict:
    """Emit explicit per-file instructions with fixed pixel anchors and counts."""
    if mode not in ("live2d", "inochi2d", "3d"):
        raise ValueError("unsupported prompt mode: " + mode)
    general = _common(identity)
    if mode == "3d":
        general += (
            "\\n3D DEFAULT INTEGRATED COSTUME: "
            + identity.outfit.strip()
            + ". Render identical clothing on every orthographic view; "
              "not an outfit-free mannequin and not a standalone garment."
        )
    result: list[dict] = []
    if mode in ("live2d", "inochi2d"):
        w, h = CANVAS_2D
        geometry = (
            "CANVAS EXACTLY 2048 x 3072 pixels (W x H), portrait, RGBA. "
            "Origin (0,0) TOP LEFT; +X right, +Y down. "
            "HEAD CENTER x=1024; crown y=240; eyes center y=1110; "
            "nose y=1280; mouth y=1380; jaw y=1510; neck y=1590; "
            "shoulders y=1730; torso centerline x=1024; "
            "waist y=2700; no features cropped. "
            "All layers must match the front master at the SAME absolute pixel "
            "coordinates; never center the isolated part within its canvas. "
        )
        master = (
            "OUTPUT front_master.png. Render ONE complete clean front-view, "
            "neutral anime bust/upper-body reference, mouth CLOSED, eyes OPEN, "
            "arms neutral and consistent. Fully antialiased edges; full visible "
             "hair silhouette, neutral anatomy/underlayer, and face. "
            + geometry
            + " Master may use a solid neutral background for visual reference; "
            "all part layers MUST be transparent."
        )
        result.append({"filename": "front_master.png", "width": w, "height": h,
                       "purpose": "master", "prompt": general + "\n" + master})
        for key, description in LAYER_PARTS:
            variant = (
                "This layer is an alternative animation state, not part of the "
                "neutral master composite. Preserve identical positioning. "
                if key in OPTIONAL_VARIANTS else ""
            )
            prompt = (
                f"OUTPUT EXACTLY {key}.png. ONLY render: {description} "
                "Everything outside this ONE semantic part MUST be TRUE "
                "TRANSPARENT ALPHA=0, not white, not black, not checkerboard. "
                "Draw the entire part including the portions occluded by other "
                "parts in the master; do not draw adjacent body parts. "
                "Pixels of visible regions must match front_master.png. "
                "Fully opaque core, anti-aliased alpha edges, no shadows outside "
                "part silhouette. Do NOT move, zoom, scale, crop, or rotate. "
                + variant + geometry
            )
            result.append({"filename": f"{key}.png", "width": w, "height": h,
                           "purpose": "part", "semantic_id": key,
                           "prompt": general + "\n" + prompt})
        packaging = (
             "Deliver 21 separate PNG images: front_master.png and the 20 "
            "named RGBA semantic layers. Every layer uses the same 2048x3072 "
            "full canvas and exact origin. No sprite sheet. Complete all "
            "occluded areas; JPEG is not accepted."
        )
    else:
        w, h = CANVAS_3D
        # Legacy five-file image brief. The default v8 Colab route uses two
        # multiview sheets + face; both describe an ALREADY CLOTHED avatar.
        geometry = (
            "PORTRAIT width:height=2:3, render at native image AI quality. "
            "Same character center, head-to-foot framing, body height, "
            "costume proportions and shoe positions across every view. "
            "Entire DEFAULT OUTFIT (top/bottom or dress, collar, sleeves, "
            "cuffs, outer garment, shoes, fabric colors, seams) stays "
            "ON the character in FRONT/BACK/LEFT/RIGHT. "
            "The outfit is part of this initial 3D avatar and is NOT "
            "exported as a separate removable garment. "
            "Orthographic eye-level camera, neutral symmetric A-pose with "
            "arms slightly separated, visible hands and feet. "
            "Do not mirror images or change clothes between views. "
        )
        for key, description in VIEWS_3D:
            if key == "face":
                geo = (
                    "SQUARE width:height=1:1 PNG face close-up, native resolution. "
                    "Front facing and orthographic. Include hairline, jaw and collar, "
                    "eyelids fully visible. This FACE CROP IS A SEPARATE "
                    "VIEW; do not treat it as full-body registered coordinates."
                )
            else:
                geo = geometry
            result.append({
                "filename": f"{key}.png", "width": CANVAS_FACE[0] if key == "face" else w,
                "height": CANVAS_FACE[1] if key == "face" else h,
                "purpose": "view", "prompt": general + "\n"
                + f"OUTPUT EXACTLY {key}.png. {description} "
                + geo + " No props, text, cast shadow or asymmetrical pose; "
                "fixed lighting and character details in every view.",
            })
        packaging = (
            "Legacy single-view upload: exactly FIVE separate PNG files: "
            "front.png, back.png, left.png, right.png (portrait 2:3) "
            "and face.png (square 1:1). Save exact filenames. "
            "For default Colab 3D v8 use TWO paired-view sheets "
            "(sheet_front_back.png, sheet_side_views.png; each 4:3) "
            "plus face.png, zipped as character_3d_sheet_pack.zip. "
            "ALL views are of the SAME CLOTHED avatar with identical outfit."
        )
    return {
        "schema": "vtuber-external-image-contract-v1", "mode": mode,
        "canvas": [w, h], "image_count": len(result),
        "identity": identity.describe(),
        "packaging": packaging, "images": result,
        "required_layers": list(REQUIRED_2D) if mode != "3d" else [],
    }


def write_prompt_package(mode: str, identity: Identity, destination: str) -> str:
    """Create shareable text files containing all user-ready image requests."""
    from zipfile import ZIP_DEFLATED, ZipFile

    spec = build_prompts(mode, identity)
    folder = Path(destination)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{mode}_image_generation_prompts.zip"
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(spec, ensure_ascii=False, indent=2))
        archive.writestr("README.txt",
                         f"MODE={mode}\nIMAGES={spec['image_count']}\n"
                         + spec["packaging"] + "\n"
                         "IMPORTANT: prompt instructions are NOT proof of exact "
                         "registration. Validate downloaded images before build.\n")
        for item in spec["images"]:
            archive.writestr(
                f"prompts/{item['filename']}.txt",
                item["prompt"] + "\n",
            )
    return str(path)
