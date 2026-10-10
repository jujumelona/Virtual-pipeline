"""Live2D GPU subprocesses share the serial worker lock; no models needed."""
from contextlib import contextmanager
import sys
import types

import pytest
from PIL import Image


@pytest.mark.parametrize("worker", ["see_through", "qwen"])
def test_live2d_inference_stops_prewarm_and_holds_gpu_lock(monkeypatch, tmp_path,
                                                        worker):
    from tools import colab_gpu_warmup, vts_production, vts_qwen_refine, vts_subprocess
    from vtuber_pipeline.common import stage_runner
    events = []
    monkeypatch.setattr(colab_gpu_warmup, "available_face_worker", lambda: True)
    monkeypatch.setattr(colab_gpu_warmup, "stop_face_worker", lambda: events.append("stop"))

    @contextmanager
    def lock(timeout_sec):
        events.append("lock")
        try:
            yield
        finally:
            events.append("unlock")

    monkeypatch.setattr(stage_runner, "_process_gpu_lock", lock)

    class InferenceStopped(Exception):
        pass

    def run_logged(*args, **kwargs):
        events.append("inference")
        assert events == ["stop", "lock", "inference"]
        raise InferenceStopped

    monkeypatch.setattr(vts_subprocess, "run_logged", run_logged)
    master = tmp_path / "master.png"
    Image.new("RGBA", (16, 16)).save(master)
    third_party = tmp_path / "third_party"
    output = tmp_path / "output"
    if worker == "see_through":
        program = third_party / "inference/scripts/inference_psd_quantized.py"
        program.parent.mkdir(parents=True)
        program.write_text("# fixture")
        monkeypatch.setitem(sys.modules, "torch", types.SimpleNamespace(
            cuda=types.SimpleNamespace(is_available=lambda: True,
                                      get_device_capability=lambda _: (8, 0))))
        invoke = lambda: vts_production.run_see_through(
            master, output, third_party=third_party, timeout=30)
    else:
        program = third_party / "Stable-Layers/decompose.py"
        program.parent.mkdir(parents=True)
        program.write_text("# fixture")
        snapshot = tmp_path / "snapshot"
        adapter = snapshot / "model/adapter_model.safetensors"
        adapter.parent.mkdir(parents=True)
        adapter.touch()
        monkeypatch.setitem(sys.modules, "huggingface_hub", types.SimpleNamespace(
            snapshot_download=lambda *args, **kwargs: str(snapshot)))
        monkeypatch.setattr(vts_qwen_refine, "_patch_pinned_official",
                            lambda *args, **kwargs: "# fixture")
        monkeypatch.setattr(vts_qwen_refine, "validate_qwen_runtime_source",
                            lambda script: {"syntax": "PASS", "gpu_inference_verified": False})
        invoke = lambda: vts_qwen_refine.infer(
            master, output, third_party=third_party, timeout=30)
    with pytest.raises(InferenceStopped):
        invoke()
    assert events == ["stop", "lock", "inference", "unlock"]
