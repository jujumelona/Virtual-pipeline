"""No invented frontal observation of hidden 3D surfaces."""
import numpy as np

from vtuber_pipeline.avatar.uv_projection import rasterize_multiview_texture


def _triangle(face_indices, back=None):
    vertices = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=float)
    faces = np.array([face_indices], dtype=np.int64)
    uv = np.array([[.1, .1], [.9, .1], [.1, .9]], dtype=float)
    front = np.full((64, 64, 4), (255, 0, 0, 255), dtype=np.uint8)
    xy = np.array([[1, 1], [61, 1], [1, 61]], dtype=float)
    opts = {} if back is None else {"back_pixels": back, "back_xy": xy}
    return rasterize_multiview_texture(vertices, faces, uv, front, xy, 64, **opts)


def test_backfacing_triangles_do_not_use_front_pixels():
    rgba, stats = _triangle([0, 2, 1])
    assert stats["painted_texels"] == 0
    assert np.count_nonzero(rgba[..., 3]) == 0


def test_rear_reference_is_used_only_when_it_exists():
    rear = np.full((64, 64, 4), (0, 255, 0, 255), dtype=np.uint8)
    rgba, stats = _triangle([0, 2, 1], back=rear)
    assert stats["painted_texels"] > 0
    assert stats["view_texel_samples"]["back"] > 0
    painted = rgba[rgba[..., 3] > 0]
    assert np.all(painted[:, 0] == 0)
    assert np.all(painted[:, 1] == 255)
