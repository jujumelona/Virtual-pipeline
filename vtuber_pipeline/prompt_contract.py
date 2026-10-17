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
    ("neck", "Neck skin only, same natural skin color as face and ears; extends below jaw for a clothing collar overlap."),
    ("ear_left", "Character-left ear, fully drawn at correct head anchor."),
    ("ear_right", "Character-right ear, fully drawn at correct head anchor."),
    ("face", "Bald head with short round jaw, forehead and facial skin without eyes, nose or mouth; no shoulders or torso."),
    ("eye_left_white", "Left eye sclera on transparent head canvas."),
    ("eye_left_iris", "Left iris and pupil, bright orange anime eye."),
    ("eye_left_lid", "Left eyelids with closed-lid blink geometry."),
    ("eye_right_white", "Right eye sclera on transparent head canvas."),
    ("eye_right_iris", "Right iris and pupil, bright orange anime eye."),
    ("eye_right_lid", "Right eyelids with closed-lid blink geometry."),
    ("brow_left", "Whole left eyebrow."),
    ("brow_right", "Whole right eyebrow."),
    ("nose", "Small stylized anime nose only."),
    ("mouth_closed", "Closed mouth line only."),
    ("mouth_open", "Open mouth with inside, top teeth and tongue; separate animation reference."),
)
REQUIRED_2D = (
    "face", "neck", "eye_left_white", "eye_left_iris",
    "eye_right_white", "eye_right_iris", "brow_left", "brow_right",
    "mouth_closed", "mouth_open",
)
OPTIONAL_VARIANTS = frozenset(("mouth_open",))
VIEWS_3D = (
    ("front", "Bald face and neck facing camera, top of head to neck end."),
    ("back", "Back of the same bald head and neck, orthographic rear."),
    ("left", "Same bald face and neck rotated to exact left profile."),
    ("right", "Same bald face and neck rotated to exact right profile."),
    ("face", "Front orthographic close-up of the same head and facial features, no perspective."),
)


@dataclass(frozen=True)
class Identity:
    hair_color: str
    hairstyle: str
    eye_color: str
    face_description: str
    outfit: str = ""  # Deprecated compatibility arg; base body never uses outfit.
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
            "natural_skin_color": self.skin_color or "match natural face tone (enter exact HEX)",
            "palette": self.palette,
            "accessories": self.accessories, "extra": self.extra,
        }
        for name in ("hair_color", "hairstyle", "eye_color", "face_description"):
            if not data[name].strip():
                raise ValueError("Character identity field missing: " + name)
        return "\n".join(f"{key}: {value.strip()}" for key, value in data.items()
                         if value.strip())


def _common(identity: Identity, *, mode: str = "2d") -> str:
    face_brief = (
        "PROFESSIONAL ADULT ANIME VTUBER FACE ASSET ONLY: "
        "Draw only a bald anime head, expressive orange irises, ears, "
        "small nose and mouth, and a natural neck extended just enough to "
        "connect inside a separately generated outfit collar. "
        "Natural skin color must match on face, ears, scalp and neck. "
        "No shoulders, arms, hands, torso, chest, abdomen, legs, clothing, "
        "hair, accessories or body-only reference artwork in this image. "
        "Do not render a clothed or unclothed body. "
        "Professional 2-3 tone cel-shaded adult VTuber face art. "
        "The separately generated OUTFIT asset will supply clothed shoulders "
        "torso and arms, while HAIR remains a separate asset. "
        "ONE image per request; no text or watermarks. "
    )
    return face_brief + "\\n" + identity.describe() + "\\n"

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
            "face-only crop; shoulders and torso absent; "
            "neck end y=1950; no features cropped. "
            "All layers must match the front master at the SAME absolute pixel "
            "coordinates; never center the isolated part within its canvas. "
        )
        master = (
            "OUTPUT front_master.png. Render ONE complete clean front-view, "
            "neutral anime face and neck only, mouth CLOSED, eyes OPEN, "
            "face and neck in stable reference positions. Fully antialiased edges; full visible "
             "uncovered scalp, face and neck only; NO torso or wardrobe. "
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
             "Deliver 16 separate PNG images: front_master.png and the 15 "
            "named RGBA semantic layers. Every layer uses the same 2048x3072 "
            "full canvas and exact origin. No sprite sheet. Complete all "
            "occluded areas; JPEG is not accepted."
        )
    else:
        w, h = CANVAS_3D
        # Legacy five-view brief. Colab uses paired sheets + face.
        # Views depict a fully covered blue-gray production rigging suit.
        geometry = (
            "PORTRAIT width:height=2:3, render at native image AI quality. "
            "Same character face center, head-and-neck-only framing, head height, "
            "head proportions and neck position across views. "
            "Face/neck only; never generate torso, arms, clothing or legs. "
            "Orthographic eye-level camera, symmetric face profile with "
            "face forward, neck ends within frame. "
            "Do not mirror images or redesign basewear between views. "
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
            "FACE REFERENCES ONLY — not a riggable VRM input. Exactly FIVE PNG files: "
            "front.png, back.png, left.png, right.png (portrait 2:3) "
            "and face.png (square 1:1). Save exact filenames. "
            "FACE-only references cannot produce a VRM directly; legacy sheet names: "
            "(sheet_front_back.png, sheet_side_views.png; each 4:3) "
            "plus face.png, zipped as character_3d_sheet_pack.zip. "
            "ALL views depict one adult anime head and neck, not a complete VRM avatar."
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
