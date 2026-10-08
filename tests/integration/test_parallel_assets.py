"""Ensure setup downloads independent immutable assets in bounded parallel jobs."""

from __future__ import annotations

import importlib.util
import pathlib
import threading

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _module():
    spec = importlib.util.spec_from_file_location(
        "model_prefetch_contract", ROOT / "tools" / "prefetch_model_assets.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_all_required_asset_download_tasks_are_explicit_and_pinned():
    mod = _module()
    assert [name for name, _ in mod.TASKS] == [
        "TripoSR", "YOLO/HRNet", "u2net", "DINO", "MakeHuman",
    ]
    source = " ".join(code for _, code in mod.TASKS)
    for symbol in (
        "resolve_triposr_model", "resolve_anime_face_model_paths",
        "_verify_rembg_u2net", "DINO_MODEL_REVISION", "get_template_path",
    ):
        assert symbol in source
    assert mod.MAX_WORKERS == 3


def test_three_independent_assets_actually_start_concurrently():
    mod = _module()
    active = 0
    peak = 0
    lock = threading.Lock()
    rendezvous = threading.Barrier(3)

    def runner(name, code):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        try:
            rendezvous.wait(timeout=10)
        finally:
            with lock:
                active -= 1

    mod.prefetch_assets(
        [("one", "1"), ("two", "2"), ("three", "3")],
        workers=3, runner=runner,
    )
    assert peak == 3


def test_download_error_prevents_preflight_success():
    mod = _module()
    seen = []

    def runner(name, code):
        seen.append(name)
        if name == "invalid":
            raise RuntimeError("hash mismatch")

    with pytest.raises(RuntimeError, match="invalid: hash mismatch"):
        mod.prefetch_assets(
            [("valid", "1"), ("invalid", "2")],
            workers=2, runner=runner,
        )
    assert set(seen) == {"valid", "invalid"}


def test_worker_limit_cannot_be_overridden_to_unbounded_parallelism():
    mod = _module()
    with pytest.raises(ValueError, match="workers"):
        mod.prefetch_assets([], workers=100)
    with pytest.raises(ValueError, match="Duplicate"):
        mod.prefetch_assets([("same", "1"), ("same", "2")])


def test_colab_setup_runs_parallel_prefetch_only_after_package_installation():
    source = (ROOT / "tools" / "colab_app.py").read_text(encoding="utf-8")
    prefetch = source.index('str(REPO_DIR / "tools" / "prefetch_model_assets.py")')
    package = source.index('"anime-face-detector==0.1.0"')
    editable = source.index('str(REPO_DIR),', package)
    audit = source.index('str(REPO_DIR / "tools" / "audit_runtime_environment.py")')
    assert package < editable < prefetch < audit
