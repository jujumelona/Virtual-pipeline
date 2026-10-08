"""Conservative relative-depth *shape* constraint for the observed front view.

This is not a metric camera calibration. It uses only a real input cutout's
silhouette bounding box and independently inferred Depth Anything V2 Small
values, fits affine-invariant relative depth against the facing vertex Z
coordinate, and applies one small bounded gradient step. If no foreground
cutout or statistically consistent relative depth exists, no shape adjustment
is made; missing evidence must never be invented.
"""
from __future__ import annotations
from pathlib import Path

import numpy as np


def correct_relative_front_depth(
    vertices, normals, constraints: dict, references: dict,
    *, maximum_relative_displacement: float = 0.002,
):
    coords = np.asarray(vertices, dtype=np.float64)
    face_normals = np.asarray(normals, dtype=np.float64)
    if coords.ndim != 2 or coords.shape[1] != 3 or not np.isfinite(coords).all():
        raise ValueError("Relative-depth correction requires finite XYZ vertices")
    if face_normals.shape != coords.shape or not np.isfinite(face_normals).all():
        raise ValueError("Invalid front-facing normal contract")
    if not 0 < maximum_relative_displacement <= 0.005:
        raise ValueError("Relative-depth adjustment limit must be small and positive")
    report = {
        "relative_depth_constraint": "skipped",
        "relative_depth_metric_calibrated": False,
        "front_camera_calibrated": False,
        "modified_vertex_count": 0,
        "maximum_displacement_mesh_units": 0.0,
    }
    observed = constraints.get("observed_views", {}).get("front")
    ref = references.get("images", {}).get("front")
    if not observed or not ref:
        report["reason"] = "no observed front-depth reference"
        return coords.copy(), report
    if observed.get("observed_view") is not True or observed.get("relative_depth_only") is not True:
        raise ValueError("Synthetic or metric-labelled depth may not enter relative-depth fitting")
    if Path(observed["source_image"]).resolve() != Path(ref["path"]).resolve():
        raise ValueError("Depth source image and declared front observation do not match")
    bb = ref.get("alpha_foreground_bbox")
    if bb is None:
        report["reason"] = "no reliable original front silhouette bounding box"
        return coords.copy(), report
    if not (isinstance(bb, (list, tuple)) and len(bb) == 4):
        raise ValueError("Front cutout bounds must contain four values")
    lx, ty, rx, by = [float(x) for x in bb]
    size = ref.get("size")
    if not isinstance(size, list) or len(size) != 2:
        raise ValueError("Missing measured source image resolution")
    w, h = [int(x) for x in size]
    if not (0 <= lx < rx <= w and 0 <= ty < by <= h):
        raise ValueError("Invalid observed source alpha extent")
    depth_path = Path(observed["depth_npy"])
    if not depth_path.is_file():
        raise FileNotFoundError(depth_path)
    depth = np.load(depth_path, allow_pickle=False)
    if depth.shape != (h, w) or not np.isfinite(depth).all():
        raise ValueError("Depth values must be finite and aligned to original image pixels")
    spread = np.ptp(coords, axis=0)
    height = float(spread[1])
    if height < 1e-6 or spread[0] < 1e-6:
        raise ValueError("Degenerate canonical shape cannot be aligned")
    candidates = np.flatnonzero(face_normals[:, 2] >= 0.2)
    if len(candidates) < 16:
        report["reason"] = "no trustworthy front-facing vertex subset"
        return coords.copy(), report

    source_xy = np.stack([
        lx + (coords[candidates, 0] - np.min(coords[:, 0])) / spread[0] * (rx - lx),
        by - (coords[candidates, 1] - np.min(coords[:, 1])) / height * (by - ty),
    ], axis=1)
    xi = np.clip(np.rint(source_xy[:, 0]).astype(int), 0, w - 1)
    yi = np.clip(np.rint(source_xy[:, 1]).astype(int), 0, h - 1)
    measured = np.asarray(depth[yi, xi], dtype=np.float64)
    z = coords[candidates, 2]
    if len(measured) < 16 or np.ptp(measured) < 1e-6 or np.ptp(z) < 1e-6:
        report["reason"] = "relative-depth or canonical surface has zero range"
        return coords.copy(), report

    # Both depth maps and uncalibrated mesh coordinates are scale- and
    # offset-ambiguous. Standardize by robust quantiles, never call them meters.
    dlow, dhigh = np.quantile(measured, (0.1, 0.9))
    zlow, zhigh = np.quantile(z, (0.1, 0.9))
    if dhigh - dlow < 1e-6 or zhigh - zlow < 1e-6:
        report["reason"] = "insufficient robust depth variation"
        return coords.copy(), report
    d = (measured - (dlow + dhigh) / 2) / (dhigh - dlow)
    z_relative = (z - (zlow + zhigh) / 2) / (zhigh - zlow)
    correlation = float(np.corrcoef(d, z_relative)[0, 1])
    if not np.isfinite(correlation) or abs(correlation) < 0.20:
        report["reason"] = "unregistered or inconsistent relative depth"
        report["absolute_depth_correlation"] = abs(correlation) if np.isfinite(correlation) else 0.0
        return coords.copy(), report

    # One bounded gradient step on 1/2 ||z_relative - sign*d||^2.
    # Do not change x/y, do not move the rear/hidden portion of the mesh.
    desired = d * np.sign(correlation)
    delta = (desired - z_relative) * (zhigh - zlow)
    max_step = height * maximum_relative_displacement
    confidence = float(constraints.get("registration", {}).get("confidence", 0.0))
    if not np.isfinite(confidence) or not 0 <= confidence <= 1:
        raise ValueError("Invalid depth registration confidence")
    correction = np.clip(delta * confidence * 0.16, -max_step, max_step)
    out = coords.copy()
    out[candidates, 2] += correction
    if not np.isfinite(out).all():
        raise RuntimeError("Relative depth correction generated invalid geometry")
    report.update({
        "relative_depth_constraint": "bounded_gradient_step",
        "absolute_depth_correlation": abs(correlation),
        "relative_depth_adjustment_weight": 0.16 * confidence,
        "maximum_displacement_mesh_units": float(np.max(np.abs(correction))),
        "modified_vertex_count": int(np.count_nonzero(np.abs(correction) > 1e-12)),
        "projection_assumption": "front orthographic silhouette; uncalibrated",
    })
    return out, report
