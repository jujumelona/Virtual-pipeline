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
    ("hair_back", "Complete back-of-head hair, including hidden roots and hair behind shoulders."),
    ("body", "Complete upper body and jacket/tunic torso with uninterrupted fabric behind arms and hair."),
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
    ("hair_left", "Complete left side-hair tuft/strand groups, including roots behind face."),
    ("hair_right", "Complete right side-hair tuft/strand groups, including roots behind face."),
    ("hair_front", "Full bangs/forelock with complete roots, preserving the front reference."),
    ("arm_left", "Complete character-left arm and sleeve, including body-hidden shoulder."),
    ("arm_right", "Complete character-right arm and sleeve, including body-hidden shoulder."),
    ("hand_left", "Character-left hand, fully modeled even when sleeve obscures wrist."),
    ("hand_right", "Character-right hand, fully modeled even when sleeve obscures wrist."),
    ("outfit_front", "Outer upper-body garment panel, detachable and complete beneath accessories."),
    ("outfit_back", "Outer rear garment panel, complete underneath front panels and arms."),
)
REQUIRED_2D = (
    "hair_back", "body", "face", "hair_front", "eye_left_white",
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
    palette: str = ""
    accessories: str = ""
    extra: str = ""

    def describe(self) -> str:
        data = {
            "hair_color": self.hair_color, "hairstyle": self.hairstyle,
            "eye_color": self.eye_color, "face_description": self.face_description,
            "outfit": self.outfit, "palette": self.palette,
            "accessories": self.accessories, "extra": self.extra,
        }
        for name in ("hair_color", "hairstyle", "eye_color", "face_description", "outfit"):
            if not data[name].strip():
                raise ValueError("Character identity field missing: " + name)
        return "\n".join(f"{key}: {value.strip()}" for key, value in data.items()
                         if value.strip())


def _common(identity: Identity) -> str:
    return (
        "CRITICAL IDENTITY LOCK: Keep a SINGLE identical original anime VTuber "
        "character across ALL outputs. Same proportions, line thickness, color "
        "swatches, hairstyle, garment shapes, facial features and lighting. "
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
            "hair silhouette, clothing, and face. "
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
            "Save the 26 semantic PNG layers named exactly as listed and put "
            "them in a ZIP with no extra PNGs or directories. Also deliver "
            "front_master.png separately. Each layer MUST be 2048x3072 RGBA, "
            "same exact origin/coordinate system. No sprite sheet. All "
            "occluded parts completed. JPEG is NOT accepted."
        )
    else:
        w, h = CANVAS_3D
        geometry = (
            "CANVAS EXACTLY 2048x3072 pixels W x H, origin top-left. "
            "Character centerline x=1024; crown y=150; neck y=600; "
            "shoulder line y=730; waist y=1550; knees y=2330; "
            "feet contact line y=2930. Occupies the same scale and exactly "
            "the same registered coordinates in front, back, left, right. "
            "Entire body and shoes visible. NO perspective, orthographic camera "
            "at level height, neutral symmetric A-pose with arms separated "
            "from torso, fingers distinguishable. "
        )
        for key, description in VIEWS_3D:
            if key == "face":
                geo = (
                    "2048x2048 PNG close-up. Front facing and orthographic. "
                    "Face centered x=1024 y=1050; crop hairline to collar, "
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
            "Deliver exactly FIVE separate image files: front.png, back.png, "
            "left.png, right.png (each 2048x3072) and face.png (2048x2048). "
            "Never produce a multi-view contact sheet or change the character "
            "identity between images."
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
