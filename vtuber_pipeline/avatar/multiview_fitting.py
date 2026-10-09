"""Register InstantMesh geometry to TripoSR without pretending inferred views were observed.

Registration is a geometry-only constraint. The absolute camera orientation is
not recoverable from two arbitrary mesh exports; it is reported as unverified.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _mesh(path: str):
    import numpy as np
    import trimesh

    loaded = trimesh.load(str(path), process=False)
    if isinstance(loaded, trimesh.Scene):
        meshes = [item for item in loaded.geometry.values() if isinstance(item, trimesh.Trimesh)]
        if not meshes:
            raise ValueError(f"no triangle mesh in {path}")
        loaded = trimesh.util.concatenate(meshes)
    vertices = np.asarray(loaded.vertices, dtype=np.float64)
    if len(vertices) < 16 or len(loaded.faces) < 8 or not np.isfinite(vertices).all():
        raise ValueError(f"invalid non-empty finite mesh required: {path}")
    if np.ptp(vertices, axis=0).max() < 1e-6:
        raise ValueError(f"degenerate mesh: {path}")
    return loaded


def _points(vertices, count=3500):
    import numpy as np

    return vertices[np.linspace(0, len(vertices) - 1, min(count, len(vertices)), dtype=np.intp)]


def _best_similarity(source, target):
    """Trimmed nearest-neighbor ICP with explicit scale, yaw hypotheses and diagnostics."""
    import numpy as np
    from scipy.spatial import cKDTree

    a = _points(source)
    b = _points(target)
    tree = cKDTree(b)
    height_a = np.ptp(a[:, 1])
    height_b = np.ptp(b[:, 1])
    if min(height_a, height_b) < 1e-7:
        raise ValueError("cannot register a mesh with zero vertical extent")
    initial_scale = float(height_b / height_a)
    if not 0.01 <= initial_scale <= 100.0:
        raise ValueError("unreasonable initial mesh scale ratio")
    best = None
    for yaw in (0.0, 0.5 * np.pi, np.pi, 1.5 * np.pi):
        co, si = np.cos(yaw), np.sin(yaw)
        rotation = np.array([[co, 0.0, -si], [0.0, 1.0, 0.0], [si, 0.0, co]])
        scale = initial_scale
        offset = b.mean(axis=0) - (a.mean(axis=0) @ rotation) * scale
        for _ in range(18):
            transformed = scale * (a @ rotation) + offset
            distances, indices = tree.query(transformed)
            keep = distances <= np.quantile(distances, 0.75)
            if keep.sum() < 16:
                raise ValueError("insufficient geometry overlap for registration")
            src = a[keep]
            dst = b[indices[keep]]
            src_center, dst_center = src.mean(axis=0), dst.mean(axis=0)
            src0, dst0 = src - src_center, dst - dst_center
            u, _, vt = np.linalg.svd(src0.T @ dst0)
            correction = np.eye(3)
            correction[-1, -1] = np.sign(np.linalg.det(u @ vt))
            new_rotation = u @ correction @ vt
            denominator = float(np.sum(src0 * src0))
            if denominator < 1e-12:
                raise ValueError("degenerate ICP correspondences")
            new_scale = float(np.sum((src0 @ new_rotation) * dst0) / denominator)
            if not np.isfinite(new_scale) or new_scale <= 0.0:
                raise ValueError("invalid ICP scale")
            new_offset = dst_center - new_scale * (src_center @ new_rotation)
            movement = abs(new_scale - scale) + np.linalg.norm(new_offset - offset)
            rotation, scale, offset = new_rotation, new_scale, new_offset
            if movement < 1e-8:
                break
        distances, _ = tree.query(scale * (a @ rotation) + offset)
        error = float(np.mean(np.sort(distances)[:max(16, int(0.75 * len(distances)))]))
        if not np.isfinite(error):
            raise ValueError("registration has nonfinite residual")
        if best is None or error < best["trimmed_error"]:
            best = {
                "scale": scale, "rotation": rotation, "translation": offset,
                "trimmed_error": error, "yaw_initial_radians": float(yaw),
            }
    return best


def _document(value: str | dict, label: str) -> dict[str, Any]:
    document = json.loads(Path(value).read_text(encoding="utf-8")) if isinstance(value, str) else value
    if not isinstance(document, dict):
        raise ValueError(f"{label} must be a JSON object")
    return document


def align_sources(
    coarse_obj: str,
    multiview_obj: str,
    depth_manifest: str,
    reference_manifest: str | dict,
    output_dir: str,
    *,
    source_metadata: str | None = None,
) -> dict[str, Any]:
    """Return a registered GLB and explicit observation/uncertainty contract.

    The observed front/side/back images remain separate from model-predicted
    multi-view views. No relative-depth value is interpreted as meters.
    """
    import numpy as np

    coarse = _mesh(coarse_obj)
    generated = _mesh(multiview_obj)
    depths = _document(depth_manifest, "depth manifest")
    references = _document(reference_manifest, "reference manifest")
    if depths.get("units") != "relative/no-metric-scale":
        raise ValueError("Depth Anything values must be explicitly labelled relative")
    views = depths.get("views")
    if not isinstance(views, dict) or "front" not in views:
        raise ValueError("a real front depth view is required")
    reference_images = references.get("images")
    if not isinstance(reference_images, dict) or "front" not in reference_images:
        raise ValueError("front source-reference metadata is required")
    observations = {}
    for role, item in views.items():
        if role not in {"front", "face", "back", "left", "right"}:
            raise ValueError(f"unexpected depth view role: {role}")
        if item.get("observed_view") is not True or item.get("relative_depth") is not True:
            raise ValueError(f"{role}: generated data cannot claim observed depth")
        observed_image = reference_images.get(role)
        if not observed_image:
            raise ValueError(f"{role}: depth references an unregistered source image")
        depth_path = Path(item["depth_npy"])
        if not depth_path.is_file():
            raise FileNotFoundError(depth_path)
        values = np.load(depth_path, allow_pickle=False)
        if values.ndim != 2 or values.size == 0 or not np.isfinite(values).all():
            raise ValueError(f"{role}: invalid relative depth map")
        if list(values.shape[::-1]) != list(item["image_size"]):
            raise ValueError(f"{role}: depth map and source image dimensions differ")
        observations[role] = {
            "observed_view": True,
            "depth_npy": str(depth_path.resolve()),
            "source_image": observed_image["path"],
            "relative_depth_only": True,
        }

    licensed_source = None
    independent_roles = []
    if source_metadata is not None:
        licensed_source = _document(source_metadata, "licensed multiview provenance")
        if licensed_source.get("contract") != "vtuber-commercial-triposr-multiview-v1":
            raise ValueError("Unrecognized commercial reconstruction provenance")
        if licensed_source.get("noncommercial_checkpoints_used") is not False:
            raise ValueError("Noncommercial reconstruction weights are forbidden")
        if Path(licensed_source.get("geometry_mesh", "")).resolve() != Path(multiview_obj).resolve():
            raise ValueError("Multiview mesh does not match attested licensed source")
        roles = licensed_source.get("registered_views")
        if not isinstance(roles, list) or len(set(roles)) != len(roles):
            raise ValueError("Registered observed view roles must be unique")
        if set(roles) - {"back", "left", "right"}:
            raise ValueError("Unexpected synthetic camera role in licensed source")
        for role in roles:
            record = licensed_source.get("views", {}).get(role, {})
            reference = reference_images.get(role)
            if (not reference or role not in observations or
                record.get("status") != "registered" or
                record.get("input_view_observed") is not True or
                Path(record.get("input_image", "")).resolve() != Path(reference["path"]).resolve()):
                raise ValueError(f"{role}: license provenance is not supported by an actual observed image/depth")
        independent_roles = roles

    if licensed_source is not None:
        # This file was already assembled in the front camera frame by
        # register_observed_geometry. Running unconstrained ICP here can
        # silently reverse a side/back observation and destroy camera-role
        # registration. Validate the ORIGINAL front mesh prefix instead.
        from scipy.spatial import cKDTree
        front = np.asarray(coarse.vertices, dtype=np.float64)
        fused = np.asarray(generated.vertices, dtype=np.float64)
        if len(fused) < len(front):
            raise ValueError("Licensed multiview mesh lost its canonical front vertices")
        ref_height = max(float(np.ptp(front[:, 1])), 1e-8)
        prefix_error = float(np.max(np.linalg.norm(fused[:len(front)] - front, axis=1)))
        if not np.isfinite(prefix_error) or prefix_error > ref_height * 5e-4:
            raise ValueError(
                "Licensed multiview mesh is not in the original front camera frame"
            )
        distances, _ = cKDTree(front).query(fused, k=1)
        residual = float(np.mean(np.sort(distances)[:max(16, int(len(distances) * .75))]))
        registration = {
            "rotation": np.eye(3),
            "scale": 1.0,
            "translation": np.zeros(3),
            "trimmed_error": residual,
            "yaw_initial_radians": 0.0,
        }
    else:
        # Legacy independent geometry has no attested shared camera frame.
        registration = _best_similarity(np.asarray(generated.vertices), np.asarray(coarse.vertices))
    rotation = registration["rotation"]
    scale = registration["scale"]
    translation = registration["translation"]
    aligned = generated.copy()
    aligned.vertices = np.asarray(generated.vertices) @ rotation * scale + translation
    extent = max(float(np.ptp(np.asarray(coarse.vertices), axis=0).max()), 1e-8)
    normalized_error = registration["trimmed_error"] / extent
    if not np.isfinite(normalized_error) or normalized_error > 0.65:
        raise ValueError(f"multiview geometry could not be registered: normalized error={normalized_error:.3f}")
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    aligned_path = out / "aligned_multiview.glb"
    aligned.export(aligned_path)
    # Front-only candidate is exactly the already-reconstructed source, not
    # an independent view. Bound its weak geometric weight appropriately.
    # Independently supplied images add evidence but are still not calibrated
    # cameras; never grant them full confidence.
    raw_confidence = float(np.clip(1.0 - normalized_error / 0.65, 0.0, 1.0))
    if licensed_source is not None:
        evidence_scale = min(0.85, 0.22 + 0.20 * len(independent_roles))
    else:
        evidence_scale = 1.0

    diagnostics = {
        "contract": "vtuber-multiview-constraints-v1",
        "geometry_provider": (licensed_source or {}).get("geometry_provider", "unspecified"),
        "licensed_multiview_source": str(Path(source_metadata).resolve()) if source_metadata else None,
        "independently_observed_roles": independent_roles,
        "front_only_reconstruction": bool(licensed_source is not None and not independent_roles),
        "reference_frame": "TripoSR mesh local coordinates (not metrically calibrated)",
        "aligned_multiview_glb": str(aligned_path.resolve()),
        "coarse_mesh": str(Path(coarse_obj).resolve()),
        "transform": {
            "scale": float(scale),
            "rotation_row_vector": rotation.tolist(),
            "translation": translation.tolist(),
        },
        "registration": {
            "trimmed_mean_distance": registration["trimmed_error"],
            "normalized_residual": normalized_error,
            "initial_yaw_radians": registration["yaw_initial_radians"],
            "orientation_verified_by_calibrated_camera": False,
            "observed_camera_alignment": False,
            "source_frame_identity_verified": licensed_source is not None,
            "confidence": raw_confidence * evidence_scale,
            "confidence_evidence_multiplier": evidence_scale,
        },
        "observed_views": observations,
        "inferred_views_are_observed": False,
    }
    constraints_path = out / "constraints.json"
    constraints_path.write_text(json.dumps(diagnostics, indent=2, allow_nan=False), encoding="utf-8")
    return {
        "status": "complete",
        "constraints_json": str(constraints_path),
        "aligned_multiview_glb": str(aligned_path),
        "output_path": str(aligned_path),
    }
