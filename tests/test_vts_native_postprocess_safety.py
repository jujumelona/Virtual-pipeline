"""CPU-only regression for optional See-through postprocessing safety."""
import json
from pathlib import Path

import pytest
from PIL import Image


@pytest.mark.parametrize("damage", ["single_pixel", "corrupt_psd", "composite_failure", "layer_iteration_failure"])
def test_optional_native_split_rejects_corruption(tmp_path, monkeypatch, damage):
    from psd_tools import PSDImage
    from tools import vts_subprocess
    from tools.vts_production import _safe_refine_psd

    script = tmp_path / "inference/scripts/heuristic_partseg.py"
    script.parent.mkdir(parents=True)
    script.write_text("# mocked native CLI", encoding="utf-8")
    source = tmp_path / "original.psd"
    source.write_bytes(b"base PSD fixture")
    (tmp_path / "original_depth.psd").write_bytes(b"depth fixture")
    (tmp_path / "original.psd.json").write_text(
        json.dumps({"parts": {"hair": {}}}), encoding="utf-8")
    calls = []

    def fake_run(command, **kwargs):
        mode = command[3]
        calls.append(mode)
        if mode == "seg_wdepth":
            return 1
        (tmp_path / "original_lrsplit.psd").write_bytes(b"candidate fixture")
        return 0

    class Leaf:
        def is_group(self):
            return False

    class FakePSD:
        size = (64, 64)

        def __init__(self, path):
            self.split = "lrsplit" in str(path)

        def composite(self):
            if self.split and damage == "composite_failure":
                raise ValueError("invalid PSD composite")
            canvas = Image.new("RGBA", self.size, (20, 40, 80, 255))
            if self.split:
                canvas.putpixel((7, 9), (205, 40, 80, 255))
            return canvas

        def descendants(self):
            if self.split and damage == "layer_iteration_failure":
                raise RuntimeError("invalid PSD layer tree")
            return [Leaf() for _ in range(3 if self.split else 2)]

    def open_psd(path):
        if damage == "corrupt_psd" and "lrsplit" in str(path):
            raise ValueError("invalid PSD data")
        return FakePSD(path)

    monkeypatch.setattr(vts_subprocess, "run_logged", fake_run)
    monkeypatch.setattr(PSDImage, "open", open_psd)
    assert _safe_refine_psd(
        source, third_party=tmp_path, worker_python="python") == source
    assert calls == ["seg_wdepth", "seg_wlr"]
