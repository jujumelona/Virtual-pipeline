"""Protect the face-landmark boundary that runs before GPU inference."""

from __future__ import annotations

from vtuber_pipeline.avatar.build import AvatarPipeline
from vtuber_pipeline.core.stage_progress import stage_reporter


def test_successful_status_with_missing_landmarks_is_rejected_before_completion(tmp_path):
    pipeline = AvatarPipeline(str(tmp_path / "avatar"))
    events = []
    with stage_reporter(lambda *args: events.append(args)):
        gate = pipeline._run_stage(
            "input_gate",
            ("source.png",),
            lambda: {
                "status": "complete",
                "valid": True,
                "landmarks": [],
                "landmark_count": 0,
            },
        )
    assert gate["status"] == "error"
    assert gate["valid"] is False
    assert "got 0/28" in gate["error"]
    assert ("input_gate", "complete", "") not in events
    assert any(name == "face_landmarks" and "count=0/28" in detail
               for name, status, detail in events)
    assert any(name == "input_gate" and status == "error"
               for name, status, detail in events)


def test_invalid_cached_face_result_is_not_reused(tmp_path):
    pipeline = AvatarPipeline(str(tmp_path / "avatar"))
    args = ("same-source.png",)
    key = pipeline._get_stage_key("input_gate", *args)
    pipeline.manifest.record_stage(
        key,
        {"status": "complete", "valid": True, "landmarks": [], "landmark_count": 0},
    )
    seen = []
    fresh = {
        "status": "complete",
        "valid": True,
        "landmarks": [[float(i), 1.0] for i in range(28)],
        "landmark_count": 28,
    }

    def detect_again():
        seen.append(True)
        return fresh

    gate = pipeline._run_stage("input_gate", args, detect_again)
    assert seen == [True]
    assert gate["status"] == "complete"
    assert len(gate["landmarks"]) == 28
    assert gate.get("cache_hit") is not True


def test_valid_28_landmarks_are_not_changed_by_contract_guard(tmp_path):
    pipeline = AvatarPipeline(str(tmp_path / "avatar"))
    fresh = {
        "status": "complete",
        "valid": True,
        "landmarks": [[float(i), 1.0] for i in range(28)],
        "landmark_count": 28,
    }
    actual = pipeline._run_stage("input_gate", ("valid.png",), lambda: dict(fresh))
    assert actual["status"] == "complete"
    assert actual["landmarks"] == fresh["landmarks"]
