"""The FINAL handoff gate must reject the reported flat-proxy VTuber body failure.

This checks deterministic artifact defects; it does not assert visual quality or
Cubism Editor certification. Intermediate legacy sprite ZIPs remain supported.
"""
from io import BytesIO
from zipfile import ZipFile

import pytest
from PIL import Image

from tools.validate_image_ai_artwork_zip import validate


def _png(colour):
    im = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    for y in range(32, 200):
        for x in range(32, 200):
            im.putpixel((x, y), (*colour, 255))
    data = BytesIO()
    im.save(data, format="PNG")
    return data.getvalue()


def _pack(tmp_path, *, flat=False, psd=False, masks=False, inputs=False, json_file=False):
    path = tmp_path / "generated_artwork.zip"
    with ZipFile(path, "w") as z:
        sprite1 = "isolated_parts/BODY_flat_proxy.png" if flat else "isolated_parts/torso.png"
        z.writestr(sprite1, _png((192, 196, 204)))
        z.writestr("isolated_parts/face.png", _png((240, 204, 201)))
        z.writestr("layer_order.txt", sprite1 + "\n" + "isolated_parts/face.png\n")
        z.writestr("outputs/master.png", _png((240, 204, 201)))
        z.writestr("previews/composite.png", _png((240, 204, 201)))
        if psd:
            z.writestr("body.psd", b"8BPS" + b"\x00" * 40)
        if masks:
            z.writestr("alpha_masks/face.png", _png((255, 255, 255)))
        if inputs:
            z.writestr("inputs/source.png", _png((220, 200, 180)))
        if json_file:
            z.writestr("qa/layers.json", "{}")
    return path


def test_legacy_intermediate_png_pack_stays_valid(tmp_path):
    validate(_pack(tmp_path), edition="pro")


def test_final_rejects_flat_body_even_with_other_files(tmp_path):
    path = _pack(tmp_path, flat=True, psd=True, masks=True, inputs=True, json_file=True)
    with pytest.raises(ValueError, match="flat BODY proxy"):
        validate(path, final_live2d_body=True)


@pytest.mark.parametrize(
    ("missing", "message"),
    [
        ("psd", "layered PSD"),
        ("masks", "alpha masks"),
        ("inputs", "original input"),
        ("json_file", "JSON"),
    ],
)
def test_final_rejects_incomplete_handoff(tmp_path, missing, message):
    kwargs = dict(psd=True, masks=True, inputs=True, json_file=True)
    kwargs[missing] = False
    with pytest.raises(ValueError, match=message):
        validate(_pack(tmp_path, **kwargs), final_live2d_body=True)
