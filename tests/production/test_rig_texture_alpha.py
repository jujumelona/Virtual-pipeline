"""Real GLB readback catches lost PNG alpha at the skin/material boundary."""
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image
from pygltflib import GLTF2

from vtuber_pipeline.avatar.rigging import create_gltf_with_skin


@pytest.mark.parametrize("mode,alpha,expected", [
    ("RGBA", 128, "BLEND"), ("RGBA", 0, "BLEND"),
    ("RGBA", 255, "OPAQUE"), ("RGB", None, "OPAQUE"),
])
def test_skinned_glb_material_preserves_observed_png_alpha(tmp_path, mode, alpha, expected):
    mesh = SimpleNamespace(
        vertices=np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]]),
        vertex_normals=np.tile([0, 0, 1], (3, 1)), faces=np.array([[0, 1, 2]]),
    )
    skeleton = {
        "inverse_bind_matrices": np.eye(4)[None], "num_joints": 1,
        "names": ["hips"], "parents": [-1], "positions": np.zeros((1, 3)),
    }
    texture = tmp_path / "texture.png"
    pixels = Image.new(mode, (2, 2), (24, 56, 99, 255) if mode == "RGBA" else (24, 56, 99))
    if alpha is not None:
        pixels.putpixel((1, 1), (24, 56, 99, alpha))
    pixels.save(texture)
    source_png = texture.read_bytes()
    uv = tmp_path / "uv.npy"
    np.save(uv, np.array([[0, 0], [1, 0], [0, 1]], dtype=np.float32))
    target = tmp_path / "avatar.glb"
    create_gltf_with_skin(
        mesh, skeleton, np.zeros((3, 4)), np.tile([1, 0, 0, 0], (3, 1)),
        str(target), texture_path=str(texture), uv_path=str(uv),
    )
    actual = GLTF2().load_binary(str(target))
    assert actual.materials[0].alphaMode == expected
    view = actual.bufferViews[actual.images[0].bufferView]
    embedded = actual.binary_blob()[view.byteOffset:view.byteOffset + view.byteLength]
    assert embedded == source_png  # Keep straight-alpha color bytes without conversion.
