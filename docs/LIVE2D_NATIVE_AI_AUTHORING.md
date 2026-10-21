# Live2D AI native authoring / measured acceptance (2026-10-22)

This document separates **implemented code** from **real-world runtime evidence**. A passing
unit test or MOC3 format check is not an artistically accepted VTuber.

## 1. GPU Colab: bounded native auto-rig repair

Use [See-through-only Colab](../notebooks/VTuber_SeeThrough_Only_Source_ZIPs.ipynb)
with FACE, OUTFIT and HAIR actual artwork ZIPs. After manually checking the
source composite, select:

- \`RUN_GPU_SEPARATION=True\`
- \`FRAME=upper\` or \`full\`
- \`RIGGING=auto_repair\`

The path is:

\`ZIP RGBA → composite → See-through/SemanticSAM PSD → independent PSD2Live
rebuild candidates → real MOC3 Cubism pose QA → packaged verified candidate\`.

\`tools/vts_native_autorepair.py\` changes bounded PSD2Live settings (head
strength, body strength and mesh spacing), not arbitrary character pixels. It
does **not** call an image generator for new anatomy. A candidate must pass
geometry, parameter isolation, mouth interpolation, and pose activity gates.
A failed candidate never becomes a "success"; the diagnostics remain in
\`native_search/autorig_search.json\`. The default budget is four actual
generation+pose-validation attempts. Running that many jobs may be expensive.

Successful native QA is **not** VTube Studio / OBS face-tracking acceptance.

## 2. Local AI: native 3/4 keyform improvements

This phase requires both reference artwork and rendered poses from the **same
character** and a running local PSD2Live desktop editor/project with MCP enabled.
The local VLM defaults to matching 45-degree references with actual \`ParamAngleX=-45,+45\` native yaw frames. Explicit matching \`-30,+30\` reference/native pairs are also accepted by the keyform compiler.

Prerequisites:

1. Open the generated \`.psd2live\` or \`.cmo3\` model in PSD2Live desktop.
2. Enable its local MCP; keep its access token in the local environment, **not**
   in GitHub or a ZIP. The source checkout contains \`mcp_proxy.py\`.
3. From \`workspace_inspect\` / \`workspace_overview\`, identify *actual* independent
   Warp IDs for face contour, nose, jaw, character's left eye. A prefix such as
   \`warp:\` alone does not create a real target.
4. Obtain MOC3 yaw rendered screenshots, e.g.
   \`yaw_left.png\` and \`yaw_right.png\` from
   \`tools.vts_native_moc_pose_worker\`.
5. Prepare matching \`head_three_quarter_L.png\` and
   \`head_three_quarter_R.png\` reference images. The local vision model
   normalizes both to an explicitly documented square canvas; visually review
   framing and anatomy. A different composition may prevent meaningful
   alignment.

Create a mapping file such as:

\`\`\`json
{
  "face_contour": "warp:REAL_FACE_CONTOUR_ID",
  "nose_tip": "warp:REAL_NOSE_WARP_ID",
  "jaw": "warp:REAL_JAW_WARP_ID",
  "eye_left": "warp:REAL_LEFT_EYE_WARP_ID"
}
\`\`\`

Do not paste these placeholder IDs directly. Substitute the true ones returned
by the *loaded* PSD2Live project. If the model does not have separable Warp
objects for all four roles, edit/create real deformers first rather than
silently modifying an unrelated parent Warp.

Use an OpenAI-compatible **local** image-capable model, for example one served
at \`http://127.0.0.1:8000/v1/chat/completions\`. No external cloud endpoint is
enabled by default. In a terminal in this repository:

\`\`\`bash
python -m tools.vts_ai_landmark_pairs \
  --reference-dir /path/to/references \
  --native-dir /path/to/native_moc3_pose \
  --bindings /path/to/real_warp_bindings.json \
  --model YOUR_LOCAL_VISION_MODEL \
  --output /path/to/landmark_run \
  --endpoint http://127.0.0.1:8000/v1/chat/completions
\`\`\`

This only produces \`native_reference_plan.json\`. It does **not** modify the
model and \`reference_angles_used_as_rig_keyforms\` remains false.

To apply and export in the same command, add:

\`\`\`bash
  --apply --proxy-root /path/to/psd2live_source --export-to /path/to/new_export
\`\`\`

The author applies a bounded, normalized translation at each supplied real
Warp and yaw key, uses \`workspace_preview_edits\` before editing, saves the
workspace and exports a new Cubism model. It then requires **real native MOC3
pose QA** before reporting execution success. Both reference and native
images are preserved for review.

**Limitations:** This is a correction to existing 3/4 keyforms, not an automatic
reconstruction of the face's true 3D topology. Vision-proposed landmarks may be
incorrect. The current native QA checks geometry and parameter activity; it
does not yet prove pixel-level similarity to the reference. An observed pass
does not imply accurate 90-degree anatomy.

## 2.1 Autonomous visual feedback (bounded)

Instead of a single visual correction, the local AI agent can repeat
**native render → VLM landmark re-observation → MCP warp edit → native render**
(up to three rounds by default), keeping the source project's initial file
unchanged. Launch a saved PSD2Live project in the desktop editor first, with
MCP active, then run:

```bash
python -m tools.vts_ai_native_feedback_loop \
  --reference-dir /path/to/references \
  --native-dir /path/to/first/native_moc3_pose \
  --warp-bindings /path/to/real_warp_bindings.json \
  --psd2live-source /path/to/psd2live_source \
  --model YOUR_LOCAL_VISION_MODEL \
  --endpoint http://127.0.0.1:8000/v1/chat/completions \
  --rounds 3 --output /path/to/feedback_run
```

Each application invokes PSD2Live `workspace_preview_edits` before the actual
`rig_deform`. Its first step saves a **new `.psd2live` authoring copy**.
The native exported model must pass Cubism pose QA on each authoring pass; a
new VLM observation must also show measurable landmark improvement and a
normalized residual ≤0.018 by the end. If the model doesn't converge,
`feedback_verdict.json` records failure and a winning model is not certified.
The locally saved draft may contain failed experiments; return to the
unmodified original project to restart.

This is a **geometry/landmark-assisted** agent, not an AI that understands
every hair strand, hand, mask occlusion or artist's style. The local model
must be vision-capable, and manually reviewing correspondence and complex
occlusion is still necessary.

## 3. Full 90-degree profile

No current generic, reliable mapping from a single frontal PSD plus a profile
PNG into perfect native ±90° keyforms has been validated. Proper native
support needs extra painted profile ArtMeshes, occlusion/order, attached
face/neck/hood geometry, layer switching, and parameter ranges beyond basic
frontal head yaw. This workflow **rejects** 90° requests rather than
mislabeling ±30°/±45° frontal warps as a complete profile.

## 4. Failure states and acceptance

A completed model requires all of these independent observations:

1. A genuine export with .model3.json, .moc3, .cmo3 and real textures.
2. Native renderer creates changed head/eye/mouth frames with geometry,
   isolation and interpolation gates passing.
3. 3/4 reference corrections demonstrably reach native keyforms if the
   local MCP stage was invoked (a plan alone is never accepted).
4. Separate visual inspection of identity, silhouette, hair, collar and
   mask occlusion; real VTube Studio tracking must be measured in the app.

The tests under \`tests/test_vts_native_autorepair.py\`,
\`tests/test_vts_reference_keyform_author.py\` and
\`tests/test_vts_ai_landmark_pairs.py\` exercise **orchestration** with
injected fake backends. They cannot substitute for a real character export
or GPU experiment.
