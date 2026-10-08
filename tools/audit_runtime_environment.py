"""Audit the resolved runtime dependency graph for commercial blockers."""

from __future__ import annotations

import importlib.metadata as metadata
import json
import pathlib
import re
import sys
from typing import Any, Dict, Iterable, List, Set

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


ROOT_PACKAGES = [
    "anime-face-detector",
    "torch",
    "torchvision",
    "scikit-image",
    "trimesh",
    "Pillow",
    "numpy",
    "scipy",
    "click",
    "pygltflib",
    "omegaconf",
    "einops",
    "transformers",
    "rembg",
    "huggingface-hub",
    "imageio",
    "xatlas",
    "moderngl",
    "onnxruntime",
    "opencv-python-headless",
    "safetensors",
    "gradio",
]

BLOCKED_NAMES = {
    "instantmesh": "blocked project dependency",
    "nvdiffrast": "blocked runtime dependency",
    "stable-fast-3d": "commercial conditions outside the mainline contract",
}

BLOCKED_LICENSE_PATTERNS = [
    re.compile(r"\bAGPL\b", re.I),
    re.compile(r"GNU Affero General Public License", re.I),
    re.compile(r"\bGPL(?:-|\b)", re.I),
    re.compile(r"GNU General Public License", re.I),
    re.compile(r"non[- ]commercial", re.I),
    re.compile(r"CC[- ]BY[- ]NC", re.I),
]

PERMISSIVE_LICENSE_PATTERNS = [
    re.compile(r"\bMIT\b", re.I),
    re.compile(r"MIT-CMU", re.I),
    re.compile(r"\bBSD\b", re.I),
    re.compile(r"Apache(?: Software License)?(?:[- ]?2(?:\.0)?)?", re.I),
    re.compile(r"\bISC\b", re.I),
    re.compile(r"Mozilla Public License|\bMPL(?:-|\b)", re.I),
    re.compile(r"Python Software Foundation|\bPSF\b", re.I),
    re.compile(r"Unlicense", re.I),
    re.compile(r"CC0|Public Domain", re.I),
]


def _license_text(dist: metadata.Distribution) -> str:
    values: List[str] = []
    for key in ("License-Expression", "License"):
        value = dist.metadata.get(key)
        if value:
            values.append(str(value))
    values.extend(
        value
        for value in dist.metadata.get_all("Classifier", [])
        if value.startswith("License ::")
    )
    return " | ".join(values).strip()


def _classify_license(text: str) -> str:
    if not text:
        return "unknown"
    if any(pattern.search(text) for pattern in BLOCKED_LICENSE_PATTERNS):
        return "blocked"
    if any(pattern.search(text) for pattern in PERMISSIVE_LICENSE_PATTERNS):
        return "permissive"
    return "unknown"


def _installed_distribution(name: str) -> metadata.Distribution:
    return metadata.distribution(name)


def _active_requirements(dist: metadata.Distribution) -> Iterable[str]:
    for raw in dist.requires or []:
        try:
            requirement = Requirement(raw)
        except Exception:
            continue
        if requirement.marker is not None and not requirement.marker.evaluate():
            continue
        yield requirement.name


def audit_runtime() -> Dict[str, Any]:
    queue = list(ROOT_PACKAGES)
    visited: Set[str] = set()
    packages: List[Dict[str, Any]] = []
    missing: List[str] = []

    while queue:
        requested = queue.pop(0)
        canonical = canonicalize_name(requested)
        if canonical in visited:
            continue
        visited.add(canonical)

        try:
            dist = _installed_distribution(requested)
        except metadata.PackageNotFoundError:
            missing.append(requested)
            continue

        name = dist.metadata.get("Name") or requested
        canonical_dist = canonicalize_name(name)
        license_text = _license_text(dist)
        status = _classify_license(license_text)
        name_block = BLOCKED_NAMES.get(canonical_dist)

        item = {
            "name": name,
            "version": dist.version,
            "license": license_text or None,
            "license_status": "blocked" if name_block else status,
            "blocked_reason": name_block,
        }
        packages.append(item)

        for dependency in _active_requirements(dist):
            dep_canonical = canonicalize_name(dependency)
            if dep_canonical not in visited:
                queue.append(dependency)

    blocked = [
        item for item in packages
        if item["license_status"] == "blocked"
    ]
    unknown = [
        item["name"] for item in packages
        if item["license_status"] == "unknown"
    ]

    # Every required runtime distribution must be installed and auditable.
    hard_missing = list(missing)

    return {
        "status": "error" if blocked or hard_missing else "complete",
        "root_packages": ROOT_PACKAGES,
        "package_count": len(packages),
        "blocked": blocked,
        "unknown_license_metadata": sorted(set(unknown)),
        "missing_distribution_metadata": missing,
        "packages": sorted(
            packages,
            key=lambda item: canonicalize_name(item["name"]),
        ),
    }


def main() -> int:
    report = audit_runtime()
    output = pathlib.Path(
        "/content/vtuber_builder/commercial_dependency_audit.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({
        "status": report["status"],
        "package_count": report["package_count"],
        "blocked": report["blocked"],
        "unknown_license_metadata": report["unknown_license_metadata"],
        "report": str(output),
    }, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
