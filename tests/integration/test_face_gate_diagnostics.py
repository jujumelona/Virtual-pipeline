"""Live face-gate diagnostics and cropped portrait detection contracts."""

from __future__ import annotations

import pathlib
import sys
import types

from PIL import Image

from vtuber_pipeline.core.stage_progress import stage_reporter


def test_waist_up_portrait_face_area_passes_real_scored_gate(tmp_path, monkeypatch):
    """The user-facing upper-body image class was rejected by a 5% face rule."""
    from vtuber_pipeline.avatar.input_gate import validate_input
    import vtuber_pipeline.avatar.face_detector as face_module

    image = tmp_path / "portrait.png"
    Image.new("RGB", (1024, 1344), (245, 245, 245)).save(image)
    landmarks = [
        [480.0 if i < 14 else 640.0, 270.0 + 6.0 * (i % 14)]
        for i in range(28)
    ]

    class Detector:
        def detect(self, image_path):
            return {
                "bbox": [430.0, 220.0, 690.0, 420.0],
                "landmarks": landmarks,
                "landmark_scores": [0.90] * 28,
                "score": 0.96,
            }

    monkeypatch.setattr(face_module, "AnimeFaceDetector", Detector)
    events = []
    with stage_reporter(lambda *args: events.append(args)):
        gate = validate_input(str(image), str(tmp_path / "out"))
    assert gate["face_area_ratio"] < 0.05
    assert gate["face_area_ratio"] >= 0.015
    assert gate["status"] == "complete", gate
    assert len(gate["landmarks"]) == 28
    messages = [msg for name, status, msg in events if name == "input_diagnostics"]
    assert any("validate_input source=" in msg for msg in messages)
    assert any("landmarks=28" in msg and "scores=28" in msg for msg in messages)
    assert any("face_area_ratio=" in msg for msg in messages)
    assert any("gate status=complete" in msg for msg in messages)


def test_face_detector_retries_upper_crop_and_exposes_every_attempt(tmp_path, monkeypatch):
    import vtuber_pipeline.avatar.face_detector as face_module

    fake_package = types.SimpleNamespace(create_detector=lambda backend: None)
    monkeypatch.setitem(sys.modules, "anime_face_detector", fake_package)
    image = tmp_path / "full.png"
    Image.new("RGB", (480, 1000), (245, 245, 245)).save(image)

    calls = []

    def backend(image_bgr):
        calls.append(tuple(image_bgr.shape))
        if len(calls) == 1:
            return []
        return [{
            "bbox": [140.0, 150.0, 330.0, 340.0, 0.97],
            "keypoints": [[180.0 + float(i), 190.0, 0.8] for i in range(28)],
        }]

    monkeypatch.setattr(face_module, "_create_pinned_anime_face_detector", lambda: backend)
    events = []
    with stage_reporter(lambda *args: events.append(args)):
        detected = face_module.AnimeFaceDetector().detect(str(image))

    assert len(calls) == 2
    assert calls[0] == (1000, 480, 3)
    assert calls[1] == (680, 480, 3)
    assert detected["score"] == 0.97
    assert detected["bbox"] == [140.0, 150.0, 330.0, 340.0]
    assert len(detected["landmarks"]) == 28
    logs = [detail for name, status, detail in events if name == "face_detector"]
    assert any("pass=full detections=0" in msg for msg in logs)
    assert any("pass=upper-body detections=1" in msg for msg in logs)
    assert any("selected pass=upper-body" in msg for msg in logs)


def test_detector_failure_includes_traceback_and_failing_checks(tmp_path, monkeypatch):
    from vtuber_pipeline.avatar.input_gate import validate_input
    import vtuber_pipeline.avatar.face_detector as face_module

    image = tmp_path / "portrait.png"
    Image.new("RGB", (480, 1000), (245, 245, 245)).save(image)

    class Detector:
        def detect(self, image_path):
            raise ValueError("no valid 28-point detection")

    monkeypatch.setattr(face_module, "AnimeFaceDetector", Detector)
    events = []
    with stage_reporter(lambda *args: events.append(args)):
        gate = validate_input(str(image), str(tmp_path / "out"))
    assert gate["status"] == "error"
    assert gate["landmark_count"] == 0
    assert "ValueError: no valid 28-point detection" in gate["errors"][0]
    assert any(
        name == "input_diagnostics" and status == "error"
        and "Traceback" in detail and "no valid 28-point detection" in detail
        for name, status, detail in events
    )



def test_nested_detector_import_failure_is_not_labeled_package_missing(monkeypatch):
    """Never hide missing transitive dependencies under a generic pip hint."""
    import pytest
    import vtuber_pipeline.avatar.face_detector as module

    monkeypatch.setitem(
        sys.modules, "anime_face_detector",
        types.SimpleNamespace(create_detector=lambda name: None),
    )

    def broken_initialization():
        raise ModuleNotFoundError(
            "No module named 'runtime_missing_backend'",
            name="runtime_missing_backend",
        )

    monkeypatch.setattr(module, "_create_pinned_anime_face_detector", broken_initialization)
    events = []
    with stage_reporter(lambda *args: events.append(args)):
        with pytest.raises(ModuleNotFoundError, match="runtime_missing_backend"):
            module.AnimeFaceDetector()

    diagnostics = [
        detail for stage, status, detail in events
        if stage == "face_model" and status == "error"
    ]
    assert any("runtime_missing_backend" in detail for detail in diagnostics)
    assert not any("패키지를 찾을 수 없습니다" in detail for detail in diagnostics)


def test_only_genuinely_absent_face_detector_package_gets_missing_label(monkeypatch):
    import pytest
    import vtuber_pipeline.avatar.face_detector as module

    monkeypatch.setitem(sys.modules, "anime_face_detector", None)
    with pytest.raises(RuntimeError, match="anime-face-detector 패키지를 찾을 수 없습니다"):
        module.AnimeFaceDetector()


def test_model_preparation_must_instantiate_face_detector_before_cache_marker():
    root = pathlib.Path(__file__).resolve().parents[2]
    source = (root / "tools" / "colab_app.py").read_text(encoding="utf-8")
    begin = source.index("def prepare_models()")
    end = source.index("def _reload_pipeline_modules()", begin)
    function = source[begin:end]
    assert "face-detector-init-ok" in function
    assert "detector = AnimeFaceDetector()" in function
    assert function.index("face-detector-init-ok") < function.index(
        'marker.write_text('
    )

    probe = (root / "tools" / "runtime_abi_probe.py").read_text(encoding="utf-8")
    assert "from anime_face_detector import create_detector" in probe
    assert "anime_face_detector.detector" in probe
