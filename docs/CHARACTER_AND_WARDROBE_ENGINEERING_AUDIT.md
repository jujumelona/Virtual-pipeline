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

**Conclusion:** A FIRST character may wear its default clothes, but a reusable
character must keep independent body/skin, clothing and any wardrobe-specific
arms/leg/sleeves mesh. A neutral, covered underlayer under default outfit is
sufficient; exposing a nude human model is NOT a prerequisite.

## Source-of-truth active code contract (reviewed)

| Boundary | Actual code | Present behavior | Missing for wardrobe |
|---|---|---|---|
| Colab | `notebooks/VTuber_Commercial_Pipeline_Colab_v8.ipynb` | TASK character/accessory | dedicated outfit task |
| 2D sheet | `vtuber_pipeline/sheet_contract.py` | 1 master + 7 sheets = 26 parts | per-costume replaceable sleeves/collar/hem |
| 2D layer validation | `vtuber_pipeline/two_d/build.py` | 26 exact layers and PSD/ORA | wardrobe variant grouping/visibility |
| Live2D | `vtuber_pipeline/two_d/cubism_handoff.py` | handoff PSD + spec | Cubism Editor import/parameterized outfit switch |
| Inochi | `vtuber_pipeline/two_d/inochi_bridge.py` | only marks complete if SDK INP output validates | outfit parameter mapping/visibility keys |
| 3D | `vtuber_pipeline/avatar/build.py` | 4 real view inputs -> TripoSR+canonical rig -> VRM | separated cloth mesh/body masking/skinning |
| 3D weight | `vtuber_pipeline/avatar/rigging.py` | humanoid and hair mesh weights | independently skinned costume |
| Static accessory | `vtuber_pipeline/accessory/bake.py` | rigid parent-bone GLB merge; rejects glTF skins | garment fitter/retarget/cloth clip, not rigid merge |
| First outfit replacement utility | `tools/outfit_variant_pack.py` | can preserve base 2D PNG cells and replace two garment cells | UX connection and rig review |

**Do not claim clothing support from the static-accessory baker.**
**Do not claim an image-only 3D garment is production-ready skinned.**
**Do not call prepared PSD/ORA a Live2D .moc3 or Inochi .inp.**

## Recommended minimum image INPUT per mode

These are *engineering defaults*, not vendor-mandated pixel counts. Quality
depends on composition and detail, not merely the export resolution.

| Task | Recommended source images | Ratios | What gets generated |
|---|---|---|---|
| 2D base | front reference 1 + current 7 semantically split sheets: **8 PNG** | front 2:3; eye/face 1:1; long hair 2:3; body/arms 4:3 | 26 underlying RGBA ArtMesh source parts |
| 2D basic wardrobe variant | same base character + **1 costume-only 2×2 sheet** with two populated garment cells | sheet 4:3 | new front/back outfit and re-rig-ready full 2D input pack; sleeves and moving details need separate authored parts |
| 2D elaborate outfit | body-proportional front/back garment plus independently moving left/right sleeve, collar, hem/skirt, ribbon | individual part sheets by need; don't crowd | requires extending base part taxonomy/rig, no fixed 2-layer guarantee |
| 3D base | front/back/left/right orthographic full-body 4 views + face closeup = **5 views in 3 PNG files** | each body view 2:3, paired sheets 4:3, face 1:1 | one clothed 3D VRM, NOT interchangeable wardrobe |
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
- 2D body and garment: **4:3** sheet, 2×2 grid, base body independent
  from front/back cloth. No opaque fake transparency.
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

1. **Character creation**, with a default clothed appearance AND a distinct
   under-body/skin for possible wardrobe workflows.
2. **Rigid accessory creation** (hats, glasses, solid hanging items) remains
   bone-parented. The current operation is unsuitable for sleeves, trousers,
   skirt or coats that follow multiple bones.
3. **2D costume variant**: take the original 2D sheet ZIP and a *costume-only*
   source; reconstruct a new variant with unchanged body/face/hair, prepare PSD
   and explicit editor work for deformers/visibility keys. The current variant
   utility supports only 2 garment parts, not complex wardrobe auto-rigging.
4. **3D costume**, distinct from static accessory despite sharing the user
   interface: for working wardrobe use an externally fitted garment asset
   through VRoid XWear dress-up editor, with export/animation checks. A new
   Python fitting + skin transfer + body mask + VRM merge backend would have
   to be developed and actually validated before claiming automatic clothes
   from source images.

Do not delete legacy direct-layer PNG route blindly: it is still selected by
the Colab `provided_layers` option. Remove only after a tested replacement
and corresponding notebook changes.
