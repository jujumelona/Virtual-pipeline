# Template-grounded, one-part-per-generation VTuber art contract
2026-10-16

## Definitive correction

Image AI is a **part-by-part illustrator** after reference-template review, not
merely a master-portrait painter. The prior “master-only, Colab must segment
everything” contract gave the wrong role to the image model. The earlier
“generate generic oval mouth internals in Colab” implementation also failed
to preserve individual anime character styles. **Do not reactivate it
automatically.**

The templates teach **segmentation geometry and movement ownership**, not
a character design to copy. Distinct tasks must use the template part slot,
the current character master and any already-approved adjacent part as
visual references during each individual image generation call.

## Actual reference template sources to inspect before drawing

1. Live2D [official SD Boy/Girl PSD-based template](https://docs.live2d.com/en/cubism-editor-tutorials/template/): navigate Head/Body, examine per-element example layers, linework, paint and necessary hidden extensions. This is structurally useful but its SD proportions must not override the character style.
2. Live2D [official illustration processing](https://docs.live2d.com/en/cubism-editor-tutorials/psd/): white/iris/lash, lips/inside mouth, ear/neck, upper-arm/forearm/hand, hair depth.
3. Inochi Creator [official Aka tutorial](https://docs.inochi2d.com/en/latest/creator/first-model/tutorial01.html): valid **head-only** PSD-layer example; do not claim it supplies arms/full-body slots.
4. [PSD2Live CC0 example PSDs](https://github.com/tsunehimatoi/psd2live-examples): genuine layered artworks to study. Check per-case material/license; do not mechanically copy an example character.
5. Local structural reference registry: `docs/image_ai_kits_v2/source/EXISTING_TEMPLATE_SLOT_REGISTRY.json`. A registry URL is not a record that an actual PSD was visually opened.

## Drawing tasks: ONE art generation action per individual part

- **BODY face:** complete character master first, then face base *without*
  duplicate eyes/mouth; left/right ears and brows; left/right eye white,
  iris and upper lash; nose; closed lip line; open mouth dark cavity;
  upper teeth; tongue; neck with hidden extensions; torso; upper arm,
  forearm, hand for each side; legs and feet for full-body.
- **HAIR:** front, back, side left/right. Long strands, ponytails, hair
  roots and hidden underlayers only if part of the actual design.
- **OUTFIT:** front/back garment panels, independent sleeves left/right,
  collar, separately moving ribbon or hem, hidden inner sleeve seams.
- **ACCESSORY:** the actually chosen accessory alone: attachment base,
  independently moving fronts/backs and asymmetric left/right shapes.
- **3D:** the above 2D RGBA parts are not a substitute for meshes and bones.
  Keep separate 3D turnarounds.

The artist **generates each individual part** (not just cuts a painted group
out of an image), including the initially hidden area beyond the silhouette
where it might become exposed by moving the rig. Every result uses the same
full image canvas, RGBA with genuine transparency outside its part.
Do not replace fine anime lips/eyes with plain SVG icons or dark oval shapes.
For stable neutral display, drawing groups with alternative expression states
are excluded from the neutral composite.

## New 2D artwork ZIP format

```text
outputs/master.png
part_art/_order.txt                # ordered top to bottom, one relative path per line
part_art/eye.left.white.png        # full canvas, only this art
part_art/eye.left.iris.png
part_art/eye.left.upper.lash.png
part_art/mouth.close.png
part_art/mouth.open.png
part_art/mouth.tooth.t.png
part_art/mouth.tongue.png
part_art/face.png
part_art/neck.png
... other character-specific parts ...
reference_views/<each required view>.png
expression_refs/mouth_closed.png   # BODY only
expression_refs/mouth_open.png     # BODY only
```

This is a **source-art data package**, not an authored PSD/Cubism/Inochi
project. The image model draws PNGs. Colab parses `_order.txt`,
checks actual RGBA and matching full-canvas dimensions, and creates the PSD.

## Colab routing and evidence

- `tools/vts_source_only_pack.py`: validates master and multi-view, detects `part_art/`.
- `tools/vts_authored_part_art.py`: rejects missing order, missing/duplicate
  layers, non-RGBA/opaque-fake-background PNGs and canvas mismatch. Produces a
  layered PSD and `neutral_reconstruction.png`; does **not** claim semantic
  correctness from filenames.
- `tools/vts_multiview_runtime.py`: uses authored PNG PSD as the input and
  does not run See-through again when the authored art is available.
  Without parts, the legacy See-through inference remains available.
- `tools/vts_artwork_export.py`: no automatic crude ellipse mouth injection.
- `tools/update_source_only_body_kits.py`: canonical updater for exactly
  20 2D image-AI instruction ZIPs (5 model modes x 4 asset roles).
  The 4 3D ZIPs are unaffected.

## Verification levels / limits

- Current focused test checks RGBA separation, strict order, PNG transparency,
  missing/extra part rejection, preservation of the neutral master appearance
  in a fixture, and that all 20 instructions state the reference-first model.
- High-quality style resemblance, truly read PSD reference template, correct
  occluded artwork, alignment of regenerated parts across angles, and actual
  VTube Studio or Inochi2D motion are **not proved by file structure**.
- Model-native editing: PSD2Live can import actual PSD for Live2D, but the
  official Inochi2D export/rig path remains a separate unverified task.
- All four workflows (authoring, visual validation, PSD processing,
  native rigging) must pass their own criteria to claim production completion.
