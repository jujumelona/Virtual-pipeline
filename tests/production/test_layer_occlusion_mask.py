"""Hidden restoration should only run where an actual front part overlaps."""
import json
from pathlib import Path

import numpy as np
from PIL import Image

from vtuber_pipeline.perception.layer_split import split_semantic_layers


def test_no_foreground_occlusion_does_not_generate_flux_task(tmp_path):
    image = tmp_path / "source.png"
    Image.new("RGBA", (256, 256), (200, 150, 140, 255)).save(image)
    face = np.zeros((256, 256), dtype=np.uint8)
    face[55:205, 50:205] = 255
    face_path = tmp_path / "face.png"
    Image.fromarray(face, "L").save(face_path)
    manifest = tmp_path / "masks.json"
    manifest.write_text(json.dumps({"parts": [
        {"semantic_id": "face", "mask_png": str(face_path)},
    ]}))
    doc = split_semantic_layers(str(image), str(manifest), "unused", str(tmp_path / "layers"))
    assert len(doc.parts) == 1
    assert doc.parts[0].hidden_fill_mask_png is None


def test_only_strictly_higher_z_overlap_is_repaired(tmp_path):
    image = tmp_path / "source.png"
    Image.new("RGBA", (256, 256), (200, 150, 140, 255)).save(image)
    # Hair begins directly above the face edge and can occlude the face
    # within the prescribed narrow extension band.
    face = np.zeros((256, 256), dtype=np.uint8)
    hair = np.zeros_like(face)
    face[80:205, 50:205] = 255
    hair[68:83, 65:180] = 255
    layers = []
    for name, array in (("face", face), ("hair.front", hair)):
        path = tmp_path / (name + ".png")
        Image.fromarray(array, "L").save(path)
        layers.append({"semantic_id": name, "mask_png": str(path)})
    manifest = tmp_path / "masks.json"
    manifest.write_text(json.dumps({"parts": layers}))
    doc = split_semantic_layers(str(image), str(manifest), "unused", str(tmp_path / "layers"))
    by_name = {p.semantic_id: p for p in doc.parts}
    assert by_name["hair.front"].hidden_fill_mask_png is None
    assert by_name["face"].hidden_fill_mask_png is not None
    hidden = np.asarray(Image.open(by_name["face"].hidden_fill_mask_png))
    assert np.count_nonzero(hidden) > 0
    # Missing exterior background is not an underlying character feature.
    assert not np.any(hidden[205:])
