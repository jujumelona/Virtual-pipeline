"""Texel-space multiview rasterization for fitted avatar meshes.

Every texture pixel receives its own barycentric 3D-to-image projection.
No single source sample is painted across an entire UV triangle.
"""
from __future__ import annotations

import numpy as np


def _bilinear(image: np.ndarray, xy: np.ndarray):
    """Sample RGBA pixels; out-of-frame or transparent samples are invalid."""
    h, w = image.shape[:2]
    x, y = xy[:, 0], xy[:, 1]
    inside = (np.isfinite(x) & np.isfinite(y) &
              (x >= 0) & (y >= 0) & (x < w) & (y < h))
    x = np.clip(np.nan_to_num(x, nan=0), 0, w - 1)
    y = np.clip(np.nan_to_num(y, nan=0), 0, h - 1)
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    x1, y1 = np.minimum(x0 + 1, w - 1), np.minimum(y0 + 1, h - 1)
    wx, wy = (x - x0)[:, None], (y - y0)[:, None]
    samples = (
        image[y0, x0] * (1 - wx) * (1 - wy)
        + image[y0, x1] * wx * (1 - wy)
        + image[y1, x0] * (1 - wx) * wy
        + image[y1, x1] * wx * wy
    )
    return samples, inside & (samples[:, 3] >= 32)


def rasterize_multiview_texture(
    vertices: np.ndarray, faces: np.ndarray, uv: np.ndarray,
    front_pixels: np.ndarray, front_xy: np.ndarray, texture_size: int,
    *, face_pixels: np.ndarray | None = None,
    face_xy: np.ndarray | None = None,
    back_pixels: np.ndarray | None = None,
    back_xy: np.ndarray | None = None,
) -> tuple[np.ndarray, dict]:
    """Paint UV texels with interpolated image coordinates from actual views.

    The face crop applies only to head triangles facing forward; back images
    only to rear-facing triangles. Unobserved surfaces remain explicitly
    marked in the returned visibility mask/statistics. Caller can fill holes.
    """
    vertices = np.asarray(vertices, dtype=np.float64)
    faces = np.asarray(faces, dtype=np.int64)
    uv = np.asarray(uv, dtype=np.float64)
    if vertices.ndim != 2 or vertices.shape[1] != 3:
        raise ValueError("Expected mesh vertices Nx3")
    if uv.shape != (len(vertices), 2):
        raise ValueError("UV/vertex count mismatch")
    if faces.ndim != 2 or faces.shape[1] != 3:
        raise ValueError("Expected triangular faces")
    if not np.isfinite(vertices).all() or not np.isfinite(uv).all():
        raise ValueError("Non-finite mesh/UV coordinates")
    if len(faces) == 0 or np.min(faces) < 0 or np.max(faces) >= len(vertices):
        raise ValueError("Mesh triangle indices are invalid")
    if not isinstance(texture_size, int) or texture_size < 64:
        raise ValueError("Invalid texture_size")

    views = {"front": (front_pixels, front_xy)}
    if face_pixels is not None and face_xy is not None:
        views["face"] = (face_pixels, face_xy)
    if back_pixels is not None and back_xy is not None:
        views["back"] = (back_pixels, back_xy)
    for name, (pixels, projected) in views.items():
        if pixels.ndim != 3 or pixels.shape[2] != 4:
            raise ValueError(f"{name} must be HxWx4 RGBA")
        if np.asarray(projected).shape != (len(vertices), 2):
            raise ValueError(f"{name} projected coordinates must be Nx2")

    canvas = np.zeros((texture_size, texture_size, 4), dtype=np.uint8)
    painted = np.zeros((texture_size, texture_size), dtype=bool)
    y_min = float(vertices[:, 1].min())
    body_height = max(float(np.ptp(vertices[:, 1])), 1e-8)
    texel_count_by_view = {name: 0 for name in views}
    eps = 1e-8
    for tri_indices in faces:
        tri = vertices[tri_indices]
        a, b, c = np.asarray(uv[tri_indices], dtype=np.float64) * (texture_size - 1)
        minx = max(0, int(np.floor(min(a[0], b[0], c[0]))))
        maxx = min(texture_size - 1, int(np.ceil(max(a[0], b[0], c[0]))))
        miny = max(0, int(np.floor(min(a[1], b[1], c[1]))))
        maxy = min(texture_size - 1, int(np.ceil(max(a[1], b[1], c[1]))))
        if minx > maxx or miny > maxy:
            continue
        denom = ((b[1] - c[1]) * (a[0] - c[0]) +
                 (c[0] - b[0]) * (a[1] - c[1]))
        if abs(denom) <= eps:
            continue
        yy, xx = np.mgrid[miny:maxy + 1, minx:maxx + 1]
        px, py = xx.astype(float) + .5, yy.astype(float) + .5
        w0 = ((b[1] - c[1]) * (px - c[0]) +
              (c[0] - b[0]) * (py - c[1])) / denom
        w1 = ((c[1] - a[1]) * (px - c[0]) +
              (a[0] - c[0]) * (py - c[1])) / denom
        w2 = 1.0 - w0 - w1
        mask = (w0 >= -eps) & (w1 >= -eps) & (w2 >= -eps)
        if not mask.any():
            continue
        coords_y, coords_x = yy[mask], xx[mask]
        weights = np.column_stack((w0[mask], w1[mask], w2[mask]))
        normal = np.cross(tri[1] - tri[0], tri[2] - tri[0])
        norm = float(np.linalg.norm(normal))
        facing = float(normal[2] / norm) if norm > eps else 0
        head = float(np.mean(tri[:, 1])) >= y_min + .72 * body_height
        selected = "front"
        if facing < -.12 and "back" in views:
            selected = "back"
        elif facing > .12 and head and "face" in views:
            selected = "face"
        # Try preferred observed view first; front view handles valid holes.
        ordered = [selected] + (["front"] if selected != "front" else [])
        remaining = np.ones(len(coords_x), dtype=bool)
        for name in ordered:
            if not remaining.any():
                break
            pixels, proj = views[name]
            indices = np.flatnonzero(remaining)
            source_xy = weights[indices] @ np.asarray(proj)[tri_indices]
            values, valid = _bilinear(pixels.astype(np.float32, copy=False), source_xy)
            if not valid.any():
                continue
            chosen = indices[valid]
            canvas[coords_y[chosen], coords_x[chosen]] = np.clip(
                values[valid], 0, 255).astype(np.uint8)
            painted[coords_y[chosen], coords_x[chosen]] = True
            remaining[chosen] = False
            texel_count_by_view[name] += int(valid.sum())
    return canvas, {
        "painted_texels": int(painted.sum()),
        "painted_fraction": float(painted.mean()),
        "view_texel_samples": texel_count_by_view,
        "projection": "barycentric-per-texel",
        "unobserved_texels": int((~painted).sum()),
    }
