"""Regression tests for strict, metadata-aware commercial runtime license audit.

These fixtures model real wheel metadata where the legacy License field
contains an entire Apache 2.0 legal document, sometimes followed by a BSD
classifier. References within legal boilerplate must not become false positives.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from tools import audit_runtime_environment as audit


@dataclass
class FakeMeta:
    values: dict[str, str]
    classifiers: list[str]

    def get(self, key: str, default=None):
        return self.values.get(key, default)

    def get_all(self, key: str, default=None):
        if key == "Classifier":
            return self.classifiers
        return default


@dataclass
class FakeDist:
    metadata: FakeMeta
    version: str = "1.0.0"
    requires: tuple[str, ...] = ()


def make_dist(
    *,
    license_expression: str = "",
    legacy_license: str = "",
    classifiers: tuple[str, ...] = (),
    requires: tuple[str, ...] = (),
) -> FakeDist:
    return FakeDist(
        metadata=FakeMeta(
            values={
                "Name": "demo",
                "License-Expression": license_expression,
                "License": legacy_license,
            },
            classifiers=list(classifiers),
        ),
        requires=requires,
    )


APACHE_LEGAL_DOCUMENT = (
    "Apache License\n"
    "Version 2.0, January 2004\n"
    "TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION\n"
    + ("1. Definitions. Redistribution terms, applicable permissions, "
       "warranties and limitations. \n" * 15)
    + "This document mentions the GNU General Public License (GPL) "
      "as an example of other license terms, not as this package's license.\n"
    + "APPENDIX: How to apply the Apache License to your work\n"
    + ("Copyright [yyyy] [name of copyright owner]\n" * 10)
)


def classify(dist: FakeDist) -> str:
    return audit._classify_license_declarations(audit._license_declarations(dist))


def test_apache_legal_prose_with_gpl_reference_and_bsd_classifier_is_not_blocked():
    dist = make_dist(
        legacy_license=APACHE_LEGAL_DOCUMENT,
        classifiers=("License :: OSI Approved :: BSD License",),
    )
    declarations = audit._license_declarations(dist)
    assert classify(dist) == "permissive"
    assert ("License (document heading)", "Apache License Version 2.0, January 2004") in declarations
    assert all("GNU General Public License" not in item for _, item in declarations)
    assert sum(len(item) for _, item in declarations) < 250


def test_apache_full_text_without_classifiers_uses_its_actual_heading():
    assert classify(make_dist(legacy_license=APACHE_LEGAL_DOCUMENT)) == "permissive"


@pytest.mark.parametrize(
    "expression",
    [
        "GPL-3.0-only", "AGPL-3.0-or-later",
        "GPL-2.0-only AND MIT", "MIT OR GPL-3.0-only",
        "CC-BY-NC-4.0", "NonCommercial-Only",
    ],
)
def test_explicit_restricted_license_expression_is_blocked(expression):
    assert classify(make_dist(license_expression=expression)) == "blocked"


def test_explicit_gpl_declaration_overrides_friendly_classifier():
    dist = make_dist(
        license_expression="GPL-3.0-only",
        classifiers=("License :: OSI Approved :: BSD License",),
    )
    assert classify(dist) == "blocked"


def test_short_legacy_gpl_or_noncommercial_license_is_blocked():
    assert classify(make_dist(legacy_license="GNU General Public License v3")) == "blocked"
    assert classify(make_dist(legacy_license="For non-commercial use only")) == "blocked"


def test_full_length_gpl_document_is_still_blocked_by_header():
    full_gpl = "GNU GENERAL PUBLIC LICENSE\nVersion 3, 29 June 2007\n" + (
        "Copyright and redistribution terms apply.\n" * 30
    )
    assert classify(make_dist(legacy_license=full_gpl)) == "blocked"


def test_unknown_license_remains_unknown_not_mistaken_for_permissive():
    assert classify(make_dist()) == "unknown"


def test_runtime_audit_passes_documented_apache_and_reports_only_license_identity(monkeypatch):
    dist = make_dist(
        legacy_license=APACHE_LEGAL_DOCUMENT,
        classifiers=("License :: OSI Approved :: BSD License",),
    )
    monkeypatch.setattr(audit, "ROOT_PACKAGES", ["demo"])
    monkeypatch.setattr(audit, "_installed_distribution", lambda _: dist)
    result = audit.audit_runtime()
    assert result["status"] == "complete"
    assert result["blocked"] == []
    assert result["package_count"] == 1
    package = result["packages"][0]
    assert package["license_status"] == "permissive"
    assert len(package["license"]) < 250
    assert "APPENDIX" not in package["license"]


def test_runtime_audit_still_fails_when_gpl_dependency_is_installed(monkeypatch):
    root = make_dist(license_expression="MIT", requires=("restricted",))
    restricted = make_dist(license_expression="GPL-3.0-only")
    mapping = {"root": root, "restricted": restricted}
    monkeypatch.setattr(audit, "ROOT_PACKAGES", ["root"])
    monkeypatch.setattr(audit, "_installed_distribution", lambda name: mapping[name])
    result = audit.audit_runtime()
    assert result["status"] == "error"
    assert len(result["blocked"]) == 1
    assert result["blocked"][0]["license_status"] == "blocked"


def test_runtime_audit_fails_if_required_dependency_missing(monkeypatch):
    monkeypatch.setattr(audit, "ROOT_PACKAGES", ["absent"])
    monkeypatch.setattr(
        audit, "_installed_distribution",
        lambda _: (_ for _ in ()).throw(audit.metadata.PackageNotFoundError("absent")),
    )
    result = audit.audit_runtime()
    assert result["status"] == "error"
    assert result["missing_distribution_metadata"] == ["absent"]
