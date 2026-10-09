# 2D/3D character + replaceable wardrobe: implementation audit

Status: verified against repository main and primary-source editor manuals,
2026-10-09. Engineering recommendations, not a claim of automatic perfect rigs.

## Evidence and fundamental distinction

- Live2D official *Illustration Processing*: PSD artwork is subdivided into hair,
  facial and body layers; hidden surfaces have to be completed, and collars,
  cardigans and swinging ribbons should be separate when independent motion is
  wanted. https://docs.live2d.com/en/cubism-editor-tutorials/psd/
- Live2D official *Import PSDs*: adding or replacing layers of a model is an
  editor operation; an image is not an automatically compatible .moc3.
  https://docs.live2d.com/en/cubism-editor-manual/psd-import/
- Live2D official *Notes on Pose Switching*: replacing clothing and arm parts
  requires the correct parameter keys/motion; swapping texture alone can break
  motions. https://docs.live2d.com/en/cubism-sdk-tutorials/attention-changepose/
- Inochi Creator PSD workflow: importing PSD works, but blend and visibility
  may require manual adjustment; Live2D model files are not Inochi2D files.
  https://docs.inochi2d.com/en/latest/inochi2d/faq.html
- VRoid XWear official: avatar (.vroid / VRM / XAvatar), compatible dress-up
  outfit (.xwear), fitting, mesh deletion, blend shapes and animation QA are
  separate operations. https://vroid.pixiv.help/hc/en-us/articles/38722733769241-Getting-Started-with-the-Dress-up-Feature-for-those-who-want-to-dress-up-their-characters
- VRoid XWear data supports a set, tops, gloves, shoes, etc. This is not
  equivalent to bone-parenting a rigid prop.
  https://vroid.pixiv.help/hc/en-us/articles/39513229598233-What-is-XWear
- Blender official armature deformation: mesh vertices need bone weights.
  A rigidly bone-parented mesh will not bend at the elbow/knee.
  https://docs.blender.org/manual/en/latest/modeling/modifiers/deform/armature.html

**Current modular VTuber input contract:** Author a fully covered adult
anime VTuber wearing an opaque, seamless production base cover matching the
natural face/hand skin color. The cover must be plain, with no gray suit,
zipper, collar or seam. This is NOT an exposed-body illustration.
2D hair and future fashion outfits remain separate assets; 3D reconstruction
keeps a consistent hairstyle across views. 3D garment fitting and automated
wardrobe switching are not implemented.

## Source-of-truth active code contract (reviewed)

| Boundary | Actual code | Present behavior | Missing for wardrobe |
|---|---|---|---|
| Colab | `notebooks/VTuber_Commercial_Pipeline_Colab_v8.ipynb` | TASK character/accessory + ACCESSORY_SUBTYPE rigid prop / 2D outfit / 3D XWear | 3D outfit images -> automatic garment rig still missing |
| 2D sheet | `vtuber_pipeline/sheet_contract.py` | 1 master + 6 body/face sheets = 20 base parts | advanced costume motion and additional accessory parts |
| 2D layer validation | `vtuber_pipeline/two_d/build.py` | 20 base semantic layers and PSD/ORA handoff | wardrobe variant grouping/visibility |
| Live2D | `vtuber_pipeline/two_d/cubism_handoff.py` | handoff PSD + spec | Cubism Editor import/parameterized outfit switch |
| Inochi | `vtuber_pipeline/two_d/inochi_bridge.py` | only marks complete if SDK INP output validates | outfit parameter mapping/visibility keys |
| 3D | `vtuber_pipeline/avatar/build.py` | 4 real view inputs -> TripoSR+canonical rig -> VRM | separated cloth mesh/body masking/skinning |
| 3D weight | `vtuber_pipeline/avatar/rigging.py` | humanoid and hair mesh weights | independently skinned costume |
| Static accessory | `vtuber_pipeline/accessory/bake.py` | unchanged rigid parent-bone GLB merge; rejects glTF skins | proper garment fitter/retarget/cloth clip; never reuse prop baker for outfits |
| 2D outfit utility | `tools/outfit_variant_pack.py` | integrated in Colab ④/⑤: preserve base body and replace front/back garment cells, then rerun 2D route | rich independent sleeve deformation and runtime wardrobe toggles |

**Do not claim clothing support from the static-accessory baker.**
**Do not claim an image-only 3D garment is production-ready skinned.**
**Current avatar/build.py merges the observed costume silhouette/texture into
its canonical skinned avatar mesh rather than producing a detachable outfit
mesh. A VRM with bulky baked-in clothing is not automatically wardrobe-ready.
For future XWear dressing, use a fully covered neutral production reference
with a skin-tone opaque cover, not an undressed or gray-fabric body.
The cover is baked into the current base image / resulting 3D appearance;
it is not an automatically detachable garment. Verify any subsequently
fitted real wearable mesh and skinning in VRoid or Blender.
A skinned base alone is NOT an automatically switchable-wardrobe VRM.**
**Do not call prepared PSD/ORA a Live2D .moc3 or Inochi .inp.**

## Recommended minimum image INPUT per mode

These are *engineering defaults*, not vendor-mandated pixel counts. Quality
depends on composition and detail, not merely the export resolution.

