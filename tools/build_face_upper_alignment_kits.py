"""Make registered UPPER reference ZIPs from a real minted FACE artwork ZIP.

Does not draw a hairstyle or outfit; generated ZIPs are reference material
for image creation/editing, NOT substitutes for finished See-through input.
"""
from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path
import hashlib
import json
import zipfile

import numpy as np
from PIL import Image, ImageDraw

CANVAS = (1536, 2304)
SCALE = 0.55
GUIDE = Path(__file__).resolve().parents[1] / "docs" / "SEE_THROUGH_REGISTERED_UPPER_INPUT_2026-10-22.md"
PROMPTS = {
    "COMPLETE_CHARACTER": (
        "OUTPUT ONE full_character_input.png; 1536x2304 RGBA. Preserve the EXACT "
        "female mint-eyed face_registered_upper.png pixels. Add a dressed adult "
        "anime VTuber upper body and black/white hairstyle as image edits or "
        "overlaid artwork. Front, neutral, eyes open, mouth closed, mask OFF. "
        "No labels, no guide lines, no background."
    ),
    "OUTFIT": (
        "OUTPUT ONE outfit.png; 1536x2304 true transparent RGBA. Draw ONLY "
        "the fully dressed shoulders, collar, chest, sleeves and arms. Align "
        "the collar to existing face_registered_upper.png neck ending y=1132. "
        "The outfit extends to about y=2210. Black/white modern plague-doctor "
        "inspired hoodie, no green clothing highlights. Do NOT repaint "
        "any part of the original face, hair or bare head."
    ),
    "HAIR": (
        "OUTPUT ONE hair.png; 1536x2304 true transparent RGBA. Draw ONLY "
        "split white-and-black anime hair on top of EXACT original "
        "face_registered_upper.png, including side and back hair. Big mint "
        "eyes remain visible. Do NOT redraw face, body or clothes. The hair "
        "must fit the original bald crown, not a newly hallucinated skull."
    ),
    "ACCESSORY": (
        "OUTPUT ONE accessory.png; 1536x2304 true transparent RGBA. Draw "
        "separately a slim pointed future plague-doctor mask with visible "
        "front purifier. Keep face unchanged. Do NOT include the mask in "
        "the initial See-through full-character image; add it after face "
        "separation as an optional visible accessory."
    ),
}


def build(face_zip: Path, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(face_zip) as z:
        if z.testzip() is not None:
            raise ValueError("Corrupt FACE ZIP")
        raw = z.read("outputs/master.png")
    original = Image.open(BytesIO(raw))
    original.load()
    if original.format != "PNG" or original.mode != "RGBA" or original.size != (1536, 1920):
        raise ValueError("Expected original 1536x1920 transparent RGBA FACE master")
    if original.getchannel("A").getextrema() != (0, 255):
        raise ValueError("FACE master must contain visible pixels and a transparent background")
    bbox = original.getchannel("A").getbbox()
    new_size = tuple(round(v * SCALE) for v in original.size)
    dx = round(CANVAS[0] / 2 - (bbox[0] + bbox[2]) * SCALE / 2)
    dy = round(140 - bbox[1] * SCALE)
    data = np.asarray(original).astype(np.float32)
    alpha = data[:, :, 3:4] / 255.0
    premul = np.uint8(np.clip(np.rint(np.concatenate((data[:, :, :3] * alpha, data[:, :, 3:4]), axis=2)), 0, 255))
    reduced = Image.fromarray(premul, "RGBA").resize(new_size, Image.Resampling.LANCZOS)
    pixels = np.asarray(reduced).copy()
    a = pixels[:, :, 3].astype(np.float32)
    valid = a > 0
    for channel in range(3):
        raw_color = pixels[:, :, channel].astype(np.float32)
        recovered = np.zeros_like(raw_color)
        recovered[valid] = np.clip(np.rint(raw_color[valid] * 255 / a[valid]), 0, 255)
        pixels[:, :, channel] = np.uint8(recovered)
    registered = Image.new("RGBA", CANVAS)
    registered.alpha_composite(Image.fromarray(pixels, "RGBA"), (dx, dy))
    registration_bbox = registered.getchannel("A").getbbox()
    if registration_bbox[3] >= round(CANVAS[1] * .60):
        raise ValueError("Registered FACE covers too much UPPER torso space")
    reference = output / "face_registered_upper.png"
    registered.save(reference)
    manifest = {
        "schema": "virtual-pipeline/upper-registered-character-v1",
        "frame": "live2d_upper",
        "canvas": list(CANVAS),
        "source_master_sha256": hashlib.sha256(raw).hexdigest(),
        "source_master_size": list(original.size),
        "source_master_alpha_bbox": list(bbox),
        "registered_face_file": reference.name,
        "registered_face_sha256": hashlib.sha256(reference.read_bytes()).hexdigest(),
        "registration": {"scale": SCALE, "new_size": list(new_size),
                         "translation_px": [dx, dy],
                         "filter": "premultiplied_alpha_lanczos",
                         "intentional_framing": "upper-body, manually specified"},
        "registered_face_alpha_bbox": list(registration_bbox),
        "pixel_coordinates": "origin upper left, x right, y down",
        "output": "full_character_input.png RGBA 1536x2304 (head + hair + outfit)",
        "full_character_generated": False,
    }
    (output / "registration_contract.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    guide = GUIDE.read_text(encoding="utf-8")
    for scope, prompt in PROMPTS.items():
        zip_path = output / f"GENERATOR_{scope}_UPPER_REFERENCE.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as z:
            z.write(reference, "face_registered_upper.png")
            z.write(output / "registration_contract.json", "registration_contract.json")
            z.writestr("00_READ_FIRST.md", guide)
            z.writestr("01_GENERATION_PROMPT.txt", prompt + "\n")
            preview = Image.new("RGBA", CANVAS, (247, 248, 250, 255))
            preview.alpha_composite(registered)
            stream = BytesIO()
            preview.convert("RGB").save(stream, "PNG")
            z.writestr("02_POSITION_REFERENCE_NOT_OUTPUT.png", stream.getvalue())
    print("UPPER_REGISTERED_FACE:", reference)
    print("CANVAS:", CANVAS, "ORIGINAL FACE BBOX:", bbox, "REGISTERED BBOX:", registration_bbox)
    print("Generated four image-AI reference ZIPs; NONE contains a finished character.")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--face-zip", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    build(args.face_zip, args.output_dir)


if __name__ == "__main__":
    main()
