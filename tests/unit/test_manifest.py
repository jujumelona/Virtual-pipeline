"""Manifest cache-integrity tests."""

from __future__ import annotations

import json

from vtuber_pipeline.core.manifest import PipelineManifest


def test_manifest_restores_unchanged_artifact(tmp_path):
    artifact = tmp_path / "mesh.glb"
    artifact.write_bytes(b"original-mesh")

    manifest = PipelineManifest(str(tmp_path))
    manifest.record_stage(
        "stage-key",
        {
            "status": "complete",
            "stage_name": "reconstruction",
            "output_path": str(artifact),
            "artifact_paths": [str(artifact)],
        },
    )

    assert manifest.is_complete("stage-key") is True
    restored = manifest.get_stage("stage-key")
    assert restored["output_path"] == str(artifact)


def test_manifest_rejects_nonempty_but_modified_artifact(tmp_path):
    artifact = tmp_path / "mesh.glb"
    artifact.write_bytes(b"original-mesh")

    manifest = PipelineManifest(str(tmp_path))
    manifest.record_stage(
        "stage-key",
        {
            "status": "complete",
            "stage_name": "reconstruction",
            "output_path": str(artifact),
            "artifact_paths": [str(artifact)],
        },
    )
    artifact.write_bytes(b"different-but-still-nonempty")

    reloaded = PipelineManifest(str(tmp_path))
    assert reloaded.is_complete("stage-key") is False


def test_manifest_rejects_missing_or_empty_artifact(tmp_path):
    artifact = tmp_path / "mesh.glb"
    artifact.write_bytes(b"mesh")

    manifest = PipelineManifest(str(tmp_path))
    manifest.record_stage(
        "stage-key",
        {
            "status": "complete",
            "stage_name": "reconstruction",
            "artifact_paths": [str(artifact)],
        },
    )

    artifact.unlink()
    assert PipelineManifest(str(tmp_path)).is_complete("stage-key") is False

    artifact.write_bytes(b"")
    assert PipelineManifest(str(tmp_path)).is_complete("stage-key") is False


def test_old_manifest_without_artifact_hash_is_not_restorable(tmp_path):
    artifact = tmp_path / "old.glb"
    artifact.write_bytes(b"old-cache")
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "version": "1.0",
                "stages": {
                    "legacy": {
                        "status": "complete",
                        "contract": {
                            "status": "complete",
                            "stage_name": "legacy",
                            "output_path": str(artifact),
                            "artifact_paths": [str(artifact)],
                        },
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    assert PipelineManifest(str(tmp_path)).is_complete("legacy") is False


def test_semantic_stage_without_artifacts_can_be_restored(tmp_path):
    manifest = PipelineManifest(str(tmp_path))
    manifest.record_stage(
        "semantic",
        {
            "status": "complete",
            "stage_name": "input_gate",
            "valid": True,
            "landmarks": [[1.0, 2.0]],
            "artifact_paths": [],
        },
    )

    assert manifest.is_complete("semantic") is True


def test_stage_key_changes_with_config_and_tool_revision(tmp_path):
    manifest = PipelineManifest(str(tmp_path))

    base = manifest.compute_stage_key(
        "stage",
        {"image": "abc"},
        {"remove_background": True},
        "code-a",
        "tool-a",
    )
    changed_config = manifest.compute_stage_key(
        "stage",
        {"image": "abc"},
        {"remove_background": False},
        "code-a",
        "tool-a",
    )
    changed_tool = manifest.compute_stage_key(
        "stage",
        {"image": "abc"},
        {"remove_background": True},
        "code-a",
        "tool-b",
    )

    assert base != changed_config
    assert base != changed_tool
