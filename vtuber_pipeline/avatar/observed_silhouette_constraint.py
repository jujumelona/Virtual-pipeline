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


def correct_observed_multiview_silhouettes(
    vertices, normals, observed_rgba_by_role: dict[str, str],
    *, maximum_relative_displacement: float = .003,
):
    """Use actually segmented front/back/left/right observations as weak constraints.

    Photographs are not metrically camera-calibrated. Fit only the silhouette
    (not texture pixels) in the corresponding orthographic projection,
    recording each per-view source and never treating inferred views as seen.
    The shape keeps its existing vertex indexing and topology.
    """
    coords = np.asarray(vertices, dtype=np.float64)
    surface_normals = np.asarray(normals, dtype=np.float64)
    if (coords.ndim != 2 or coords.shape[1] != 3
            or surface_normals.shape != coords.shape
            or not np.isfinite(coords).all() or not np.isfinite(surface_normals).all()):
        raise ValueError("Multi-view silhouette requires finite matching XYZ and normals")
    if not observed_rgba_by_role:
        return coords.copy(), {"roles": {}, "constraint": "no_observed_alpha_views"}
    if set(observed_rgba_by_role) - {"front", "back", "left", "right"}:
        raise ValueError("Only independently observed camera roles are valid")
    # Validate the provenance files before geometry math. A user supplying
    # a nonexistent observed cutout must receive the actionable missing-file
    # error even when the canonical mesh itself is also degenerate.
    for observed_role, observed_path in observed_rgba_by_role.items():
        if not isinstance(observed_path, str) or not Path(observed_path).is_file():
            raise FileNotFoundError(
                f"{observed_role}: observed silhouette cutout missing: {observed_path}")
    # The view normal is the actual outward canonical direction. The horizontal
    # projection flips between front/back and left/right; camera poses are
    # orthographic conventions, NOT calibration evidence.
    cameras = {
        "front": (0, 1, 2, +1, +1),
        "back": (0, 1, 2, -1, -1),
        "left": (2, 1, 0, +1, -1),
        "right": (2, 1, 0, -1, +1),
    }
    result = coords.copy()
    output = {}
    height = float(np.ptp(coords[:, 1]))
    if height <= 1e-6:
        raise ValueError("Unusable canonical model height")
    for role in ("front", "back", "left", "right"):
        if role not in observed_rgba_by_role:
            continue
        file = Path(observed_rgba_by_role[role])
        if not file.is_file():
            raise FileNotFoundError(f"{role}: observed silhouette cutout missing: {file}")
        with Image.open(file) as image:
            if image.mode != "RGBA":
                raise ValueError(f"{role}: observed model input must be alpha-cutout RGBA")
            alpha = np.asarray(image.getchannel("A"))
        foreground = alpha > 32
        if not foreground.any() or not (~foreground).any():
            output[role] = {
                "status": "skipped_no_alpha", "observed": True,
                "modified_vertex_count": 0,
            }
            continue
        ys, xs = np.nonzero(foreground)
        lx, rx = float(xs.min()), float(xs.max()+1)
        ty, by = float(ys.min()), float(ys.max()+1)
        horiz, vertical, facing_axis, flip, normal_sign = cameras[role]
        origin = result.min(axis=0)
        span = np.ptp(result, axis=0)
        if span[horiz] <= 1e-8:
            raise ValueError(f"{role}: degenerate model camera-plane extent")
        candidates = np.flatnonzero(surface_normals[:, facing_axis] * normal_sign > .30)
        if len(candidates) < 16:
            output[role] = {
                "status": "skipped_no_visible_surface", "observed": True,
                "modified_vertex_count": 0,
            }
            continue
        proportion = (result[candidates, horiz] - origin[horiz]) / span[horiz]
        if flip < 0:
            proportion = 1 - proportion
        screen_x = lx + proportion * (rx-lx)
        screen_y = by - (result[candidates, vertical] - origin[vertical]) / span[vertical] * (by-ty)
        cx = np.clip(np.rint(screen_x).astype(int), 0, foreground.shape[1]-1)
        cy = np.clip(np.rint(screen_y).astype(int), 0, foreground.shape[0]-1)
        outside = ~foreground[cy, cx]
        if not outside.any():
            output[role] = {
                "status": "inside_observed_alpha", "observed": True,
                "modified_vertex_count": 0,
            }
            continue
        dist, nearest = distance_transform_edt(~foreground, return_indices=True)
        row, col = cy[outside], cx[outside]
        dx = (nearest[1, row, col].astype(float) - screen_x[outside])
        dy = (nearest[0, row, col].astype(float) - screen_y[outside])
        plane = np.column_stack((
            dx * span[horiz] / max(rx - lx, 1) * flip,
            -dy * span[vertical] / max(by - ty, 1),
        )) * .18
        cap = maximum_relative_displacement * height
        magnitude = np.linalg.norm(plane, axis=1)
        plane *= np.minimum(1.0, cap / np.maximum(magnitude, 1e-8))[:, None]
        current = result[candidates[outside]].copy()
        current[:, horiz] += plane[:, 0]
        current[:, vertical] += plane[:, 1]
        result[candidates[outside]] = current
        output[role] = {
            "status": "bounded_observed_silhouette",
            "observed": True,
            "source_rgba": str(file.resolve()),
            "modified_vertex_count": int(np.count_nonzero(np.linalg.norm(plane, axis=1) > 1e-12)),
            "outside_vertices": int(np.count_nonzero(outside)),
            "mean_original_silhouette_error_pixels": float(dist[row, col].mean()),
            "max_displacement_mesh_units": float(np.max(np.linalg.norm(plane, axis=1))),
        }
    if not np.isfinite(result).all():
        raise RuntimeError("Nonfinite 3D multi-view silhouette result")
    return result, {
        "constraint": "observed_orthographic_rgba_multiview",
        "camera_calibrated": False,
        "metric_depth_calibrated": False,
        "model_topology_changed": False,
        "roles": output,
    }
