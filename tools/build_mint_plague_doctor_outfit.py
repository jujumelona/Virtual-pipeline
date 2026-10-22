"""Build an honest FACE-compatible alpha-only OUTFIT intake ZIP.

The actual clothing pixels were generated to match the user's existing mint-eye
plague doctor reference. A separate face master was not available, so pixel
registration and Live2D rigging are NOT claimed as verified.
"""
from __future__ import annotations

import base64
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets/user_character/mint_plague_doctor/outfit_hoodie_transparent.png.b64"
CANVAS = (1536, 1920)


def build(destination: Path) -> dict:
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    raw = base64.b64decode(SOURCE.read_text(encoding="ascii"), validate=True)
    with Image.open(BytesIO(raw)) as src:
        src.load()
        if src.format != "PNG" or src.mode != "RGBA":
            raise ValueError("ACTUAL_TRANSPARENT_RGBA_ART_REQUIRED")
        alpha = src.getchannel("A")
        amin, amax = alpha.getextrema()
        if amin != 0 or amax < 200:
            raise ValueError("ARTWORK_IS_OPAQUE_OR_EMPTY")
        bbox = alpha.getbbox()
        if not bbox:
            raise ValueError("EMPTY_HOODIE_CUTOUT")
        cropped = src.crop(bbox)

    # This is a rigging-safe layout transform, not a new synthesized body.
    # The neck opening is intentionally lower than the FACE portrait, so the
    # face and hair assets can cover it. Final registration is not proven.
    canvas = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    max_width, max_height = 1120, 1190
    scale = min(max_width / cropped.width, max_height / cropped.height)
    size = (round(cropped.width * scale), round(cropped.height * scale))
    costume = cropped.resize(size, Image.Resampling.LANCZOS)
    dx = (CANVAS[0] - costume.width) // 2
    top = 710
    if top + costume.height > CANVAS[1]:
        top = CANVAS[1] - costume.height
    canvas.alpha_composite(costume, (dx, top))
    outpng = destination / "outfit.png"
    canvas.save(outpng, optimize=True)
    if canvas.getchannel("A").getextrema()[0] != 0:
        raise ValueError("MASTER_TRANSPARENCY_LOST")
    if canvas.getchannel("A").getbbox() is None:
        raise ValueError("MASTER_NO_CLOTHING")

    manifest = {
        "schema": "vtuber/user-outfit-artwork-v1",
        "character": "original_mint_green_eyes_female_plague_doctor",
        "asset": "outfit",
        "scope": "upper",
        "input_contract": "tools.vts_see_through_only._read_master",
        "canvas": list(CANVAS),
        "source": "Adobe Firefly PNG + original background removal",
        "source_cutout_canvas": "single flat RGBA garment, not fabricated individual layers",
        "original_identity_preserved": {
            "existing_mint_green_eyes": "not modified",
            "existing_black_white_hair": "not modified",
            "existing_black_beak_mask": "not modified; face accessory is separate",
            "outfit_style": "black matte hoodie, dark red hood lining, silver zip, loose sleeves"
        },
        "part_art": False,
        "see_through_separation_required_if_full_layered_psd_desired": True,
        "pixel_registered_to_existing_face": False,
        "pixel_registered_to_existing_hair": False,
        "real_live2d_rig_or_vtube_studio_verified": False,
        "output_master_size": list(CANVAS),
        "outfit_alpha_bounds": list(canvas.getchannel("A").getbbox()),
        "warning": "The original face artwork PNG was unavailable in this run. Align with that FACE before treating this as a final composite; no body, face, hair or mask has been invented."
    }
    readme = """# OUTFIT ARTWORK — 민트 눈 여성 역병의사\n\n"""
    readme += """기존 민트색 눈/검정·흰색 헤어/검정 부리형 마스크를 바꾸지 않은 후드티 의상 원화만 포함합니다.\n\n"""
    readme += """- 원화: outputs/master.png (1536x1920 RGBA, 투명 배경).\n"""
    readme += """- 2D upper 구도, 별도 BODY ZIP 요구하지 않음.\n"""
    readme += """- mask와 얼굴/헤어는 여기서 그리지 않았습니다.\n"""
    readme += """- 독립 파츠가 생성된 것이 아니므로 part_art/_order.txt가 없습니다. See-through 분리가 필요한 입력입니다.\n"""
    readme += """- 이전 실제 FACE master를 확보하지 못했으므로 픽셀 단위 목/어깨 정렬은 아직 미검증입니다.\n"""
    readme += """- outfit.zip 업로드 전에 FACE/HAIR와 캔버스, 비율, 목 연결을 합성 검수하십시오.\n"""
    readme += """- 이미지 AI 원화 품질과 실제 방송용 3D/2D 리깅 성공 여부는 별도 검증해야 합니다.\n"""
    zipfile = destination / "outfit__ARTWORK.zip"
    with ZipFile(zipfile, "w", ZIP_DEFLATED) as z:
        z.write(outpng, "outputs/master.png")
        z.writestr("00_READ_FIRST.md", readme)
        z.writestr("metadata/artwork_report.json", json.dumps(manifest, indent=2, ensure_ascii=False))
    with ZipFile(zipfile) as z:
        assert z.testzip() is None
        assert "outputs/master.png" in z.namelist()
        with Image.open(BytesIO(z.read("outputs/master.png"))) as verify:
            assert verify.mode == "RGBA" and verify.size == CANVAS
    (destination / "outfit_report.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(build(args.output), ensure_ascii=False, indent=2))
