"""Multilayer PSD and ORA must remain editable, not renamed flattened PNGs."""
from pathlib import Path
import zipfile

import numpy as np
from PIL import Image
from psd_tools import PSDImage

from vtuber_pipeline.common.schemas import Part, PartsDocument
from vtuber_pipeline.two_d.layer_export import write_psd_and_ora


def test_native_multilayer_documents_preserve_layer_names(tmp_path):
    parts = []
    for i, name in enumerate(("hair.front", "face")):
        pixels = np.zeros((32, 24, 4), dtype=np.uint8)
        pixels[4 + i:21 + i, 3 + i:19 + i] = [30 + i * 50, 80, 200, 255]
        rgba = tmp_path / f"layer{i}.png"
        mask = tmp_path / f"mask{i}.png"
        Image.fromarray(pixels, "RGBA").save(rgba)
        Image.fromarray(pixels[:, :, 3], "L").save(mask)
        parts.append(Part(name, str(rgba), str(mask), None,
                          [3 + i, 4 + i, 19 + i, 21 + i],
                          100 - i * 10, [], "user"))
    document = PartsDocument(24, 32, parts, None, "")
    out = write_psd_and_ora(document, str(tmp_path / "out"))
    psd = PSDImage.open(out["psd"])
    assert sorted(x.name for x in psd) == ["face", "hair.front"]
    assert len(psd) == 2
    with zipfile.ZipFile(out["ora"]) as zipped:
        assert zipped.read("mimetype") == b"image/openraster"
        assert b"hair.front" in zipped.read("stack.xml")
        assert b"face" in zipped.read("stack.xml")
        assert zipped.read("data/layer_000.png")[:8] == bytes([137,80,78,71,13,10,26,10])
    assert Path(out["layers_json"]).is_file()
