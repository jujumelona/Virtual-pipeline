# FACE-first image art / Colab handoff repeated QA — 2026-10-17

## Result and scope

**Production artwork quality is not certified.** This audit verifies published instructions, binary reproducibility, input validation, and existing CI checks. It does not establish that a particular image generation service will paint high-quality VTuber art from a ZIP, nor prove native model/rigging success.

| Gate | Observed | Meaning |
|---|---|---|
| Public ZIP inventory | 18 total: 1 2D FACE, 15 scoped 2D assets, 2 3D kits | Correct 2D/3D division |
| Markdown contracts | 18 × 14 = 252 documents | Semantic audit: 0 blockers |
| Binary reproducibility | 18/18 blobs byte-identical to current `build_source_only_kits_v7.js` | Mismatched 16 blobs were rebuilt |
| Python semantic ZIP audit | PASS | [Workflow 39022076124](https://github.com/jujumelona/Virtual-pipeline/actions/runs/39022076124) |
| Fast contract test suite | PASS | [Workflow 39022076066](https://github.com/jujumelona/Virtual-pipeline/actions/runs/39022076066) |
| Independent-image/PSD preflight and dual ZIP checks | PASS: 18 ZIPs / 252 docs / 0 blockers | [Workflow 39022439063](https://github.com/jujumelona/Virtual-pipeline/actions/runs/39022439063) |
| Full CPU pytest discovery | FAIL: 308 failed, 1,139 passed, 1 skipped, 163 errors | [Workflow 39022076044](https://github.com/jujumelona/Virtual-pipeline/actions/runs/39022076044) |
| Generated FACE art style & identity | NOT VERIFIED on latest ZIP | Requires output images for human assessment |
| Colab GPU segmentation, PSD and native rig motion | NOT VERIFIED end-to-end | Structural FACE preflight is not a rig |

## Source fixes validated

1. `face.zip` 14 documents now explicitly describe professional original adult anime VTuber head/neck artwork. `00_MASTER_FIRST.md` contains a direct English production image prompt. The body, shoulders, sleeves and hair are not generated in FACE. A simple vector/mannequin is a FAIL, not a production art deliverable.
2. Master-first workflow: inspect a single professional front portrait before generating separately drawn 3/4, 90° left/right, up/down, neck overlap and 2 mouth states. Reject collage slicing, name-only copies and mirrored profiles.
3. Rebuilt 16 mismatched published artifacts: full catalog byte-comparison now 18/18 and `node tools/build_source_only_kits_v7.js --check` really runs in GitHub Actions alongside `python -m tools.audit_24_image_kits --strict`.
4. FACE post-generation technical preflight requires the master plus 9 registered references and both mouth states, all PNG, same canvas, master shortest side at least 768 pixels; rejects a copied master posing as an angled view, missing/identical mouth refs, and incompatible view dimensions.
5. Colab FACE artifact handoff retains both mouth references, provides `manual_visual_review_required=true`, and explicitly reports `visual_quality_verified=false`. It never reports PSD/MOC3/native rig success for a FACE-only source drawing.
6. Historical `update_source_only_body_kits.py` CLI is prevented from overwriting the 18 current FACE-first image prompts. Current README no longer advertises 24 body-asset ZIPs or AI-generated PSD/masks/isolated parts.

## Manual visual inspection still required

The bad prior example was a crude oval head and cylinder-like neck with pasted-on, minimally rendered eyes; this must be rejected. A suitable example contains anatomically coherent but non-photoreal anime ears, eye corners and multilayered orange irises, painterly hairline-ready scalp and naturally connected neck, consistent jaw/eye structures across angle references.

**Visual references are not embedded in the published Github `face.zip`.** Separate three illustrative face images are available as an optional user-side style-reference ZIP in the current conversation, but cannot substitute for full-resolution production PNGs. Model interpretation and aesthetic consistency remain unverified on the new ZIP.

## Open failure unrelated to the successful ZIP audits

The full CPU test discovery still runs many archived assumptions in `tests/test_image_ai_*24*.py`, BODY/basewear/part-art production contracts, and former 20-part notebook input contracts. These tests cannot pass unchanged after removing the BODY path and replacing 24 ZIPs with 18. **Do not disable them merely to paint the full CI green.** The correct follow-up is to migrate each test to the new FACE/OUTFIT/3D contracts, preserving meaningful assertions (including actual image coverage and native integration), then rerun the full suite. Current fast test success does not override this known CI failure.

## Recommended end-to-end acceptance

Attach the current `face.zip` and, optionally, the three style-reference images to a high-quality image generator. Request only `outputs/master.png` first, inspect the anime artwork and reject primitive geometry; then generate the remaining 11 named views. Upload the 12 actual production PNGs to Colab. Require technical FACE preflight PASS and separate human approval of all 12 views. Only then attempt further part segmentation, composite with the clothed OUTFIT, PSD handoff and actual application motion verification.
