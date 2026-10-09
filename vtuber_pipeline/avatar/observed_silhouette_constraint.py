"""Bounded anatomical silhouette term using only a measured RGBA cutout.

The input is a real alpha-matted front photograph, not an LLM-synthesized
silhouette. No projective-camera calibration is claimed. The correction uses
the same normalized orthographic convention as full-body texture projection.
"""
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt


def correct_observed_front_silhouette(
    vertices, face_normals, source_rgba: str | None,
    *, maximum_relative_displacement: float = 0.003,
):
    xyz = np.asarray(vertices, dtype=np.float64)
    normals = np.asarray(face_normals, dtype=np.float64)
    if (xyz.ndim != 2 or xyz.shape[1] != 3 or normals.shape != xyz.shape
            or not np.isfinite(xyz).all() or not np.isfinite(normals).all()):
        raise ValueError("Observed silhouette requires finite matching XYZ and vertex normals")
    if not 0 < maximum_relative_displacement <= .005:
        raise ValueError("Silhouette update bound must be at most half a percent of body height")
    report = {"silhouette_constraint": "skipped", "camera_calibrated": False,
              "modified_vertex_count": 0, "maximum_displacement_mesh_units": 0.}
    if source_rgba is None:
        report["reason"] = "no input foreground cutout"
        return xyz.copy(), report
    path = Path(source_rgba)
    if not path.is_file():
        raise FileNotFoundError(path)
    with Image.open(path) as photo:
        if photo.mode != "RGBA":
            report["reason"] = "no measured alpha channel"
            return xyz.copy(), report
        alpha = np.asarray(photo.getchannel("A"))
    occupied = alpha > 32
    if not occupied.any() or not (~occupied).any():
        report["reason"] = "no distinguished foreground silhouette"
        return xyz.copy(), report

    image_ys, image_xs = np.nonzero(occupied)
    left, right = float(image_xs.min()), float(image_xs.max() + 1)
    top, bottom = float(image_ys.min()), float(image_ys.max() + 1)
    minimum, maximum = xyz.min(axis=0), xyz.max(axis=0)
    width = float(maximum[0] - minimum[0])
    height = float(maximum[1] - minimum[1])
    if width <= 1e-7 or height <= 1e-7:
        raise ValueError("Canonical mesh has degenerate image-plane extent")

    # Only visually front-facing mesh positions can be constrained by front alpha.
    front = np.flatnonzero(normals[:, 2] > .30)
    if len(front) < 16:
        report["reason"] = "insufficient observed front-facing geometry"
        return xyz.copy(), report
    xs = left + (xyz[front, 0] - minimum[0]) / width * (right - left)
    ys = bottom - (xyz[front, 1] - minimum[1]) / height * (bottom - top)
    cx = np.clip(np.rint(xs).astype(int), 0, occupied.shape[1] - 1)
    cy = np.clip(np.rint(ys).astype(int), 0, occupied.shape[0] - 1)
    outside = ~occupied[cy, cx]
    if not outside.any():
        report["silhouette_constraint"] = "already_inside_observed_alpha"
        return xyz.copy(), report

    # Distance-transform nearest true foreground pixel. This is an approximate
    # foreground consistency gradient, not a claimed calibrated silhouette fit.
    distances, indices = distance_transform_edt(~occupied, return_indices=True)
    row = cy[outside]
    col = cx[outside]
    src = front[outside]
    dx_pixels = indices[1, row, col].astype(float) - xs[outside]
    dy_pixels = indices[0, row, col].astype(float) - ys[outside]
    delta = np.column_stack((dx_pixels * width / max(right - left, 1),
                            -dy_pixels * height / max(bottom - top, 1)))
    lengths = np.linalg.norm(delta, axis=1)
    cap = height * maximum_relative_displacement
    step = .18 * delta
    step *= np.minimum(1., cap / np.maximum(np.linalg.norm(step, axis=1), 1e-9))[:, None]
    corrected = xyz.copy()
    corrected[src, :2] += step
    if not np.isfinite(corrected).all():
        raise RuntimeError("Silhouette gradient generated invalid coordinates")
    report.update({
        "silhouette_constraint": "observed_alpha_bounded_step",
        "source_rgba": str(path.resolve()),
        "outside_vertices": int(outside.sum()),
        "initial_mean_outside_distance_pixels": float(distances[row, col].mean()),
        "modified_vertex_count": int(np.count_nonzero(np.linalg.norm(step, axis=1) > 1e-12)),
        "maximum_displacement_mesh_units": float(np.max(np.linalg.norm(step, axis=1))),
        "projection_assumption": "uncalibrated front orthographic",
    })
    return corrected, report
