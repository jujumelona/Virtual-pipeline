"""CPU-only regression tests for serialized model workers and depth artifacts."""
import json

import numpy as np
import pytest

from vtuber_pipeline.common.stage_runner import _outputs, _process_gpu_lock


def test_depth_npy_is_hashed_even_when_nested_in_manifest(tmp_path):
    file_path = tmp_path / "depth_front.npy"
    np.save(file_path, np.array([[0.1, 0.5], [0.2, 0.6]], dtype=np.float32))
    manifest_path = tmp_path / "depth_manifest.json"
    manifest_path.write_text(json.dumps({
        "units": "relative/no-metric-scale",
        "views": {
            "front": {
                "depth_npy": str(file_path),
                "observed_view": True,
                "relative_depth": True,
                "image_size": [2, 2],
            }
        },
    }), encoding="utf-8")
    result = {
        "status": "complete",
        "manifest_json": str(manifest_path),
        "depth_front_npy": str(file_path),
    }
    before = _outputs(result, str(tmp_path))
    assert str(file_path) in before
    assert str(manifest_path) in before
    np.save(file_path, np.zeros((2, 2), dtype=np.float32))
    after = _outputs(result, str(tmp_path))
    assert before[str(file_path)] != after[str(file_path)]


def test_gpu_lock_has_bounded_wait_and_can_be_reacquired(tmp_path, monkeypatch):
    monkeypatch.setenv("VTUBER_GPU_STAGE_LOCK", str(tmp_path / "worker.lock"))
    with _process_gpu_lock(timeout_sec=2):
        with pytest.raises(RuntimeError, match="GPU lock timed out"):
            with _process_gpu_lock(timeout_sec=0):
                pytest.fail("nested independent file handle must not bypass the lock")
    with _process_gpu_lock(timeout_sec=1):
        pass
