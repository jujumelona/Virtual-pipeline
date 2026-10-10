"""CPU contract tests: no model downloads, not a GPU-quality certification."""
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from tools.vts_official_second_pass import partition_from_masks
from tools.vts_see_through_batch import patch_quantized_batch


def fixture_part():
    rgba = Image.new("RGBA", (64, 32), (0, 0, 0, 0))
    for y in range(32):
        for x in range(64):
            rgba.putpixel((x, y), (x * 3, y * 7, 145, 90 + (x % 166)))
    return {"name": "unknown.raw.001", "image": rgba, "depth": 0}


def split_masks():
    left = Image.new("RGBA", (64, 32), (0, 0, 0, 0))
    right = Image.new("RGBA", (64, 32), (0, 0, 0, 0))
    left.paste((0, 0, 0, 255), (0, 0, 32, 32))
    right.paste((0, 0, 0, 255), (32, 0, 64, 32))
    return [left, right]


def test_official_second_pass_uses_every_unknown_name_and_exact_source_rgba():
    part = fixture_part()
    children, status = partition_from_masks(part, split_masks())
    assert status["accepted"]
    assert len(children) == 2
    original = np.asarray(part["image"])
    reconstructed = np.zeros_like(original)
    for child in children:
        x = np.asarray(child["image"])
        occupied = x[:, :, 3] > 0
        reconstructed[occupied] = x[occupied]
    assert np.array_equal(reconstructed, original)
    assert children[0]["name"].startswith("unknown.raw.001.pass2.")


def test_official_second_pass_rejects_trivial_unchanged_masks():
    part = fixture_part()
    masks = [part["image"].copy(), part["image"].copy()]
    children, status = partition_from_masks(part, masks)
    assert children == [part]
    assert not status["accepted"]
    assert status["reason"] == "no_meaningful_division"


def test_official_second_pass_rejects_bad_size_and_missing_coverage():
    part = fixture_part()
    with pytest.raises(ValueError, match="source canvas"):
        partition_from_masks(part, [Image.new("RGBA", (32, 32))] * 2)
    masks = [Image.new("RGBA", (64, 32)) for _ in range(2)]
    children, status = partition_from_masks(part, masks)
    assert children == [part]
    assert status["reason"] == "insufficient_mask_coverage"


def test_batch_patch_loads_each_model_once_and_visits_all_sources():
    pinned = ("import os\nimport os.path as osp\nimport json\nimport time\n"
              "import torch\n"
              "if __name__ == '__main__':\n"
              "    srcp = args.srcp\n"
              "    run_layerdiff(None, srcp, '', 0, 30, 1280)\n"
              '    print(f\'Stats saved to {osp.join(saved, "stats.json")}\')\n')
    result = patch_quantized_batch(pinned)
    assert result.count("pipeline = build_layerdiff_pipeline(args)") == 1
    assert result.count("marigold_pipe = build_marigold_pipeline(args)") == 1
    assert result.count("run_layerdiff(pipeline, srcp") == 1
    assert result.count("run_marigold(marigold_pipe, srcp") == 1
    assert result.index("del pipeline") < result.index("marigold_pipe = build_marigold_pipeline")
    assert result.count("for index, srcp in enumerate(sources, 1)") == 3
    assert "[VTS BATCH] complete count=" in result
    with pytest.raises(RuntimeError, match="single-image worker changed"):
        patch_quantized_batch(pinned.replace("srcp = args.srcp", "srcp = 'changed'"))


def test_official_pass_attempts_each_initial_layer_once(monkeypatch, tmp_path):
    from tools import vts_production as production, vts_artwork_export as export
    import tools.vts_official_second_pass as second

    a, b = fixture_part(), fixture_part()
    b["name"] = "other.unknown"
    original = [a, b]
    calls = []

    def batch(sources, work, **kwargs):
        calls.append(sorted(p.name for p in Path(sources).glob("*.png")))
        assert kwargs["qwen"] is False
        return {name: tmp_path / (name + ".psd") for name in calls[-1]}

    monkeypatch.setattr(production, "run_see_through", batch)
    monkeypatch.setattr(production, "psd_to_registered_rgba",
                        lambda p, d, **kwargs: (None, tmp_path / "layers.zip", 2))
    monkeypatch.setattr(production, "restore_source_canvas",
                        lambda p, c, d: (tmp_path / "restored.zip", {"test": True}))
    monkeypatch.setattr(export, "_read_registered", lambda _: (
        [{"image": im, "name": str(i)} for i, im in enumerate(split_masks())],
        (64, 32),
    ))
    result, trace, _ = export._refine_all_layers_official_once(
        original, (64, 32), output=tmp_path, third_party=tmp_path, edition="free")
    assert calls == [["source_0000.png", "source_0001.png"]]
    assert len(trace) == 2 and all(item["accepted"] for item in trace)
    assert len(result) == 4
