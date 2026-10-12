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


def test_official_sam_one_inference_for_sixty_layers_without_second_diffusion(
        monkeypatch, tmp_path):
    """One SAM call, no second diffusion, exact source pixels for 60 parts."""
    from tools import vts_production as production
    from tools import vts_see_through_sam as sam
    from tools import vts_artwork_export as export

    original = []
    for index in range(60):
        part = fixture_part()
        part["name"] = f"body.fragment.{index:02d}"
        original.append(part)
    masks = [Image.new("L", (64, 32), 0) for _ in range(19)]
    masks[2].paste(255, (0, 0, 32, 32))  # face
    masks[11].paste(255, (32, 0, 64, 32))  # topwear
    calls = []

    def sam_once(layers, canvas, *, output, third_party):
        calls.append((len(layers), canvas))
        output.mkdir(parents=True, exist_ok=True)
        log = output / "sam19.log"
        log.write_text("single SAM call")
        return masks, log

    def forbid_second_diffusion(*args, **kwargs):
        pytest.fail("Second LayerDiff/Marigold inference is disabled")

    monkeypatch.setattr(sam, "run_sam_from_package", sam_once)
    monkeypatch.setattr(production, "run_see_through", forbid_second_diffusion)
    refined, trace, logfile = export._apply_official_semantic_sam_once(
        original, (64, 32), output=tmp_path, third_party=tmp_path, edition="pro")
    assert calls == [(60, (64, 32))]
    assert len(trace) == 60 and len(refined) == 120
    assert all(item["accepted"] for item in trace)
    assert logfile.is_file()
    for parent, children in zip(original, (refined[i:i+2] for i in range(0, 120, 2))):
        restored = np.zeros_like(np.asarray(parent["image"]))
        for child in children:
            pixel = np.asarray(child["image"])
            occupied = pixel[..., 3] > 0
            restored[occupied] = pixel[occupied]
        np.testing.assert_array_equal(restored, np.asarray(parent["image"]))


@pytest.mark.parametrize("edition,asset", [
    ("pro", "body"), ("pro", "outfit"),
])
def test_direct_artwork_api_rejects_real_qwen_in_disallowed_modes(tmp_path, edition, asset):
    from tools.vts_artwork_export import build_artwork_package
    with pytest.raises(ValueError, match="only for FREE or PRO hair/accessory"):
        build_artwork_package(tmp_path / "not_read.zip", tmp_path / "out",
                              edition=edition, scope="upper", asset_kind=asset,
                              qwen=True, max_qwen_passes=1)


def test_official_second_pass_grayscale_masks_preserve_exact_source_rgba():
    part = fixture_part()
    left = Image.new("L", (64, 32), 0)
    right = Image.new("L", (64, 32), 0)
    left.paste(255, (0, 0, 32, 32))
    right.paste(255, (32, 0, 64, 32))
    children, status = partition_from_masks(part, [left, right])
    assert status["accepted"] and len(children) == 2
    original = np.asarray(part["image"])
    restored = np.zeros_like(original)
    for child in children:
        pixels = np.asarray(child["image"])
        visible = pixels[:, :, 3] > 0
        restored[visible] = pixels[visible]
    assert np.array_equal(restored, original)


def test_official_second_pass_rejects_rgb_masks_without_coverage_channel():
    part = fixture_part()
    with pytest.raises(ValueError, match="alpha or grayscale"):
        partition_from_masks(part, [Image.new("RGB", (64, 32))] * 2)


@pytest.mark.parametrize("mask_mode", ["RGBA", "L"])
def test_second_pass_background_opaque_does_not_swallow_foreground(mask_mode):
    part = fixture_part()
    def proposal(region):
        grayscale = Image.new("L", (64, 32), 255 if region == "background" else 0)
        if region == "left":
            grayscale.paste(255, (0, 0, 32, 32))
        elif region == "right":
            grayscale.paste(255, (32, 0, 64, 32))
        if mask_mode == "L":
            return grayscale
        rgba = Image.new("RGBA", grayscale.size)
        rgba.putalpha(grayscale)
        return rgba

    masks = [proposal(x) for x in ("background", "left", "right")]
    children, report = partition_from_masks(part, masks)
    assert report["accepted"] is True
    assert len(children) == 2
    observed = {child["image"].getchannel("A").getbbox() for child in children}
    assert observed == {(0, 0, 32, 32), (32, 0, 64, 32)}
    original = np.asarray(part["image"])
    reconstructed = np.zeros_like(original)
    for child in children:
        pixels = np.asarray(child["image"])
        occupied = pixels[:, :, 3] > 0
        reconstructed[occupied] = pixels[occupied]
    assert np.array_equal(reconstructed, original)


@pytest.mark.parametrize("mask_mode", ["RGBA", "L"])
def test_second_pass_all_identical_masks_are_still_rejected(mask_mode):
    part = fixture_part()
    grayscale = Image.new("L", (64, 32), 255)
    mask = grayscale if mask_mode == "L" else Image.new("RGBA", (64, 32), (0, 0, 0, 255))
    children, report = partition_from_masks(part, [mask, mask.copy(), mask.copy()])
    assert children == [part]
    assert report["accepted"] is False
    assert report["reason"] == "no_meaningful_division"
