"""CPU-only scheduling checks for explicit Colab model/program downloads."""
from __future__ import annotations

import threading
import time

import pytest

from tools import colab_mode_prepare as prepare


def test_independent_setup_tasks_start_concurrently_and_all_finish():
    barrier = threading.Barrier(3, timeout=8)
    seen = []
    lock = threading.Lock()

    def task(name):
        with lock:
            seen.append(("start", name))
        barrier.wait()
        with lock:
            seen.append(("done", name))

    prepare._run_parallel(tuple(
        (name, lambda name=name: task(name))
        for name in ("Blender", "TripoSR", "alpha")
    ))
    assert len([x for x in seen if x[0] == "start"]) == 3
    assert len([x for x in seen if x[0] == "done"]) == 3
    assert all(x[0] == "start" for x in seen[:3])


def test_setup_failure_aggregates_without_false_success():
    seen = []

    def fail():
        seen.append("failed")
        raise ValueError("pinned checksum mismatch")

    def success():
        seen.append("succeeded")

    with pytest.raises(RuntimeError, match="pinned checksum mismatch"):
        prepare._run_parallel((("model", fail), ("packages", success)))
    assert sorted(seen) == ["failed", "succeeded"]


def test_preparation_validates_mode_before_installing(monkeypatch):
    monkeypatch.setattr(
        prepare.runpy, "run_path",
        lambda *args, **kwargs: pytest.fail("invalid mode must not run setup"),
    )
    with pytest.raises(ValueError, match="Unknown preparation mode"):
        prepare.prepare_selected_mode("unknown", prewarm_first_gpu=False)
    with pytest.raises(ValueError, match="Invalid usage"):
        prepare.prepare_selected_mode("3d", usage="unknown",
                                      prewarm_first_gpu=False)


def test_3d_downloads_overlap_program_sources(monkeypatch):
    calls = []
    from tools import install_2d_workers
    from tools import setup_blender_runtime
    from tools import colab_gpu_warmup

    monkeypatch.setattr(colab_gpu_warmup, "available_face_worker", lambda: True)
    monkeypatch.setattr(
        install_2d_workers, "activate_alpha_environment",
        lambda: calls.append("alpha"),
    )
    monkeypatch.setattr(
        setup_blender_runtime, "ensure_blender_runtime",
        lambda *args: calls.append("blender"),
    )
    contract = {
        "ensure_runtime": lambda: calls.append("runtime"),
        "_sync_triposr": lambda: calls.append("triposr"),
        "prepare_models": lambda mode: calls.append("models:" + mode),
        "require_runtime_ready": lambda mode: calls.append("verified:" + mode),
        "WORK_ROOT": prepare.ROOT,
    }
    monkeypatch.setattr(prepare.runpy, "run_path", lambda *a, **kw: contract)
    prepare.prepare_selected_mode("3d", prewarm_first_gpu=True)
    assert calls[0] == "runtime"
    assert set(calls[1:5]) == {"alpha", "blender", "triposr", "models:3d"}
    assert calls[-1] == "verified:3d"


def test_2d_downloads_and_worker_install_are_independent(monkeypatch):
    calls = []
    from tools import install_2d_workers
    from tools import colab_gpu_warmup

    monkeypatch.setattr(colab_gpu_warmup, "available_face_worker", lambda: True)
    monkeypatch.setattr(
        install_2d_workers, "activate_2d_environment",
        lambda: calls.append("2d-packages"),
    )
    contract = {
        "ensure_runtime": lambda: calls.append("runtime"),
        "prepare_models": lambda mode: calls.append("models:" + mode),
        "require_runtime_ready": lambda mode: calls.append("verified:" + mode),
    }
    monkeypatch.setattr(prepare.runpy, "run_path", lambda *a, **kw: contract)
    prepare.prepare_selected_mode("live2d", prewarm_first_gpu=True)
    assert calls[0] == "runtime"
    assert set(calls[1:3]) == {"2d-packages", "models:live2d"}
    assert calls[-1] == "verified:live2d"
