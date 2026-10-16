"""Create *real visual inputs* for one image-AI VTuber part at a time.

A correct output requires the actual character master, the actual chosen
template-slot image, and a manually reviewed paint region mask. Descriptive
part names alone are deliberately insufficient.

This is an optional authoring utility, never a replacement for model-native
mesh/keyform/rig verification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops


def _load_rgba(path: Path) -> Image.Image:
    with Image.open(path) as source:
        source.load()
        if source.format != "PNG":
            raise ValueError("IMAGE_REFERENCE_MUST_BE_PNG: " + str(path))
        if min(source.size) < 32 or max(source.size) > 16384:
            raise ValueError("IMAGE_REFERENCE_SIZE_INVALID: " + str(path))
        return source.convert("RGBA")


def _paint_mask(path: Path, size: tuple[int, int]) -> Image.Image:
    with Image.open(path) as image:
        image.load()
        if image.format != "PNG" or image.size != size:
            raise ValueError("PART_MASK_MUST_BE_FULL_CANVAS_PNG")
        mask = image.convert("L").point(lambda x: 255 if x > 127 else 0)
    if not mask.getbbox():
        raise ValueError("PART_MASK_EMPTY")
    return mask


def _digest(image: Image.Image) -> str:
    return hashlib.sha256(image.tobytes()).hexdigest()


def prepare(*, master: Path, template_slot: Path, target_mask: Path,
            output: Path, role: str, base_part: Path | None = None,
            padding: int = 64) -> dict:
    """Build a crop and exact magenta paint-mask job from REAL input artwork."""
    if not role or any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for ch in role):
        raise ValueError("PART_ROLE_INVALID")
    m = _load_rgba(master)
    template = _load_rgba(template_slot)
    base = (_load_rgba(base_part) if base_part else
            Image.new("RGBA", m.size, (0, 0, 0, 0)))
    if base.size != m.size:
        raise ValueError("PART_BASE_MUST_MATCH_MASTER_CANVAS")
    mask = _paint_mask(target_mask, m.size)
    if ImageChops.multiply(mask, base.getchannel("A")).getbbox():
        raise ValueError("PART_MASK_OVERWRITES_APPROVED_PIXELS")
    union = ImageChops.lighter(mask, base.getchannel("A"))
    left, top, right, bottom = union.getbbox()
    left = max(0, left - padding)
    top = max(0, top - padding)
    right = min(m.width, right + padding)
    bottom = min(m.height, bottom + padding)
    crop = (left, top, right, bottom)

    # The editing model sees real surviving part pixels on bright-green chroma.
    # Only explicitly white mask regions become magenta paint targets.
    visual = Image.new("RGBA", m.size, (0, 255, 0, 255))
    visual.alpha_composite(base)
    visual = visual.convert("RGB")
    visual.paste((255, 0, 255), mask=mask)

    context = Image.new("RGBA", m.size, (248, 248, 248, 255))
    context.alpha_composite(m)

    output.mkdir(parents=True, exist_ok=True)
    visual.crop(crop).save(output / "input.png")
    context.crop(crop).convert("RGB").save(output / "character_context.png")
    mask.crop(crop).save(output / "mask.png")
    m.save(output / "character_master.png")
    template.save(output / "template_slot.png")
    base.save(output / "base_part.png")
    mask.save(output / "hidden_mask_full.png")

    prompt = (
        "You are drawing exactly ONE VTuber 2D artwork part: " + role + ".\n"
        "Inspect the attached character_context.png, character_master.png, "
        "template_slot.png, input.png and mask.png VISUALLY. "
        "The template supplies the part structure; NEVER copy the template character.\n"
        "input.png contains surviving original part pixels over pure GREEN #00FF00, "
        "and MAGENTA #FF00FF shows exactly the editable region. "
        "Draw new same-character pixels ONLY in magenta, continuing the exact linework, "
        "paint, style, local contour and hidden overlap. "
        "Keep all non-magenta pixels unchanged. If the desired silhouette ends "
        "before the mask ends, make that remainder PURE GREEN #00FF00. "
        "Do not draw adjacent eyes, face, clothing or other parts. "
        "Do not add arrows, labels, PSD layers or rigging geometry. "
        "Keep the canvas and pixel coordinates IDENTICAL to input.png. "
        "Save one edited RGB PNG as output.png. Do not reframe or crop further.\n"
    )
    (output / "part_job_prompt.txt").write_text(prompt, encoding="utf-8")
    report = {
        "schema": "vtuber/one-part-reference-edit-job-v1",
        "role": role,
        "canvas": list(m.size),
        "crop_xyxy": list(crop),
        "crop_size": [right - left, bottom - top],
        "base_pixel_sha256": _digest(base),
        "mask_pixel_sha256": _digest(mask),
        "template_pixel_sha256": _digest(template),
        "reference_images_actually_supplied": True,
        "part_geometry_approved_by_artist": False,
        "native_animation_verified": False,
        "generated_output_present": False,
    }
    (output / "job.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def apply(*, job_dir: Path, generated: Path, output_part: Path) -> dict:
    """Copy ONLY the reviewed masked generated pixels back to original canvas.

    This cannot visually certify style or movement. It does guarantee that
    outside-mask original pixels are preserved.
    """
    job = json.loads((job_dir / "job.json").read_text(encoding="utf-8"))
    if job.get("schema") != "vtuber/one-part-reference-edit-job-v1":
        raise ValueError("PART_JOB_MANIFEST_INVALID")
    base = _load_rgba(job_dir / "base_part.png")
    mask = _paint_mask(job_dir / "hidden_mask_full.png", base.size)
    if _digest(base) != job["base_pixel_sha256"] or _digest(mask) != job["mask_pixel_sha256"]:
        raise ValueError("PART_JOB_INPUTS_CHANGED")
    crop = tuple(job["crop_xyxy"])
    expected = (crop[2] - crop[0], crop[3] - crop[1])
    with Image.open(generated) as image:
        image.load()
        if image.format != "PNG" or image.size != expected:
            raise ValueError("GENERATED_PART_CROP_MISMATCH")
        art = image.convert("RGB")
    out = base.copy()
    result_mask = mask.crop(crop)
    image_px = art.load()
    mask_px = result_mask.load()
    x0, y0 = crop[:2]
    changed = 0
    green = 0
    for yy in range(expected[1]):
        for xx in range(expected[0]):
            if mask_px[xx, yy] < 128:
                continue
            rgb = image_px[xx, yy]
            if rgb == (0, 255, 0):
                out.putpixel((xx + x0, yy + y0), (0, 0, 0, 0))
                green += 1
                continue
            if rgb == (255, 0, 255):
                raise ValueError("GENERATED_PART_CONTAINS_UNFILLED_MAGENTA")
            out.putpixel((xx + x0, yy + y0), (*rgb, 255))
            changed += 1
    if changed == 0:
        raise ValueError("GENERATED_PART_NO_DRAWN_PIXELS")
    output_part.parent.mkdir(parents=True, exist_ok=True)
    out.save(output_part)
    return {
        "schema": "vtuber/one-part-reference-edit-result-v1",
        "role": job["role"], "output_part": str(output_part),
        "new_colored_pixels": changed, "transparent_mask_pixels": green,
        "unchanged_non_mask_pixels": True,
        "native_animation_verified": False,
        "style_and_hidden_geometry_visually_verified": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    p = parser.add_subparsers(dest="command", required=True)
    one = p.add_parser("prepare")
    one.add_argument("--master", type=Path, required=True)
    one.add_argument("--template-slot", type=Path, required=True)
    one.add_argument("--target-mask", type=Path, required=True)
    one.add_argument("--base-part", type=Path)
    one.add_argument("--role", required=True)
    one.add_argument("--output", type=Path, required=True)
    one.add_argument("--padding", type=int, default=64)
    two = p.add_parser("apply")
    two.add_argument("--job-dir", type=Path, required=True)
    two.add_argument("--generated", type=Path, required=True)
    two.add_argument("--output-part", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare(master=args.master, template_slot=args.template_slot,
                         target_mask=args.target_mask, base_part=args.base_part,
                         role=args.role, output=args.output, padding=args.padding)
    else:
        result = apply(job_dir=args.job_dir, generated=args.generated,
                       output_part=args.output_part)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
