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


def test_premultiplied_alpha_preserves_hair_color_at_transparent_edge():
    from vtuber_pipeline.avatar.uv_projection import _bilinear
    image = np.zeros((2, 2, 4), dtype=np.uint8)
    image[:, :, :3] = 255  # transparent white matte (common exported cutout)
    image[0, 0] = [20, 40, 80, 255]  # opaque colored strand
    colors, valid = _bilinear(image, np.array([[.5, .5]], dtype=float))
    assert valid.tolist() == [True]
    assert np.allclose(colors[0, :3], [20, 40, 80], atol=1e-5)
    assert np.isclose(colors[0, 3], 255 / 4)


def test_uv_renderer_never_converts_entire_reference_frame_for_each_triangle():
    import inspect
    from vtuber_pipeline.avatar.uv_projection import rasterize_multiview_texture
    source = inspect.getsource(rasterize_multiview_texture)
    assert "pixels.astype(np.float32" not in source
    assert "values, valid = _bilinear(pixels, source_xy)" in source
