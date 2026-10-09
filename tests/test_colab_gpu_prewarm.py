"""CPU-only evidence for real one-shot GPU model prewarming and reuse."""
from __future__ import annotations

from contextlib import contextmanager
import json
import os
import socket
import threading
import time

import pytest

from tools import colab_gpu_warmup as warm
from tools import prefetch_model_assets as assets


@pytest.fixture
def paths(tmp_path, monkeypatch):
    monkeypatch.setattr(warm, "WARM_ROOT", tmp_path)
    monkeypatch.setattr(warm, "READY", tmp_path / "face_ready.json")
    monkeypatch.setattr(warm, "SOCKET", tmp_path / "face.sock")
    return tmp_path


def test_gpu_prewarm_is_not_enabled_for_ordinary_model_prefetch(monkeypatch):
    monkeypatch.delenv("VTUBER_GPU_PREWARM", raising=False)
    seen = []
    monkeypatch.setattr(
        assets, "run_model_task",
        lambda label, code, timeout: seen.append(label),
    )
    assets.prefetch_mode("common_2d")
    assert "first-gpu-face-detector" not in seen
    assert "anime_face_yolov3" in seen
    assert "anime_face_hrnetv2" in seen


def test_first_gpu_warmup_overlaps_other_model_downloads(monkeypatch):
    monkeypatch.setenv("VTUBER_GPU_PREWARM", "1")
    seen = {}
    monkeypatch.setattr(
        assets, "run_model_task",
        lambda label, code, timeout: seen.setdefault(label, code),
    )
    assets.prefetch_mode("common_2d")
    assert "first-gpu-face-detector" in seen
    assert "start_face_worker" in seen["first-gpu-face-detector"]
    assert "resolve_anime_face_model_paths" in seen["first-gpu-face-detector"]
    assert "anime_face_yolov3" not in seen
    assert "anime_face_hrnetv2" not in seen
    assert "flux2_klein_4b" in seen
    assert "sam2_1_hiera_tiny" in seen


def test_preloaded_real_face_model_answers_first_request_then_unloads(
    paths, monkeypatch, tmp_path,
):
    import vtuber_pipeline.avatar.face_detector as face_module
    import vtuber_pipeline.common.stage_runner as stage_module

    observed = []
    @contextmanager
    def fake_lock(*, timeout_sec):
        observed.append(("acquired", timeout_sec))
        try:
            yield
        finally:
            observed.append(("released", None))

    class Detector:
        def __init__(self):
            observed.append(("weights", "loaded"))
        def detect(self, path):
            observed.append(("inference", path))
            return {"landmarks": [[1, 1]] * 28, "bbox": [0, 0, 10, 10]}

    monkeypatch.setattr(stage_module, "_process_gpu_lock", fake_lock)
    monkeypatch.setattr(face_module, "AnimeFaceDetector", Detector)
    image = tmp_path / "face.png"
    image.write_bytes(b"fake; not opened by mock")
    failures = []

    def serve():
        try:
            warm._serve_face_once(idle_seconds=5)
        except BaseException as exc:
            failures.append(exc)

    thread = threading.Thread(target=serve)
    thread.start()
    try:
        end = time.monotonic() + 4
        while not warm.available_face_worker() and time.monotonic() < end:
            time.sleep(0.01)
        assert warm.available_face_worker()
        result = warm.detect_warmed_face(str(image))
        assert result["bbox"] == [0, 0, 10, 10]
    finally:
        thread.join(timeout=7)
    assert not thread.is_alive(), "one-shot model did not unload after face request"
    assert failures == []
    assert observed[0] == ("acquired", 240)
    assert observed[1] == ("weights", "loaded")
    assert observed[2][0] == "inference"
    assert observed[-1] == ("released", None)
    assert not warm.available_face_worker()


def test_generation_proxy_never_initializes_a_second_face_model(monkeypatch):
    from vtuber_pipeline.avatar import face_detector as face_module
    monkeypatch.setenv("VTUBER_GENERATION_WORKER", "1")
    monkeypatch.setattr(warm, "available_face_worker", lambda: True)
    monkeypatch.setattr(
        face_module, "_create_pinned_anime_face_detector",
        lambda: pytest.fail("must not load a duplicate GPU model"),
    )
    called = []
    monkeypatch.setattr(
        warm, "detect_warmed_face",
        lambda image: called.append(image) or {
            "landmarks": [[0, 0]] * 28, "bbox": [0, 0, 4, 4],
        },
    )
    detector = face_module.AnimeFaceDetector()
    assert detector._prewarmed
    assert detector.detect("/tmp/first_face.png")["bbox"] == [0, 0, 4, 4]
    assert called == ["/tmp/first_face.png"]


def test_stale_ready_file_does_not_claim_gpu_model(paths):
    warm.READY.write_text(
        json.dumps({"pid": 99999999, "state": "ready"}), encoding="utf-8"
    )
    assert not warm.available_face_worker()
