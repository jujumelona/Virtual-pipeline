"""Pixel interpolation regression: textured triangles must not be flat colors."""
import numpy as np
from vtuber_pipeline.avatar.uv_projection import rasterize_multiview_texture


def test_triangle_has_distinct_texel_samples():
    vertices = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], float)
    faces = np.array([[0, 1, 2]], int)
    uv = np.array([[.15, .15], [.85, .15], [.15, .85]], float)
    front = np.full((128, 128, 4), 255, np.uint8)
    front[..., 0] = np.arange(128, dtype=np.uint8)[None, :]
    front[..., 1] = np.arange(128, dtype=np.uint8)[:, None]
    projected = np.array([[16, 16], [112, 16], [16, 112]], float)
    out, stats = rasterize_multiview_texture(
        vertices, faces, uv, front, projected, 128)
    assert stats["projection"] == "barycentric-per-texel"
    assert stats["painted_texels"] > 1000
    painted = out[out[..., 3] > 0]
    assert np.unique(painted[:, :3], axis=0).shape[0] > 100


def test_transparent_input_never_invents_coverage():
    vertices = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], float)
    uv = np.array([[.1, .1], [.9, .1], [.1, .9]], float)
    transparent = np.zeros((32, 32, 4), np.uint8)
    texture, stats = rasterize_multiview_texture(
        vertices, np.array([[0, 1, 2]]), uv, transparent,
        np.array([[1, 1], [30, 1], [1, 30]], float), 64)
    assert stats["painted_texels"] == 0
    assert not texture.any()
