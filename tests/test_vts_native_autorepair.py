"""No fabricated success: native rig candidates must pass real pose QA gates."""
from pathlib import Path
from zipfile import ZipFile

import pytest

from tools.vts_native_autorepair import (
    search_native_rig, repair_existing_artwork_zip, _pose_score
)


def _psd(tmp_path):
    p = tmp_path / "original.psd"
    p.write_bytes(b"dummy layered PSD for injected test" * 2)
    return p


def _pose(passed):
    return {
        "pose_activity_passed": passed,
        "native_pose_geometry_passed": passed,
        "native_mouth_interpolation_passed": passed,
        "parameter_isolation": {"passed": passed},
    }


def test_native_search_tries_later_candidate_and_requires_all_gates(tmp_path):
    psd = _psd(tmp_path)
    calls = []
    def builder(source, output, *, edition, **opts):
        assert source == psd
        assert edition == "free"
        output.mkdir(parents=True)
        model3 = output / "real_candidate.model3.json"
        model3.write_text("{}")
        calls.append(dict(opts))
        return {"model3_json": str(model3), "candidate": opts}
    def renderer(model3, output):
        output.mkdir(parents=True)
        return _pose(len(calls) >= 2)
    result = search_native_rig(
        psd, tmp_path / "search", build=builder, render=renderer)
    assert result["winner"] == 1
    assert len(calls) == 2
    assert result["model_verified_by_native_pose"] is True
    assert result["vts_application_tracking_verified"] is False


def test_native_search_refuses_files_without_valid_motion(tmp_path):
    psd = _psd(tmp_path)
    def builder(source, output, *, edition, **opts):
        output.mkdir(parents=True)
        model3 = output / "dead.model3.json"
        model3.write_text("{}")
        return {"model3_json": str(model3)}
    def renderer(model3, output):
        return _pose(False)
    with pytest.raises(RuntimeError, match="NO_PASSING_CANDIDATE"):
        search_native_rig(psd, tmp_path / "trials", build=builder,
                          render=renderer)
    assert (tmp_path / "trials/autorig_search.json").is_file()


def test_native_search_does_not_accept_partial_mouth_or_isolation_pass(tmp_path):
    p = _pose(True)
    p["parameter_isolation"]["passed"] = False
    assert _pose_score(p)[0] == 3
    p["parameter_isolation"]["passed"] = True
    p["native_mouth_interpolation_passed"] = False
    assert _pose_score(p)[0] == 3


def test_existing_psd_is_not_resegmented_during_repair(tmp_path):
    original = tmp_path / "artwork.zip"
    with ZipFile(original, "w") as archive:
        archive.writestr("avatar.psd", b"fake original PSD pixels " * 4)
    def builder(source, output, *, edition, **opts):
        assert source.read_bytes() == b"fake original PSD pixels " * 4
        output.mkdir(parents=True)
        model3 = output / "model3.json"
        model3.write_text("{}")
        return {"model3_json": str(model3)}
    def renderer(model3, output):
        output.mkdir(parents=True)
        return _pose(True)
    def package(model, source, target):
        assert source == original
        with ZipFile(target, "w") as zipfile:
            zipfile.writestr("model.moc3", b"test")
    result = repair_existing_artwork_zip(
        original, tmp_path / "fixed", build=builder, render=renderer,
        package=package)
    assert result["state"] == "psd2live_rigged_native_pose_verified"
    with ZipFile(result["package"]) as archive:
        assert "qa/native_autorepair_search.json" in archive.namelist()


def test_invalid_candidate_budget_does_not_fake_pass(tmp_path):
    psd = _psd(tmp_path)
    with pytest.raises(ValueError, match="1..8"):
        search_native_rig(psd, tmp_path / "output", candidates=())
