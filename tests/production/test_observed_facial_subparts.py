"""SAM facial masks must produce real editable sublayers only from input evidence."""
import numpy as np
from PIL import Image, ImageDraw
from vtuber_pipeline.perception.facial_subparts import split_facial_subparts


def test_eye_subparts_partition_observed_sam_pixels(tmp_path):
    image = Image.new("RGBA", (96, 80), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle((10, 15, 77, 53), fill=(240, 240, 240, 255))
    draw.rectangle((10, 15, 77, 18), fill=(0, 0, 0, 255))
    draw.ellipse((31, 22, 55, 48), fill=(5, 5, 10, 255))
    source = tmp_path / "src.png"
    image.save(source)
    mask = np.zeros((80, 96), dtype=np.uint8)
    mask[15:54, 10:78] = 255
    inp = tmp_path / "eye.png"
    Image.fromarray(mask).save(inp)
    out = split_facial_subparts(str(source), [
        {"semantic_id": "eye.left", "mask_png": str(inp), "score": .95},
    ], str(tmp_path / "out"))
    assert {p["semantic_id"] for p in out} == {
        "eye.left.iris", "eye.left.lid", "eye.left.white"}
    masks = [np.asarray(Image.open(p["mask_png"])) > 0 for p in out]
    assert all(m.any() for m in masks)
    assert np.array_equal(np.sum(masks, axis=0), mask > 0)
    assert all(p["score"] == .95 for p in out)


def test_flat_eye_never_invents_iris(tmp_path):
    image = tmp_path / "flat.png"
    Image.new("RGBA", (40, 40), (155, 155, 155, 255)).save(image)
    mask = tmp_path / "mask.png"
    Image.new("L", (40, 40), 255).save(mask)
    supplied = {"semantic_id": "eye.left", "mask_png": str(mask)}
    result = split_facial_subparts(str(image), [supplied], str(tmp_path / "out"))
    assert result == [supplied]


def test_mouth_inner_is_real_dark_region(tmp_path):
    im = Image.new("RGBA", (72, 45), (240, 150, 155, 255))
    draw = ImageDraw.Draw(im)
    draw.ellipse((20, 14, 53, 34), fill=(45, 10, 25, 255))
    src = tmp_path / "mouth.png"
    im.save(src)
    mask = tmp_path / "mask.png"
    Image.new("L", im.size, 255).save(mask)
    out = split_facial_subparts(str(src), [
        {"semantic_id": "mouth", "mask_png": str(mask)},
    ], str(tmp_path / "out"))
    assert {p["semantic_id"] for p in out} == {"mouth.inner", "mouth.lip"}
