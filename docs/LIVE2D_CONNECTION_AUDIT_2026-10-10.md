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

Focused tests: 110 passed with the repository-pinned psd-tools 1.14.2 and trimesh 4.12.2. Tests read/write actual PSDs and ZIPs, reproduce importer failures, preserve source-mask pixels, verify FREE limits and confirm final PRO geometry. GPU calls are replaced only at the inference boundary in CPU integration tests.

Whole repository run: 572 passed, 2 skipped, 1 failed (test_preloaded_real_face_model_answers_first_request_then_unloads in tests/test_colab_gpu_prewarm.py). The environment rejects AF_UNIX socket bind with PermissionError [Errno 1] Operation not permitted, independently reproduced with a minimal socket program. A shorter temporary path did not resolve this. No production socket checks were disabled.

Still unverified: real Colab T4 inference, actual occlusion reconstruction, anatomical accuracy of Qwen partitions, missing pupil/highlight/tongue layers for individual characters, original RGB fidelity, identity and pose matching, final Editor texture packing, actual Editor FREE object counts and MOC3 export. Area/edge bounds are necessary conditions only, not a packing witness. Generated detail IDs remain .qN mask partitions, not asserted anatomical labels. Do not call these items complete from CPU evidence.

## Publication

Code changes are committed locally on main. GitHub push was rejected by automatic approval review because authorization to publish to the external repository was not explicit in this request. No alternate upload or force-push was attempted. Remote publication requires the user's explicit approval.