| Task | Recommended source images | Ratios | What gets generated |
|---|---|---|---|
| 2D base | front reference 1 + 6 semantically split sheets: **7 PNG** | front/body 2:3; face/eyes/mouth 1:1; arms/hands 4:3 | 20 fully covered, hair-free, separate-wardrobe RGBA base parts |
| 2D basic wardrobe variant | same base character + **1 costume-only 2×2 sheet** with four garment cells | sheet 4:3 | 4 separate outfit parts (front/back + left/right sleeves), requiring movement and editor validation |
| 2D elaborate outfit | body-proportional front/back garment plus independently moving left/right sleeve, collar, hem/skirt, ribbon | individual part sheets by need; don't crowd | requires extending base part taxonomy/rig, no fixed 2-layer guarantee |
| 3D base | front/back/left/right skin-colored full-body 4 views + face closeup = **5 views in 3 PNG files** | each body view 2:3, paired sheets 4:3, face 1:1 | fully covered skin-tone basewear VRM; independently skinned wardrobe NOT yet supported |
| 3D outfit design references | front/back/left/right outfit on SAME T- or A-pose/body + optional fabric and collar/hem closeups = **4 views + 1–3 detail refs recommended** | body view 2:3, closeups 1:1 | *reference material* for mesh/texture construction, not a fitted .xwear |
| 3D wearable import | base VRM (1) + a separately modeled **riggable garment** (.xwear for VRoid editor, or suitably skinned GLB through an implemented Blender adapter) | file formats, not image ratios | avatar fitting, skinning, clip/mask and motion validation before export |
| Rigid accessory | base VRM 1 + 1–8 single-object image refs | square recommended for isolated props | rigid static bone-parented meshes; NO articulated wardrobe |

When AI outputs a smaller image, the loader should verify **actual aspect ratio,
alpha transparency, cell order and content** before extracting cells; neural
upscaling can improve sharpness but cannot reconstruct missing garment
topology, back-of-body surfaces, skin weights or missing layers.

## Practical master defaults (NOT exact generation pixel demands)

- 2D master: vertical **2:3**, frontal neutral, stable margins and consistent
  image landmarks, direct design identity reference for remaining sheets.
- 2D face/eyes: **1:1**, 2×2 grid, 1 part/cell, true transparent RGBA.
- 2D back/front/left/right hair: **2:3** sheet, 2×2 grid.
- 2D body: **2:3** one-cell image. 2D arms/hands: **4:3** 2×2 grid.
  Outfit-only variant: **4:3** 2×2 grid with four independent cloth parts.
- 3D orthographic: two **4:3** sheets split into two **2:3** full-body
  cells, A-pose consistent across all views (not arbitrarily changing poses).
- 3D face closeup: **1:1**, same character (not full-body pixel-coordinate match).
- 3D clothing references: front/back and each side same body + pose, plus
  material/edge details; actual cloth needs mesh fitting and skinning.
- Texture size: use existing 1024/2048 option; **2048 preferred** for close-up
  broadcast when VRAM allows. More atlas resolution not a substitute for geometry.
- SR: split before inference; prefer **2× geometric target** when source supports
  it; use neural 4× only for low-resolution sources that need it, with visual QC.
  Preserve alpha and register/crop using the observed source grid.

## Correct task taxonomy and success claims

1. **Character creation**: 2D base (20 separate covered rigging parts) or
   3D skin-tone covered VRM. The permanent smooth production cover may be
   part of the base; fashion outfits remain separate future assets.
2. **Rigid accessory creation** (hats, glasses, solid hanging items) remains
   bone-parented. The current operation is unsuitable for sleeves, trousers,
   skirt or coats that follow multiple bones.
3. **2D costume variant**: take the original 2D sheet ZIP and a *costume-only*
   source; reconstruct a new variant with unchanged body/face/hair, prepare PSD
   and explicit editor work for deformers/visibility keys. The current variant
   utility supports 4 garment cells; this does not prove rich automatic deformers.
4. **3D costume**, distinct from static accessory despite sharing the user
   interface: for working wardrobe use an externally fitted garment asset
   through VRoid XWear dress-up editor, with export/animation checks. A new Python fitting + skin transfer + body mask + VRM merge backend still
   needs implementation and actual validation before claiming automatic clothes
   from source images. The implemented `tools/wardrobe_handoff.py` only packages
   an existing VRM plus genuine XWear for an external editor; status is
   `editor_import_required`, never `complete`.

Do not delete legacy direct-layer PNG route blindly: it is still selected by
the Colab `provided_layers` option. Remove only after a tested replacement
and corresponding notebook changes.

## Post-audit implementation checkpoints

- `ACCESSORY_SUBTYPE=소품`: existing bone-parented rigid prop path unchanged.
- `ACCESSORY_SUBTYPE=2D 교체 의상`: notebook accepts the original 2D
  sheet ZIP plus `outfit_variant.png`, maintains the original body cell,
  builds a variant full pack, then invokes Live2D or Inochi2D production.
- `ACCESSORY_SUBTYPE=3D 교체 의상(XWear)`: notebook accepts a VRM and an
  existing `costume.xwear`, packages both plus editing instructions as
  `vroid_dressup_handoff.zip`. NOT a fitted/skinned final VRM.
- The README contains one prompt per base sheet, one costume-variant prompt,
  and two 3D fully covered orthographic-reference prompts plus a face closeup.
- Uploads use source image *ratio* and cell geometry, not fabricated exact
  4096 pixel native output claims. The interpreter normalizes after cropping.
- CI test modules: `tests/test_colab_wardrobe_inputs.py`,
  `tests/test_wardrobe_workflow.py`,
  `tests/test_readme_sheet_prompts.py`, `tests/test_sheet_input_loader.py`.
- **Still absent:** automatically reconstructed garment meshes with correct
  bone skinning and clipping, single-model live wardrobe switches for all
  sleeves/skirts and full broadcast pose QA. Claims of end-to-end wardrobe
  completion are prohibited until those features actually pass runtime tests.
