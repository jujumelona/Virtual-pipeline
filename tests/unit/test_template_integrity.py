"""Canonical template source/cache integrity tests."""

from __future__ import annotations

import pathlib

import pytest

import vtuber_pipeline.avatar.template_mesh as template_mesh


def test_git_blob_sha1_matches_git_object_encoding(tmp_path):
    path = tmp_path / "blob.bin"
    path.write_bytes(b"abc")
    assert (
        template_mesh._git_blob_sha1(path)
        == "f2ba8f84ab5c1bce84a7b441cb1959cfc7093b7f"
    )


def test_explicit_makehuman_override_must_match_pinned_blob(
    tmp_path,
    monkeypatch,
):
    fake = tmp_path / "base.obj"
    fake.write_bytes(b"not-the-pinned-makehuman-base")
    monkeypatch.setenv("MAKEHUMAN_BASE_OBJ", str(fake))

    with pytest.raises(RuntimeError, match="blob mismatch"):
        template_mesh._find_local_makehuman_base()


def test_template_cache_detects_nonempty_content_mutation(tmp_path):
    template = tmp_path / "template.glb"
    template.write_bytes(b"canonical-template-bytes")

    template_mesh._write_template_metadata(template)
    assert template_mesh._cached_template_valid(template) is True

    template.write_bytes(b"mutated-but-still-nonempty")
    assert template_mesh._cached_template_valid(template) is False


def test_template_cache_rejects_missing_or_wrong_metadata(tmp_path):
    template = tmp_path / "template.glb"
    template.write_bytes(b"canonical-template-bytes")

    assert template_mesh._cached_template_valid(template) is False

    metadata = template_mesh._template_metadata_path(template)
    metadata.write_text(
        '{"canonical_template_version":"wrong"}\n',
        encoding="utf-8",
    )
    assert template_mesh._cached_template_valid(template) is False
