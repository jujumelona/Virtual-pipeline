# High-reuse VTuber parts: actual integration status

Date: 2026-10-16

## Policy: only parts with nearly invariant basic geometry

- **2D BODY (five ZIPs):** oral cavity, upper teeth and tongue are reusable *geometry*. Recolor/reposition independently for each character. The image AI draws `outputs/master.png`, all required angle references, plus fully authored `expression_refs/mouth_closed.png` and `expression_refs/mouth_open.png`, preserving a single character and style. **It does not cut sprites or author PSD/masks.**
- **2D BODY, eyes:** eye whites are reusable only when actual outer eye bounds and clipping are verified; pupils are often already inside the iris and must not be drawn twice. Do not fabricate them from a generic whole-eye SAM19 mask.
- **2D HAIR/OUTFIT/ACCESSORY:** no oral/eye graphics added. Hair shape, garment seams and ornament shapes are design-specific. Generic attachment templates do not replace source art.
- **3D:** separate mesh/bones/materials workflow; do not insert 2D mouth PNG sheets into a 3D rig.
- **Native PSD2Live:** `MOUTH_CLOSE`, `MOUTH_OPEN`, `TOOTH_T` and `TONGUE` are recognized semantic types; opacity switching uses `ParamMouthOpenY`. However merely supplying sidecar artwork is *not* keyform integration.

## Actual code paths now implemented

1. `tools/image_ai_source_only_contract.py` defines the artwork-generation brief for the five 2D BODY modes.
2. `tools/update_source_only_body_kits.py` regenerates exactly the five matching published 14-MD ZIPs and preserves all other 19.
3. `tools/vts_reusable_mouth_parts.py` finds a unique closed mouth and lower-face anchor from already separated Colab/See-through layers. Only when geometry is unambiguous, it rasterizes **three independent alpha-containing PNGs**:
   - `reusable_parts/mouth/mouth_open.png`
   - `reusable_parts/mouth/tooth_t.png`
   - `reusable_parts/mouth/tongue.png`
4. `tools/vts_artwork_export.py` packages the PNGs and `metadata/reusable_mouth_parts.json` in BODY artwork ZIPs. It does not mix them into the visible neutral PSD, so the original drawing remains pixel-identical.
5. The final PSD2Live package contains that artwork ZIP at `source_artwork/...`, along with the model files.

## Gate and outstanding work

- **Already an authored open mouth?** Skip procedural graphics to prevent double mouths.
- **Cannot identify exactly one narrow closed mouth and suitable lower-face position?** Skip instead of guessing; preserve original art.
- **Native binding:** STILL NOT IMPLEMENTED. The procedural mouth PNGs are generated reusable artwork resources; they do not yet become active `ParamMouthOpenY` components of the native MOC3. The PSD2Live importer must create the exclusive mouth layer group and a real MOC3 pose QA must prove the closed/open transition before certification.
- **Visual appearance:** The generic colors are starting geometry, not guaranteed style matching. When original open-mouth drawing is available, prefer it over a procedural stand-in after actual artwork comparison.
- **Eye whites/pupil:** do not auto-generate until eye contours and nonduplication are verified.
- **Main tests:** synthetic image unit tests verify separate PNG alpha, original raster unchanged, duplicate refusal, invalid anchor refusal; they do not certify real model output.

## Source/license references

- MIT procedural SVG mouth reference: https://github.com/Amoner/lipsync-engine
- Official PSD2Live mouth/eye labeling: https://github.com/tsunehimatoi/psd2live/blob/master/docs/en/spec/PSD_LAYER_SPEC.md
- PSD2Live code: `src/main/kotlin/io/github/psd2live/core/RigBuilder.kt`, tags `MOUTH_CLOSE`, `MOUTH_OPEN`, `TOOTH_T`, `TONGUE`.
- Live2D official art processing: https://docs.live2d.com/en/cubism-editor-tutorials/psd/

This implementation draws original procedural pixels with Pillow, rather than distributing third-party sample characters or their artwork.
