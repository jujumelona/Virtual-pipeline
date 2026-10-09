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
    ("body", "Neutral adult VTuber body with natural face-matched skin, simplified non-explicit torso and pelvis. NO bodysuit, cloth, seams or garment."),
    ("neck", "Skin-colored neck from jaw to shoulders, including parts occluded by the face and future hair."),
    ("ear_left", "Character's left ear, fully drawn behind hair."),
    ("ear_right", "Character's right ear, fully drawn behind hair."),
    ("face", "Facial skin and jaw without eyes, brows, lips or bangs; include whole forehead for later separate hair."),
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
    ("arm_left", "Character-left natural skin-colored arm with complete hidden shoulder; no fabric, sleeve or cuff."),
    ("arm_right", "Character-right natural skin-colored arm with complete hidden shoulder; no fabric, sleeve or cuff."),
    ("hand_left", "Character-left skin-colored hand, fully drawn past wrist for later separate sleeves."),
    ("hand_right", "Character-right skin-colored hand, fully drawn past wrist for later separate sleeves."),
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
    skin_color: str = ""  # Optional explicit HEX; legacy outfit arg kept for API compatibility.

    def describe(self) -> str:
        data = {
            "gender": self.gender,
            "hair_color": self.hair_color, "hairstyle": self.hairstyle,
            "eye_color": self.eye_color, "face_description": self.face_description,
            "natural_skin_color": self.skin_color or "match face tone (enter exact HEX)",
            "palette": self.palette,
            "accessories": self.accessories, "extra": self.extra,
        }
        for name in ("hair_color", "hairstyle", "eye_color", "face_description"):
            if not data[name].strip():
                raise ValueError("Character identity field missing: " + name)
        return "\n".join(f"{key}: {value.strip()}" for key, value in data.items()
                         if value.strip())


def _common(identity: Identity, *, mode: str = "2d") -> str:
    skin_rule = (
        "PROFESSIONAL ADULT VTUBER ANATOMICAL BASE: All visible skin "
        "(face, neck, shoulders, torso, arms, hands, legs and feet when "
        "visible) must have the SAME natural face-matched skin color. "
        "Smooth simplified non-explicit chest/pelvis; no intimate details. "
        "This is human-style skin, not a skin-colored fabric covering. "
        "NO gray bodysuit, fitted underlayer, leotard, underwear, "
        "stockings, garment seams, cuffs, zippers, collars, socks or shoes. "
        "Wardrobe is a separate later production asset. "
    )
    if mode == "3d":
        return (
            "CRITICAL 3D IDENTITY LOCK: ONE original anime VTuber body with "
            "a neutral skin-colored base in EVERY direction. Use the SAME "
            "hairstyle across the 3D views because this reconstruction path "
            "extracts hair from images; automatic hair/wardrobe swapping "
            "is not supplied. Attach actual front views as identity refs "
            "for later views. Never mirror to fake a different direction. "
            + skin_rule + "\n" + identity.describe() + "\n"
            "ONE IMAGE PER REQUEST; no text, labels or watermark. "
            "Use native resolution and preserve each view's aspect ratio."
        )
    return (
        "CRITICAL 2D IDENTITY LOCK: ONE outfit-free and hairstyle-free "
        "adult anime VTuber base with uncovered scalp and no head hair. "
        "Keep face/body proportions constant. Use front_master.png for "
        "the identity and separate registration of independent parts. "
        + skin_rule + "\n" + identity.describe() + "\n"
        "ONE IMAGE PER REQUEST; no text, labels or watermark. "
        "Do not mirror or recenter individual parts."
    )

def build_prompts(mode: str, identity: Identity) -> dict:
    """Emit explicit per-file instructions with fixed pixel anchors and counts."""
    if mode not in ("live2d", "inochi2d", "3d"):
        raise ValueError("unsupported prompt mode: " + mode)
    general = _common(identity, mode=mode)
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
             "uncovered scalp, skin-colored anatomy, and face. "
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
        # Legacy five-view brief. Colab uses paired sheets + face.
        # Views now depict a natural-skin-colored neutral 3D base.
        geometry = (
            "PORTRAIT width:height=2:3, render at native image AI quality. "
            "Same character center, head-to-foot framing, body height, "
            "body proportions and bare feet positions across views. "
            "All body surfaces show one natural skin material, "
            "with no clothing, collar, seams or bodysuit in any view. "
            "Orthographic eye-level camera, neutral symmetric A-pose with "
            "arms slightly separated, visible hands and feet. "
            "Do not mirror images or add clothes between views. "
        )
        for key, description in VIEWS_3D:
            if key == "face":
                geo = (
                    "SQUARE width:height=1:1 PNG face close-up, native resolution. "
                    "Front facing and orthographic. Include hairline, jaw and skin-colored neck, "
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
            "ALL views show the SAME neutral natural-skin 3D avatar."
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
