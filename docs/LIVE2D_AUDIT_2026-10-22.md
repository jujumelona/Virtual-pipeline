# Live2D production audit — 2026-10-22 (KST)

## Evidence-based verdict

**NOT CERTIFIED for unattended AI VTuber production.**

Code-level regression gates pass for the current source-to-rig path, but
native PSD2Live GUI-MCP interoperability, real GPU illustration splitting,
a genuine character's Cubism runtime behavior and VTube Studio tracking
have not been demonstrated on a live generated character.

## GitHub Actions outcomes confirmed

These are separate runs, not an additive number of unique tests:

| Gate | Actual run | Observed result |
|---|---|---|
| Live2D source-to-rig contract | [39638799635](https://github.com/jujumelona/Virtual-pipeline/actions/runs/39638799635) | 83 passed |
| Fast contract gate | [39638437236](https://github.com/jujumelona/Virtual-pipeline/actions/runs/39638437236) | 605 passed, 1 skipped |
| BODY artwork part intake | [39638093343](https://github.com/jujumelona/Virtual-pipeline/actions/runs/39638093343) | 27 passed |
| VTS layered PSD roundtrip (Python 3.12, 3.13) | [39638405709](https://github.com/jujumelona/Virtual-pipeline/actions/runs/39638405709) | 44+37+11 passed in each interpreter |

The initial test failures were real and were repaired with small committed
changes: original BODY option was absent in the shared mode registry, tests
expected obsolete modes/old methods, and the prior PSD2Live proxy calls
contained the wrong double-wrapped \`request\` envelope. A new test checks
business request shape, failed async jobs, edit preview and saved project
sequence. These tests invoke an **injected fake MCP response**, not an
operating desktop editor.

The older **full CPU discovery** run
[39635203090](https://github.com/jujumelona/Virtual-pipeline/actions/runs/39635203090)
was unsuccessful: 320 failed, 1170 passed, 163 errors, 1 skipped.
A major contributor is legacy tests that still require removed 24-kit
\`docs/image_ai_kits_v2/zips/*__body.zip\` files, despite the actual
18-kit source-only contract. That run is not the newest HEAD; its historic
failure counts must **not** be misrepresented as the current HEAD's exact
counts. A clean full CI run on HEAD has not been observed.

## Live2D boundaries verified by reading upstream source

- The native CLI converter is pinned to **PSD2Live v3.3.1**.
- Its \`mcp_proxy.py\` lacks the \`call <operation> @json --edit\` mode used by
  the latest AI keyform author. Do not try to run those commands against the
  pinned CLI tree. The keyform writer rejects this old version before edits
  with \`PSD2LIVE_MCP_CLI_UNSUPPORTED\`.
- The separate native editor stage requires a newer compatible desktop
  PSD2Live project/source with an enabled local MCP instance and **real**
  Warp IDs; opening a v3.3.1 project in that newer app remains unverified.
- \`workspace_preview_edits\` is a dry run and does not mutate geometry.
  A successful \`rig_deform\` needs a new \`state\`, and saved/exported model
  artifacts must be validated with a **real** native pose renderer.
- The local VLM correspondences and ±45° reference warps are
  bounded correction mechanisms, not fully generative 3D head topology.
  The system still lacks authentic 90° native profile layer swaps, masking
  and head/neck/garment binding.

## Unperformed acceptance tests

1. Process **genuine** matching FACE, OUTFIT and HAIR artwork ZIPs on Colab
   GPU, inspect the combined PSD's actual occlusion/underpaint.
2. Run v3.3.1 PSD2Live CLI against that PSD; archive full native files,
   debug logs and texture atlas metrics.
3. On a compatible newer PSD2Live desktop, actually **open** the result
   (CMO3 or PSD2Live document), verify Warp IDs and run the real MCP
   keyform preview/edit/save/export cycle. Confirm app/model version compatibility.
4. Run actual MOC3 pose captures and verify required parameter
   activity, head silhouette, iris separation, mouth interpolation, hair,
   mask/hood occlusion and neck seam at ±30°/±45°.
5. Load the final model in **VTube Studio** and test actual face tracking,
   physics, clipping, performance, and model persistence.
6. Decide whether deprecated 24-kit tests should be migrated to the 18-kit
   contract or removed only with explicit replacement coverage; don't
   recreate fake ZIPs or disable the entire failing suite.

These missing steps are material; unit-test mocks and present files alone
cannot justify declaring a completed broadcasting model.
