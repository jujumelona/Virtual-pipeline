"""Execute pinned vendor crop geometry with real OpenCV, without GPU weights."""
from pathlib import Path
import os
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from tools import vts_see_through_batch as adapter

FIXTURE = Path(__file__).parent / "fixtures/seethrough"


def run_crop(tmp_path, bbox, *, patched=True, size=(64, 96)):
    cv2 = pytest.importorskip("cv2")
    source = (FIXTURE / "layerdiff.py.txt").read_text()
    if patched:
        source = adapter.patch_quantized_head_crop(source)
    context = {"np": np, "cv2": cv2, "Image": Image, "os": os, "osp": os.path}
    exec((FIXTURE / "cv.py.txt").read_text(), context)

    class Generator:
        def __init__(self, **kw):
            pass

        def manual_seed(self, seed):
            return self

    context["torch"] = SimpleNamespace(Generator=Generator)
    exec(source, context)
    calls = []

    class Pipeline:
        unet = SimpleNamespace(device="cpu")

        def __call__(self, **kw):
            calls.append(kw)
            results = [np.zeros((64, 64, 4), dtype=np.uint8)
                       for _ in kw["prompt"]]
            if kw["group_index"] == 0 and bbox is not None:
                x, y, w, h = bbox
                results[2][y:y+h, x:x+w, 3] = 255
            if kw["group_index"] == 1:
                results[0] = kw["fullpage"].copy()
            return SimpleNamespace(images=results)

    image = Image.new("RGBA", size, (80, 90, 100, 200))
    tmp_path.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "part.png"
    image.save(src)
    context["run_layerdiff"](Pipeline(), str(src), str(tmp_path / "out"), 42, 30, 64)
    return calls, tmp_path / "out/part"


@pytest.mark.parametrize("bbox,size", [
    (None, (64, 96)), (None, (96, 64)),
    ((0, 0, 2, 10), (64, 96)), ((25, 15, 1, 1), (16, 24)),
])
def test_empty_or_padding_only_head_uses_full_source_for_head_pass(tmp_path, bbox, size, capsys):
    calls, saved = run_crop(tmp_path, bbox, size=size)
    assert [call["group_index"] for call in calls] == [0, 1]
    assert np.array_equal(calls[1]["fullpage"], calls[0]["fullpage"])
    assert "VTS HEAD_CROP_FALLBACK" in capsys.readouterr().out
    with Image.open(saved / "headwear.png") as im:
        assert np.array_equal(np.asarray(im), calls[0]["fullpage"])
    for name in ["src_img.png", "front hair.png", "head.png", "src_head.png", "headwear.png", "mouth.png"]:
        with Image.open(saved / name) as im:
            assert im.size == (64, 64)


def test_nonempty_head_retains_vendor_crop_and_registered_pixels(tmp_path):
    calls, saved = run_crop(tmp_path, (25, 15, 12, 16))
    original, original_saved = run_crop(tmp_path / "original", (25, 15, 12, 16), patched=False)
    assert np.array_equal(calls[1]["fullpage"], original[1]["fullpage"])
    for part in saved.glob("*.png"):
        assert part.read_bytes() == (original_saved / part.name).read_bytes()


def test_head_crop_adapter_rejects_changed_vendor_boundary():
    source = (FIXTURE / "layerdiff.py.txt").read_text()
    with pytest.raises(RuntimeError, match="head crop"):
        adapter.patch_quantized_head_crop(source.replace("input_img, [hx, hy, hw, hh]", "input_img, coords"))


def test_unadapted_vendor_reproduces_uploaded_empty_resize(tmp_path):
    cv2 = pytest.importorskip("cv2")
    with pytest.raises(cv2.error, match="!ssize.empty"):
        run_crop(tmp_path, None, patched=False)
