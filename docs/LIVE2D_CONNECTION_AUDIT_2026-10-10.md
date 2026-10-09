# Live2D FREE/PRO connection audit — 2026-10-10

Source: supplied live2d_free_pro_chat_reference_updated.md. Scope remains layered PSD artwork and official Cubism Editor handoff.

## Verified fixes

| Requirement | Correction | Commit |
|---|---|---|
| §5 semantic identities | Check eyebrow before generic eye; preserve foot, ear, ornament and other canonical details | 98ef767 |
| §4 recursive anatomy coverage | Arm, hand, leg, foot, ear, neck, nose, shoe and eyebrow eligible; FREE requests fit remaining 100-layer budget | 98ef767 |
| §3 texture budget | Measure alpha bounding-rectangle areas and 2px margin estimate; emit TEXTURE_BUDGET.md and texture_budget.json without resizing artwork | 8082380 |
| §2/§5 original coordinate frame | Invert the pinned See-through center-square padding/resizing; final FREE/PRO PSD uses input dimensions; external PSD mismatch fails explicitly | 281dea3 |
| §5 native split identities | Preserve hairf/hairb, eyel/eyer, browl/browr, earl/earr and upstream -l/-r suffixes including iris/sclera/lash | 281dea3 |
| §8 output completeness | Package actual Qwen and See-through logs when present; supporting_files lists every final ZIP companion | f5a06b6 |
| §6 PRO registration review | Overlay the actual final PSD composite on the body reference, rather than only the submitted asset input | 6be5338 |

Coordinate mapping was checked against See-through revision df019de5129d6c4b406587a14c3501669441a783: inference/scripts/inference_psd_quantized.py run_layerdiff, common/utils/cv.py center_square_pad_resize and common/utils/inference_utils.py PSD assembly. Native inference restores head layers into the same square body canvas. Reverse the square resize, then crop original integer center padding. This restores geometry; interpolation cannot recover RGB details lost during inference.

## Existing connections retained

FREE upper/full accepts one finished character image. PRO body/hair/outfit/accessory is independent; detachable assets require one body reference. The existing CLI and Colab selectors connect edition, framing, selected asset, reference, Qwen layer count and recursion budget to the PSD package builder. Real RGBA PNGs, alpha masks, PSD, comparison preview, source references, guides and non-native metadata remain in the ZIP. Editor owns meshes, deformers, keyforms, physics, CMO3 and MOC3.

## Validation and limits

Focused tests: 140 passed with the repository-pinned psd-tools 1.14.2 and trimesh 4.12.2. Tests read/write actual PSDs and ZIPs, reproduce importer failures, preserve source-mask pixels, verify FREE limits and confirm final PRO geometry. GPU calls are replaced only at the inference boundary in CPU integration tests.

Whole repository run: 602 passed, 2 skipped, 1 failed (test_preloaded_real_face_model_answers_first_request_then_unloads in tests/test_colab_gpu_prewarm.py). The environment rejects AF_UNIX socket bind with PermissionError [Errno 1] Operation not permitted, independently reproduced with a minimal socket program. A shorter temporary path did not resolve this. No production socket checks were disabled.

Still unverified: real Colab T4 inference, actual occlusion reconstruction, anatomical accuracy of Qwen partitions, missing pupil/highlight/tongue layers for individual characters, original RGB fidelity, identity and pose matching, final Editor texture packing, actual Editor FREE object counts and MOC3 export. Area/edge bounds are necessary conditions only, not a packing witness. Generated detail IDs remain .qN mask partitions, not asserted anatomical labels. Do not call these items complete from CPU evidence.

## Follow-up implementation commits

- 57a0aec: Qwen resolves worker paths and uses a fresh candidate directory per run; stale PNGs cannot satisfy a new inference.
- 4d36a91: honor the pinned worker's 16px dimension rounding for thin parts; equal-alpha overlap goes to the foreground proposal.
- 4c86f5a: shared request validation rejects wrong Qwen budgets before any model call; resolve See-through worker paths.
- d89d7c8: model snapshots download in supervised subprocesses with wall deadlines and complete logs; invalidate stale setup readiness and publish the new manifest atomically; inference uses offline model caches.
- 1ea0977: preserve combined depth and side suffixes such as irides-l-0; avoid splitting an already sided tag again.
- 6802435: spend initial passes across observed semantic families before recursively subdividing one large hair region.
- 33cd081: complete the selected-mode detail review (including sclera, highlights, teeth, tongue, hair roots, full-body feet and garment backs) and current CLI/README guidance.
- 989f59d: exercise FREE upper/full and all four PRO assets in upper/full; wire new worker/preflight/setup tests into the existing fast gate.
- b50e5ed: a FREE result with only one final raster leaf fails as a flattened character; independent one-layer PRO accessories remain valid.

## MD coverage matrix

| MD section | Executable connection / deliverable | Evidence / remaining boundary |
|---|---|---|
| §1 principles | selected edition/frame/asset → real layered PSD, preserved mask pixels, no automatic MOC3 | 10 public-mode handoff cases; pixel partition round-trip tests; generated visual detail still requires review |
| §2 independent modes | FREE one input; PRO one selected asset and body reference only for detachable assets | Colab routing and all 10 public-mode packages; final PSD/body geometry integration test |
| §3 seven limits | FREE 100 candidate leaves, at most 30 PSD groups, necessary texture bounds; all seven limits in Editor guides; PRO avoids FREE enforcement | tests for 99→100 refinement, >100 rejection and oversized textures; final native Editor counts/packing remain manual |
| §4 model stages | preparation → pinned See-through NF4 → depth/LR → registered RGBA → selected Qwen/LoRA recursion → accepted masks in PSD | real CPU worker process boundary tests, deadlines, freshness, offline cache environment, source frame restoration; real GPU inference unverified |
| §5 details | semantic IDs retain native front/back/side/depth; selected asset gets complete anatomical/garment review guidance | import/suffix/mask tests; .qN children are mask partitions, not newly asserted anatomy; no automatic claim that every fine detail exists |
| §6 quality | actual PSD/PNG/masks, reconstructed composite, input comparison, final PRO/body overlay, invalid or flattened FREE output rejected | real PSD/ZIP tests; holes, hidden restoration, identity and motion quality require image/Editor review |
| §7 historical gaps | recursion budget, accepted PSD merge, independent PRO, no PRO 128/512 ceiling in this handoff, preserved IDs, honest Editor scope | existing and new regression cases; no native-object or broadcast-quality claims |
| §8 files | correct selected PSD plus RGBA, masks, references, previews, guide/review MD, observed metadata and actual inference logs | final ZIP inventory equality tests; JSON is explicitly non-native manual reference |
| §9 user Editor work | import → mesh/deformer/keyform/physics → CMO3 → MOC3 → VTube Studio check | instructions included; official Editor is the user's external stage |
| §10 excluded solutions | no virtual Editor, fabricated MOC3, automatic rig JSON or forced simultaneous PRO uploads | MOC3 absent from all 10 handoffs; artifact status remains Editor-rig-required |
| §11 summary | FREE fixed look and PRO independent assets terminate at PSD artwork handoff | follows §1–10; visual quality is not proven by the CPU suite |

## Publication

Changes are committed locally on main. Automatic approval review again rejected GitHub push: it interpreted the user's follow-up “commit” instruction as authorization for local commits, not explicit external publication. No alternate upload, connector write or force-push was attempted. An explicit instruction to push to jujumelona/Virtual-pipeline main is still needed for remote publication.
