"""Execute the vendor NF4 batch adapter on CPU fakes, without a GPU/model download."""
from __future__ import annotations

import argparse
import ast
import json
import os
from pathlib import Path
import time

import pytest

from tools.vts_see_through_batch import patch_quantized_batch


VENDOR_STUB = ("if __name__ == '__main__':\n"
               "    srcp = args.srcp\n"
               "    print(f'Stats saved to {osp.join(saved, \"stats.json\")}')\n")


def _run_batch(tmp_path: Path, filenames: list[str]):
    src = tmp_path / "source"
    src.mkdir()
    for name in filenames:
        (src / name).write_bytes(b"synthetic-png")
    out = tmp_path / "out"
    out.mkdir()
    events = []

    class Cuda:
        def reset_peak_memory_stats(self):
            events.append("reset_stats")

        def empty_cache(self):
            events.append("empty_cache")

        def max_memory_allocated(self):
            return 1024**3

    class Torch:
        cuda = Cuda()

    def layer_model(args):
        events.append("load_LayerDiff")
        return object()

    def depth_model(args):
        events.append("load_Marigold")
        return object()

    def run_layer(pipeline, source, target, seed, steps, res):
        events.append(("LayerDiff", Path(source).name))
        (Path(target) / Path(source).stem).mkdir(parents=True)

    def run_depth(pipeline, source, target, seed, resolution_depth):
        events.append(("Marigold", Path(source).name))

    def assemble(saved, **options):
        events.append(("PSD", Path(saved).name))
        assert options == {"rotate": False, "save_to_psd": True,
                           "tblr_split": True}

    args = argparse.Namespace(srcp=str(src), save_dir=str(out), seed=42,
                              num_inference_steps=30, resolution=1280,
                              resolution_depth=768, quant_mode="nf4",
                              save_to_psd=True, tblr_split=True)
    script = patch_quantized_batch(VENDOR_STUB)
    ast.parse(script)
    context = {"__name__": "__main__", "args": args, "osp": os.path,
               "json": json, "time": time, "torch": Torch(),
               "seed_everything": lambda n: events.append("seed"),
               "build_layerdiff_pipeline": layer_model,
               "build_marigold_pipeline": depth_model,
               "run_layerdiff": run_layer,
               "run_marigold": run_depth,
               "further_extr": assemble}
    error = None
    try:
        exec(compile(script, "adapted_vendor.py", "exec"), context)
    except Exception as exc:
        error = exc
    return events, out, error


def test_nf4_batch_calls_both_models_once_and_psd_per_input(tmp_path):
    events, out, error = _run_batch(tmp_path, ["b.png", "a.png", "ignore.txt"])
    assert error is None, repr(error)
    assert events.count("load_LayerDiff") == 1
    assert events.count("load_Marigold") == 1
    activities = [event for event in events if isinstance(event, tuple)]
    assert activities == [
        ("LayerDiff", "a.png"), ("LayerDiff", "b.png"),
        ("Marigold", "a.png"), ("Marigold", "b.png"),
        ("PSD", "a"), ("PSD", "b"),
    ]
    assert json.loads((out / "a" / "stats.json").read_text())["batch_size"] == 2
    assert json.loads((out / "b" / "stats.json").read_text())["batch_size"] == 2


def test_nf4_batch_rejects_empty_png_before_any_model_load(tmp_path):
    events, _, error = _run_batch(tmp_path, ["notes.txt"])
    assert isinstance(error, ValueError)
    assert "no PNG" in str(error)
    assert "load_LayerDiff" not in events
    assert "load_Marigold" not in events


def test_colab_code_cells_compile_and_preserve_live2d_model_handoffs():
    notebook_path = (Path(__file__).resolve().parents[1] /
                     "notebooks/VTuber_Commercial_Pipeline_Colab_v8.ipynb")
    nb = json.loads(notebook_path.read_text(encoding="utf-8"))
    cells = ["".join(c["source"]) for c in nb["cells"]
             if c.get("cell_type") == "code"]
    assert len(cells) >= 9
    for i, code in enumerate(cells):
        ast.parse(code, filename=f"{notebook_path.name}:cell:{i}")
    setup = next(c for c in cells if "--skip-sam-body" in c)
    production = next(c for c in cells if "sam_body_weights_prefetched" in c)
    assert 'LIVE2D_EDITION == "pro"' in setup
    assert "LIVE2D_USE_QWEN" in production
    assert "VTUBER_SEETHROUGH_PYTHON" in production
