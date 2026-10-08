"""Fail-closed provenance check for bundled InstantMesh CUDA renderer code.

InstantMesh's root Apache license does not sublicense files carrying Nvidia
proprietary notices or the separately non-commercial nvdiffrast dependency.
This safeguard applies even if the CC-BY-NC Zero123++ diffusion stage is skipped.
"""
from __future__ import annotations

from pathlib import Path


RUNTIME_SOURCES = (
    "src/models/lrm_mesh.py",
    "src/models/geometry/render/neural_render.py",
    "src/models/geometry/rep_3d/flexicubes.py",
    "src/models/geometry/rep_3d/flexicubes_geometry.py",
    "src/models/renderer/synthesizer_mesh.py",
    "src/models/renderer/utils/renderer.py",
    "src/utils/mesh_util.py",
)

PROHIBITED_TOKENS = (
    "nvdiffrast",
    "LicenseRef-NvidiaProprietary",
    "without an express license agreement",
    "Nvidia Source Code License",
)


def require_commercial_compatible_upstream(upstream_root: str | Path) -> dict:
    """Verify that no known noncommercial/proprietary runtime code is in use.

    This is a conservative source-level gate, NOT a legal audit or automatic
    license grant. Unknown/unavailable source files are not accepted.
    """
    root = Path(upstream_root).resolve()
    if not root.is_dir():
        raise FileNotFoundError(root)
    matched = []
    missing = []
    for relative in RUNTIME_SOURCES:
        file = root / relative
        if not file.is_file():
            missing.append(relative)
            continue
        content = file.read_text(encoding="utf-8", errors="replace").lower()
        for token in PROHIBITED_TOKENS:
            if token.lower() in content:
                matched.append({"file": relative, "restricted_dependency": token})
    if matched or missing:
        explanation = "; ".join(
            f"{item['file']} ({item['restricted_dependency']})" for item in matched[:6]
        )
        if missing:
            explanation += ("; missing source evidence: " + ", ".join(missing[:6]))
        raise RuntimeError(
            "Commercial InstantMesh source is not license-cleared. "
            "Do not run Nvidia proprietary/nvdiffrast code or treat an "
            "Apache-2.0 project-level license as an override. "
            + explanation
        )
    return {"source_license_gate": "review-required", "restricted_sources_found": False}
