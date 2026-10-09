"""Only actual disjoint hair alpha regions generate independent movable layers."""
from pathlib import Path

import numpy as np
from PIL import Image

from vtuber_pipeline.perception.hair_strands import split_observed_hair_islands


def test_disconnected_hair_tufts_become_two_independent_physics_parts(tmp_path):
    mask = np.zeros((64, 80), dtype=np.uint8)
    mask[10:40, 6:26] = 255
    mask[8:45, 54:72] = 255
    file = tmp_path / "mask.png"
    Image.fromarray(mask, "L").save(file)
    result = split_observed_hair_islands([
        {"semantic_id": "hair.front", "mask_png": str(file)},
    ], str(tmp_path / "output"))
    assert [x["semantic_id"] for x in result] == [
        "hair.front.island00", "hair.front.island01",
    ]
    layers = [np.asarray(Image.open(x["mask_png"])) > 0 for x in result]
    assert np.array_equal(sum(layers), mask > 0)
    assert all(layer.any() for layer in layers)


def test_single_connected_mask_is_preserved_without_fake_strand_split(tmp_path):
    mask = tmp_path / "solid.png"
    Image.new("L", (64, 64), 255).save(mask)
    datum = {"semantic_id": "hair.back", "mask_png": str(mask)}
    result = split_observed_hair_islands([datum], str(tmp_path / "output"))
    assert result == [datum]
