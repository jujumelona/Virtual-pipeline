# RE:ARCHIVE actual stage9 engineering rig status (2026-10-23)

## Proven native outputs

- **Stage9 independent DNA ArtMesh + swing physics + visible front position:** official PSD2Live v3.6 editable `.psd2live` project, native `.moc3`, `.model3.json`, `.physics3.json`, animations and pose frames. The [real stage9 verification](https://github.com/jujumelona/Virtual-pipeline/actions/runs/39799469580) passed actual Cubism Core rendering and changed 954 chest-region pixels after the pendant's draw-order correction. It **does not** prove final art quality.
- **Stage9 2048×2048 / one-page texture:** the [real stage9 2048 runtime verification](https://github.com/jujumelona/Virtual-pipeline/actions/runs/39803643002) passed. It has **the same .moc3 binary and physics file** as stage9 4096. The FREE editor ArtMesh ≤100, folders ≤30, deformers ≤50, parameters ≤30, blendshapes ≤3, ArtPaths ≤3 criteria have **not** been exhaustively verified.
- **Single-front regenerated original-identity draft:** [artwork workflow](https://github.com/jujumelona/Virtual-pipeline/actions/runs/39801720943) created a reference single-front JPEG and face/dress zoom previews from the requested RE:ARCHIVE concept (mint eyes, black/silver twin-tails, DNA pendant, black/white science-gothic). **This is not a layered PSD, not split into Live2D parts, and is not transplanted into stage9.**

## Do not claim complete

High-end face/garment matching the fourth user reference sheet is **FAIL**. The working rig still derives significant geometry and artwork from a CC0 example (Hiakari Inori). The Adobe standalone reference is an aesthetic draft, not independently rigged. VTube Studio camera tracking has not been tested. The Photoshop output is a 2048-pixel resized edit, not a restored full-resolution layered original.

## Repositories and cleanup policy

- All authoring scripts and CI workflows remain on **main** for repeatability. Development/test files may stay while the user works on the rig. **Do not remove work-in-progress assets now.**
- Candidate removable **only after** the fully re-authored face, clothes, hair and capsule are installed, user quality approved and final artifacts archived:
  - `rearchive_temp_assets/MASTER_FRONT_REFERENCE_JPEG_BASE64.txt` (temporary artwork delivery encoding)
  - intermediate `rearchive-` numbered experimental GitHub Actions artifacts, which also have built-in 14-day expiration.
  - draft-only working examples, *if they are not required to reproduce the final native rig.*
- Keep final art sources and working executable authoring code, current CI, attribution/license records and final model. Never silently erase original references and rollback points.
- Code and docs are tracked on main; oversized PSD2Live and MOC3 outputs are uploaded as GitHub Actions artifacts, **not committed as binary Git blobs**.

## Actual checks before calling it complete

1. Create single-source-face/head/hair/outfit/accessory transparent PSD/PNG layers **with underpaint** matching the approved fourth concept sheet.
2. Regenerate or retarget native ArtMeshes and keyforms for face/eyes/mouth/twin-tail roots/neck/dress/sleeves and new pendant.
3. Independently render parameter extremes and inspect eye alignment, seams, exposed hidden areas, layer stacking, clothing sway and DNA motion.
4. Confirm the actual **FULL** FREE editor budgets or honestly label the asset as only a runtime 2048 atlas, without implying a FREE authoring guarantee.
5. Open VTube Studio and test input tracking on real hardware.
6. Package final production PSD, all PNG parts, editable project, MOC3, physics, motions, sprites and QA before removing temporary GitHub assets.

**Status:** Technical base verified; premium original-character artwork not completed.
