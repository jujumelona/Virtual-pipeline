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
    re.compile(r"non[- _]?commercial", re.I),
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


# PyPI metadata's legacy License field may contain an entire license file,
# including examples, comparisons with other licenses, and Apache's appendix.
# Those paragraphs are NOT the declared license of the distribution.
_LICENSE_HEADER = re.compile(
    r"^(?:(?:THE )?GNU (?:AFFERO )?GENERAL PUBLIC LICENSE"
    r"|APACHE LICENSE|MIT LICENSE|BSD(?:-\d-CLAUSE| \d-CLAUSE)? LICENSE"
    r"|MOZILLA PUBLIC LICENSE|ISC LICENSE|PYTHON SOFTWARE FOUNDATION LICENSE"
    r"|CREATIVE COMMONS ZERO|UNLICENSE)(?:\s|$)",
    re.I,
)


def _license_declarations(dist: metadata.Distribution) -> List[tuple[str, str]]:
    """Read license *declarations*, not incidental text in license bodies.

    Classifiers and PEP 639 License-Expression are structured declarations.
    For legacy License values containing entire license texts, use only an
    actual opening license heading, never the legal prose/appendices.
    Conflicting explicit declarations still fail closed when any is blocked.
    """
    declared: List[tuple[str, str]] = []
    expression = str(dist.metadata.get("License-Expression") or "").strip()
    if expression:
        declared.append(("License-Expression", expression))

    legacy = str(dist.metadata.get("License") or "").strip()
    if legacy:
        if len(legacy) <= 512:
            declared.append(("License", legacy))
        else:
            # An entire Apache-2.0 license mentions other license families in
            # its boilerplate. Match only the first visible license heading.
            lines = [line.strip() for line in legacy.splitlines() if line.strip()]
            header = next(
                (line for line in lines[:8] if _LICENSE_HEADER.match(line)),
                None,
            )
            if header:
                if header.casefold() == "apache license":
                    # "Apache License" on one line and "Version 2.0" on next.
                    header += " " + next(
                        (line for line in lines[1:5] if re.match(r"^Version\s+2(?:\.0)?\b", line, re.I)),
                        "",
                    )
                declared.append(("License (document heading)", header))

    for classifier in dist.metadata.get_all("Classifier", []) or []:
        if classifier.startswith("License ::"):
            declared.append(("Classifier", classifier))
    return declared


def _classify_license_declarations(
    declarations: List[tuple[str, str]],
) -> str:
    if any(
        pattern.search(value)
        for _, value in declarations
        for pattern in BLOCKED_LICENSE_PATTERNS
    ):
        return "blocked"
    if any(
        pattern.search(value)
        for _, value in declarations
        for pattern in PERMISSIVE_LICENSE_PATTERNS
    ):
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
        license_declarations = _license_declarations(dist)
        status = _classify_license_declarations(license_declarations)
        name_block = BLOCKED_NAMES.get(canonical_dist)

        item = {
            "name": name,
            "version": dist.version,
            "license": " | ".join(value for _, value in license_declarations) or None,
            "license_source": [source for source, _ in license_declarations],
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
