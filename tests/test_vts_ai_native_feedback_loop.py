"""The image-AI/MCP/native feedback loop must converge on measured landmarks."""
import json
from pathlib import Path

import pytest
from tools.vts_ai_native_feedback_loop import (
    _residual, run_ai_native_feedback_loop,
)


def _sample_manifest(delta):
    pose = {"view": "head_three_quarter_R", "angle_x": 30}
    observed = {"face_contour": [100, 100], "nose_tip": [150, 125],
                "jaw": [130, 170], "eye_left": [120, 95]}
    desired = {name: [pair[0]+delta, pair[1]+delta]
               for name, pair in observed.items()}
    return {"canvas": [320, 320],
            "poses": [{**pose, "observed": observed, "desired": desired}]}


def test_residual_is_zero_only_for_matching_landmarks():
    assert _residual(_sample_manifest(0)) == 0
    assert _residual(_sample_manifest(15)) > 0.01


def test_local_ai_feedback_accepts_only_converged_native_export(tmp_path):
    native = tmp_path / "native"
    native.mkdir()
    calls = []
    def observer(reference_dir, native_dir, output, *, bindings, model, endpoint):
        output.mkdir(parents=True)
        error = [25, 2][sum(item == "observe" for item in calls)]
        (output / "vision_reference_manifest.json").write_text(
            json.dumps(_sample_manifest(error)))
        calls.append("observe")
        return {"canvas": [320, 320], "changes": [{"test": 1}]}, output
    def author(plan, *, proxy_root, work, export_to):
        calls.append("edit")
        return {
            "native_pose_qa": {"pose_activity_passed": True},
            "exported_model3": str(export_to / "verified.model3.json"),
        }
    verdict = run_ai_native_feedback_loop(
        reference_dir=tmp_path, initial_native_dir=native,
        bindings={}, model="local-vlm",
        endpoint="http://127.0.0.1:8000/v1/chat/completions",
        psd2live_source=tmp_path, output=tmp_path / "result",
        max_rounds=3, observer=observer, author=author)
    assert verdict["accepted"] is True
    assert verdict["native_reference_keyforms_verified"] is True
    assert verdict["actual_vtube_studio_tracking_verified"] is False


def test_no_observed_improvement_does_not_claim_ai_success(tmp_path):
    native = tmp_path / "native"
    native.mkdir()
    def observer(reference_dir, native_dir, output, *, bindings, model, endpoint):
        output.mkdir(parents=True)
        (output / "vision_reference_manifest.json").write_text(
            json.dumps(_sample_manifest(20)))
        return {"canvas": [320, 320], "changes": [{"test": 1}]}, output
    def author(plan, *, proxy_root, work, export_to):
        return {"native_pose_qa": {"pose_activity_passed": True},
                "exported_model3": str(export_to / "model3.json")}
    with pytest.raises(RuntimeError, match="NOT_CONVERGED"):
        run_ai_native_feedback_loop(
            reference_dir=tmp_path, initial_native_dir=native,
            bindings={}, model="local-vlm",
            endpoint="http://127.0.0.1:8000/v1/chat/completions",
            psd2live_source=tmp_path, output=tmp_path / "failed",
            max_rounds=2, observer=observer, author=author)
    verdict = json.loads((tmp_path / "failed/feedback_verdict.json").read_text())
    assert verdict["accepted"] is False


def test_real_editable_feedback_rounds_reopen_latest_saved_project(tmp_path):
    src = tmp_path / "start.psd2live"
    src.write_bytes(b"actual-project-fixture")
    native = tmp_path / "native"
    native.mkdir()
    checked = []
    obs_count = [0]

    def observer(reference_dir, native_dir, output, *, bindings, model, endpoint):
        output.mkdir(parents=True)
        err = (30, 20, 1)[min(obs_count[0], 2)]
        obs_count[0] += 1
        (output / "vision_reference_manifest.json").write_text(
            json.dumps(_sample_manifest(err)))
        return {"canvas": [320, 320], "changes": [{"test": 1}]}, output

    def author(plan, *, proxy_root, work, export_to, source_project):
        checked.append(str(source_project))
        work.mkdir(parents=True)
        saved = work / "updated.psd2live"
        saved.write_bytes(b"another-real-project-fixture")
        return {
            "native_pose_qa": {"pose_activity_passed": True},
            "exported_model3": str(export_to / "avatar.model3.json"),
            "editable_project_copy": str(saved),
        }

    result = run_ai_native_feedback_loop(
        reference_dir=tmp_path, initial_native_dir=native,
        bindings={}, model="local-vlm",
        endpoint="http://127.0.0.1:8000/v1/chat/completions",
        psd2live_source=tmp_path, output=tmp_path / "iteration",
        max_rounds=3, source_project=src, observer=observer, author=author)
    assert result["accepted"]
    assert checked[0] == str(src)
    assert checked[1].endswith("round_00/mcp/updated.psd2live")
    assert checked[1] != checked[0]


def test_production_author_must_explicitly_select_project(tmp_path):
    native = tmp_path / "native"
    native.mkdir()
    with pytest.raises(ValueError, match="EXPLICIT_EDITABLE_PROJECT"):
        run_ai_native_feedback_loop(
            reference_dir=tmp_path, initial_native_dir=native,
            bindings={}, model="local-vlm",
            endpoint="http://127.0.0.1:8000/v1/chat/completions",
            psd2live_source=tmp_path, output=tmp_path / "invalid")
