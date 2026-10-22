# RE:ARCHIVE | CC0 rig reuse for a high-end mint-eyed VTuber

**Status:** reproducible retarget tooling delivered. **NO new rig/model is claimed until an actual CC0 source project, real painted per-part images, PSD2Live MCP edits and native pose QA succeed.** The four supplied design sheets are references, NOT already separated transparent parts.

## Correct source and license

Use the SHA-pinned fixture downloader already included in this repository:

```bash
python -m tools.vts_open_quality_cases --case hiakari-inori --output /workspace/cc0-hiakari
# Fallback/reference only:
python -m tools.vts_open_quality_cases --case kirishima-mio --output /workspace/cc0-mio
python -m tools.vts_open_quality_cases --case star_lan --output /workspace/cc0-starlan
```

These examples have **CC0 1.0** assets according to their individual upstream manifest and licenses; the source **PSD2Live software is GPL-3.0, separately licensed**. Every download checks the exact archive size and SHA-256 and rejects unsafe extraction. A CC0 example does **not** prove its original art quality is good enough for a high-end finished avatar.

- [Hiakari Inori](https://github.com/tsunehimatoi/psd2live-examples/tree/main/cases/hiakari-inori): **primary rig topology** for long sleeves, collar and hair, seven confirmed simulation groups and original editable `.psd2live` / PSD. Upstream workflow guide refers to **41 production layers**, but the actual pinned final PSD has **33**. Its preview records observed motion/physics activity, not actual broadcasting certification. **Actual pinned final PSD audit: 33 painted raster layers at 2048×3072**; the older production guide discusses 41 intermediate layers and must not be treated as final. Original archive ~659.7 MB. **Animal ears and three animal tails cannot be transplanted as head-attached twin tails without new geometry, anchors and physics.**
- [Kirishima Mio](https://github.com/tsunehimatoi/psd2live-examples/tree/main/cases/kirishima-mio): facial registration, eye/mouth/neck seam examples, original PSD and editable project; upstream author reports 27 PSD layers; avoid transferring its simpler art in place of RE:ARCHIVE.
- [star_lan](https://github.com/tsunehimatoi/psd2live-examples/tree/main/cases/star_lan): joint deformation / texture density / atlas techniques and editor project; not a female eye/cloth replacement base.

**One source rig, multiple reusable techniques.** Never merge incompatible MOC3 files or copy raw physics IDs across characters.

## Three independently inspected real final PSDs (2026-10-22)

SHA-pinned GitHub Actions downloads and PSD parsing succeeded for **all three** CC0 cases. These are actual source PSD counts, **not** ArtMesh counts:

| Original source | Canvas | Actual raster leaf layers | Main reusable structure | Incompatible features |
| --- | --- | ---: | --- | --- |
| Hiakari Inori | 2048×3072 | 33 | eyes ×8, mouth ×2, outfit ×8, head/neck + long sleeve simulation | animal ears / three animal tails, no native RE:ARCHIVE twin-tail geometry |
| Kirishima Mio | 2048×3072 | 27 | human face/eyes/mouth/neck, simple cloth registration | basic hair and clothing, not premium sleeves |
| star_lan | 1280×1280 | 24 | multi-atlas/raster-scale and joint texture workflow | only one mouth raster, less suitable for lip-sync source |

The real original transparent PSD raster layer crops and bounding rectangles are available as verified CC0 GitHub Actions artifacts (see `.github/workflows/rearchive-cc0-real-source-audit.yml`). Their **source sprites are templates, not new high-quality RE:ARCHIVE artwork**. We retain the user's four sheet illustrations only in their local package, not in the public repository.

## Art-first high-end identity

- Primary visual identity: user's fourth Live2D concept sheet (RE:ARCHIVE).
- Adult female, large mint-to-lime eyes with separate sclera, iris, pupils, independent catchlights, individual eyelashes, full blink underpainting.
- Black/white long twin tails with mint micro-highlights and pink-mint bows; hidden scalp and hair roots fully painted, front/side/back ribbons as separate swaying source artwork.
- Black/white high-detail cyber-gothic clothing, large floating sleeves, chest/neck DNA preservation capsule for "last descendant preserving previous humanity and Earth memory"; subtle precision-machined joints rather than a full-robot exoskeleton.
- The original four sheets differ visually. Do **not** paste panels together or redraw the face on every part. The corrected master art must be approved FIRST, then physically separated from that SAME master and underpainted behind occlusions.
- Pink/lime highlights allowed, green cannot become the main garment fabric, no plague-doctor mask until neutral facial deformation is qualified.
- Premium colored line art, detailed fabric and rim light are requirements, *not* to be flattened away just to simplify rigging.

## Actual native reuse: **texture replacement in the existing project**

PSD2Live [upstream MCP AUTHORING docs](https://github.com/tsunehimatoi/psd2live/blob/master/docs/en/agent/MCP_AUTHORING.md) defines **`layer_replace_image`** with `layer_id`, `path`, `fit` and `rebuild_mesh`. **`rebuild_mesh=false` keeps the mesh, keyforms and bindings**, and updates texture/UV, but does not magically adjust changed silhouettes. For large new shapes, add new artwork and rig it separately; do not distort an old mesh to fake compatibility.

1. On a machine with newer running PSD2Live and matching `mcp_proxy.py`, open the original **CC0 .psd2live** project.
2. Use `workspace_inspect scope=objects` and **`layer_get_texture`** on **real layer IDs**, record each `canvas_rect=[x,y,width,height]`. Do not copy IDs from documentation or invent them.
3. Paint actual **per-part PNG transparent textures** from the approved RE:ARCHIVE master. Eye whites, irises, upper/lower eyelashes, mouth interior, face base, forehead/hidden ears, twin tails, sleeve material and capsule require independently authorable pixels.
4. Save per-part PNG files (not screenshots of the contact sheet) in a work directory; run `python -m tools.vts_cc0_rig_retarget --source-project ... --source-case hiakari-inori --output ...` to make a *template plan* with SHA source binding.
5. Fill the plan's real `layer_id`, `expected_canvas_rect`, `role`, and `image` relative to `--image-root`. One image per source layer. The tool refuses transparent/size-invalid art, mismatched bounds, invented paths, changed source hashes, forced mesh rebuilds and destructive source writes.
6. Only after paints/IDs and a **local modern PSD2Live MCP editor** are available: `python -m tools.vts_cc0_rig_retarget --source-project /workspace/cc0-hiakari/case/.../project/hiakari_inori_layers_v3.psd2live --source-case hiakari-inori --plan /work/retarget_plan.json --image-root /work/painted_parts --psd2live-source /path/to/psd2live-modern --output /work/retargeted_v1`.
7. Output is always a NEW `REARCHIVE_retarged_EDITABLE.psd2live` and separate `native/` MOC3 family; **original must remain byte-identical**. Real native pose checks block pass if geometry/eyes/mouth/parameter isolation fail; however actual identical-character visual QA and VTube Studio tracking remain separately required.

**This is not a run-it-on-Colab standalone model swap.** Modern PSD2Live MCP editing requires a reachable running editor and compatible proxy; the existing Colab See-through path is for art-to-PSD when suitable parts are missing. Do not use old v3.3.1 CLI as if it implements the modern image-replacement operation.

## Rig hierarchy target (design contract, not a completed rig)

```
BODY_ROOT
  body_stabilize / body_sway / shoulders
  left_sleeve + right_sleeve => independent motion or reuse Inori sleeve rig
  head_transform
    neck + face base + ears
    left_eye: sclera, iris, pupil, glint, upper/lower lashes/lids
    right_eye: sclera, iris, pupil, glint, upper/lower lashes/lids
    mouth: lips open/closed, inner-mouth, teeth/tongue optional
    hair_back / left_tail / right_tail / hair_sides / hair_bangs
  capsule_pivot / capsule_chain (NEW rig required; can borrow damping approach)
```

The user's target Cubism FREE budget (<=100 ArtMeshes, <=30 parts folders, <=50 deformers, <=30 parameters, <=3 blendshapes, <=3 ArtPaths, 2048x1 texture atlas) must be **measured on resulting real native model**, not equated to the source PSD's ~41 layer count. Complex style can exceed FREE; quality must not be sacrificed silently. Full quality master/PSD can be retained while FREE-delivery variants are simplified only when explicitly supported.

## Validation checkpoints

1. Original source ZIP hash and CC0 manifest verified.
2. Artistic-quality approval on one RE:ARCHIVE master (detail match to user's sheet 4).
3. Independent genuinely painted eye, mouth, face, hair roots, sleeve/collar, and accessory layers available; correct underpaint.
4. Exact layer IDs/bounds and compatible silhouettes, source project not overwritten.
5. Texture atlas fit, reference closeups at normal/45°/blink/visemes; hair/sleeve/capsule physics preview.
6. Native runtime checks plus FREE editor budget; VTube Studio webcam and lip tracking where applicable.
7. Only then mark `BROADCAST_READY`. Code-level tests alone are NOT a visual acceptance.

**Current verified scope:** code and reproducible tests for non-destructive retarget workflow, source examples and official MCP operation; no modified CC0 runtime model or completed RE:ARCHIVE mesh has been generated here.

## Actual GitHub-native evidence (2026-10-22)

- [Successful **real** eye-layer native retarget](https://github.com/jujumelona/Virtual-pipeline/actions/runs/39762583687): cloned the original Hiakari CC0 `.psd2live` project without changing its SHA-256, found `irides-r` and `irides-l` by true native layer IDs, used `layer_replace_image(rebuild_mesh=false)`, saved a new editable project and exported a valid MOC3/model3.json, physics and motions. The source PSD crop differs by up to six pixels from the rig layer: the original rig rect was retained rather than altering its mesh.
- [Successful independent **modified MOC3** pose rendering](https://github.com/jujumelona/Virtual-pipeline/actions/runs/39765618353): actual Cubism Core wrapper rendered neutral, ±45 yaw, blinking, gaze, open/closed mouth, combined facial expressions. Activity and native connected-component geometry checks passed. **This is not a VTube Studio tracking test**.
- **Visible art judgment: FAIL for the requested RE:ARCHIVE identity**. The model still has Hiakari's fox ears/tails and red costume, and only both irises are newly colored. Hair silhouette, face, DNA capsule and original 4-sheet look are not yet transplanted.
- Actual stage-1 artifact is stored under the successful transplant run as `rearchive-real-iris-transplant-audit`, pose screens under `rearchive-actual-native-poses-not-final-art`. Original CC0 artwork remains identifiable and must not be presented as the user's final original character.
- Stage 2 experiments on nine existing hair, ribbon and garment layers are in [the separate CI workflow](../.github/workflows/rearchive-real-costume-transplant.yml). That workflow may only call itself complete after a real project save, native export and independent MOC3 pose render. Even its success would only prove source-geometry texture compatibility, **not** high-end re-authoring, elimination of animal attributes, addition of genuine double twin-tails or DNA-cap physics.
