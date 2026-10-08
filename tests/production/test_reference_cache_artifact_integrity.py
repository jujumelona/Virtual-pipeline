"""Resume cache must not reuse missing input/observation manifests.

A cached stage with a valid front image but a missing reference report must
re-execute, not quietly produce stale report_path for multiview alignment.
"""
from pathlib import Path

from vtuber_pipeline.avatar.build import AvatarPipeline


def test_reference_report_missing_invalidates_resume(tmp_path):
    pipeline = AvatarPipeline(str(tmp_path / "build"))
    report = tmp_path / "reference_quality.json"
    count = []

    def execute():
        count.append("ran")
        report.write_text('{"images": {"front": {"path": "observed.png"}}}')
        return {"status": "complete", "report_path": str(report)}

    first = pipeline._run_stage("reference_quality", ("sha-front",), execute)
    assert first["status"] == "complete"
    assert count == ["ran"]
    assert pipeline._run_stage("reference_quality", ("sha-front",), execute)["cache_hit"]
    assert count == ["ran"]

    report.unlink()
    restored = pipeline._run_stage("reference_quality", ("sha-front",), execute)
    assert restored["status"] == "complete"
    assert not restored.get("cache_hit")
    assert count == ["ran", "ran"]


def test_camera_manifest_mutation_invalidates_resume(tmp_path):
    pipeline = AvatarPipeline(str(tmp_path / "build"))
    camera = tmp_path / "camera.json"
    calls = []

    def execute():
        calls.append("ran")
        camera.write_text('{"model": "measured"}')
        return {"status": "complete", "camera_json": str(camera)}

    pipeline._run_stage("instantmesh", ("sha-input",), execute)
    assert pipeline._run_stage("instantmesh", ("sha-input",), execute)["cache_hit"]
    camera.write_text('{"model": "corrupted"}')
    result = pipeline._run_stage("instantmesh", ("sha-input",), execute)
    assert not result.get("cache_hit")
    assert len(calls) == 2
