# FREE atlas budget repair implementation plan

> **For agentic workers:** Use superpowers:executing-plans to implement this repair in the existing main checkout. The user has already authorized fixes, commits and pushes on main.

**Goal:** Generate the existing separated artwork into one 2048px FREE atlas instead of discovering eight pages after export.

**Architecture:** A small original external-process launcher supplies the official PSD2Live v3.3.1 `PipelineConfig.atlasBudget`. The upstream CLI does not expose `maxPages`; its default is eight. The official packer chooses its maximum fit, and the official pipeline performs mesh generation, export and readback. The source PSD and its rasters remain unchanged.

**Tech stack:** Python, Kotlin, Gradle JavaExec, psd-tools, Pillow, pytest, GitHub Actions.

**Spec:** User request and attached log: 60 separated layers pass PSD roundtrip, then `PSD2LIVE_FREE_ATLAS_LIMIT` reports eight 2048px pages. Use official settings and deliver a usable output.

## Global constraints

- Work and commit on main; no new branch.
- Keep PSD2Live v3.3.1 external; do not vendor upstream code or ship its binaries in model ZIPs.
- FREE atlas budget: 2048px, one page, official default padding 2px. PRO retains 4096px and the official eight-page budget.
- Keep mesh spacing 40, document mesh units, wrap 0, head/body strength 1, texture upscale off and the existing official generation/export defaults.
- No new diffusion pass, Qwen activation, layer merge, layer deletion or source PSD resize.
- Keep the final atlas validator; record the actual fit and packed layers.

## Review focus

- Sixty large layers must fit before export; real JVM CI must exercise FREE.
- Large raster extents must not silently enlarge the FREE atlas beyond 2048px; normalize canvas coordinates while retaining original raster bytes.
- Source/output paths containing spaces must retain their identity through Gradle.
- A failed launcher or stale output must never be packaged as new success.
- The launcher must use the pinned external pipeline and preserve readback validation and original-artwork packaging.

### Task 1: Supply the official generation budget

Files: `tools/vts_psd2live.py`, new `tools/psd2live_bridge/` launcher and Gradle init script, `tests/test_vts_psd2live.py`.

Consumes: existing `run_psd2live(psd, output, edition, runner=...)` interface.
Produces: same result interface plus actual atlas fit metadata.

- [ ] Write and run a failing test proving FREE receives one-page budget and PRO keeps eight pages.
- [ ] Add the launcher and initialize the external Gradle build with its source directory; pass the settings before the official pipeline runs.
- [ ] Record generated atlas placement/count/fit and preserve the original PSD bytes. Normalize only oversized source canvas coordinates through the upstream dense-source abstraction.
- [ ] Run the bridge tests, including paths, failed JVM, stale files and packaging. Repair the two pre-existing test fixtures that incorrectly place output inside the artwork directory.

### Task 2: Exercise the real failure in CI

Files: `.github/workflows/vts-psd2live-integration.yml`, `.github/workflows/fast-contract.yml`, `ci/vts_psd2live_integration.py`, `README.md`.

Consumes: Task 1 bridge result and official pinned sample PSD.
Produces: real FREE sixty-layer export evidence and preserved PRO regression.

- [ ] Generate a real 60-layer stress PSD whose cropped raster rectangles exceed one atlas.
- [ ] Run the pinned JVM exporter and verify one <=2048px PNG, 60 packed layers, fit in (0,1), untouched PSD, editable CMO3 and a valid model bundle.
- [ ] Exercise a raster extent beyond 2048px to check the official packer cannot grow the delivered FREE atlas.
- [ ] Retain the upstream PRO sample export and include adapter/test/script changes in workflow path triggers and CPU contract coverage.
- [ ] Update only the affected README contract; run the CPU suite, review the patch, commit, push and inspect the new CI runs.
