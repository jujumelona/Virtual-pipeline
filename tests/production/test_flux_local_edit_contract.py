"""Isolated crop/alpha regression: no FLUX weights or GPU needed."""
import numpy as np
from PIL import Image

from tools.model_workers.flux_worker import prepare_masked_edit
from vtuber_pipeline.perception.compose import masked_repair


def test_model_sees_bounded_crop_with_explicit_gray_hole():
    source = Image.new("RGB", (1536, 2048), (11, 22, 33))
    mask = Image.new("L", source.size)
    data = np.zeros((2048, 1536), dtype=np.uint8)
    data[960:973, 720:731] = 255
    mask = Image.fromarray(data, "L")
    patch, box = prepare_masked_edit(source, mask)
    assert patch.size[0] <= 1024 and patch.size[1] <= 1024
    assert patch.width % 16 == 0 and patch.height % 16 == 0
    assert 720 >= box[0] and 731 <= box[2]
    assert 960 >= box[1] and 973 <= box[3]
    pixels = np.asarray(patch)
    assert np.any(np.all(pixels == [128, 128, 128], axis=-1))
    assert np.any(np.all(pixels == [11, 22, 33], axis=-1))


def test_masked_crop_composition_preserves_visible_pixels_exactly():
    source = np.full((32, 48, 4), (15, 25, 35, 255), dtype=np.uint8)
    mask = np.zeros((32, 48), dtype=np.uint8)
    mask[12:20, 22:28] = 255
    generated = np.full((32, 48, 3), (200, 100, 50), dtype=np.uint8)
    result = masked_repair(source, generated, mask)
    assert np.array_equal(result[mask == 0], source[mask == 0])
    assert np.all(result[mask > 0, :3] == (200, 100, 50))
