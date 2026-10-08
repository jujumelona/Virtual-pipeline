"""Commercially permissive multiview geometry using pinned TripoSR (MIT).

Unlike InstantMesh, this path does not import Zero123++, Nvidia proprietary
rendering code, nvdiffrast or OpenLRM noncommercial weights. Each user-supplied
view is reconstructed independently and registered in the canonical front
frame. An absent view remains UNOBSERVED, never secretly synthesized.
"""
from __future__ import annotations
import json
from pathlib import Path

YAW_RADIANS = {"back": 3.141592653589793,
               "left": 1.5707963267948966,
               "right": -1.5707963267948966}
MAX_NORMALIZED_REGISTRATION_ERROR = 0.22


def register_observed_geometry(front_vertices, view_vertices, role: str):
    """Conservative labelled-camera registration; do not freely rotate views.

    The expected yaw is fixed from the supplied role. Only isotropic scale
    and translation can adapt. This prevents nearest-neighbour ICP aligning a
    labelled back image to the front with the wrong camera orientation.
    """
    import numpy as np
    from scipy.spatial import cKDTree
    if role not in YAW_RADIANS:
        raise ValueError("Only observed back/left/right camera roles are supported")
    reference = np.asarray(front_vertices, dtype=np.float64)
    view = np.asarray(view_vertices, dtype=np.float64)
    if (reference.ndim != 2 or view.ndim != 2 or
        reference.shape[1:] != (3,) or view.shape[1:] != (3,) or
        len(reference) < 16 or len(view) < 16 or
        not np.isfinite(reference).all() or not np.isfinite(view).all()):
        raise ValueError("Registration requires finite real triangular geometry")
    h_front = float(np.ptp(reference[:, 1]))
    h_view = float(np.ptp(view[:, 1]))
    if min(h_front, h_view) < 1e-7:
        raise ValueError("Degenerate observed view")
    scale = h_front / h_view
    if not 0.2 <= scale <= 5.0:
        raise ValueError("Observed view differs unreasonably in height")
    theta = YAW_RADIANS[role]
    co, si = np.cos(theta), np.sin(theta)
    rotation = np.array([[co, 0., -si], [0., 1., 0.], [si, 0., co]])
    source_center = np.median(view, axis=0)
    destination_center = np.median(reference, axis=0)
    transformed = (view - source_center) @ rotation * scale + destination_center
    # Comparing all vertices would unduly punish legitimate back-only hair and
    # clothing shapes; trimmed distances measure overlap of shared anatomy.
    distances, _ = cKDTree(reference).query(transformed, k=1)
    residual = float(np.mean(np.sort(distances)[:max(16, int(len(distances) * .65))]))
    normalized = residual / h_front
    if not np.isfinite(normalized):
        raise ValueError("Registration yielded nonfinite residual")
    return transformed, {"camera_role": role, "camera_yaw_radians": theta,
                         "scale": float(scale),
                         "normalized_registration_error": normalized,
                         "accepted": normalized <= MAX_NORMALIZED_REGISTRATION_ERROR,
                         "orientation": "role-labelled, not physically calibrated"}


def reconstruct_licensed_multiview(
    front_mesh: str, source_views: dict[str, str | None],
    output_dir: str, *, profile: str = "commercial",
) -> dict:
    """Fuse TripoSR single-image reconstruction from independently supplied views.

    User-supplied optional views failing registration are rejected with a
    recorded reason rather than contaminating the canonical humanoid fit.
    The front mesh is always the existing real TripoSR output.
    """
    import numpy as np
    import trimesh
    from vtuber_pipeline.avatar.reconstruction import reconstruct_avatar
    from vtuber_pipeline.perception.anime_alpha import create_person_alpha

    root = Path(output_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    front_file = Path(front_mesh).resolve()
    if not front_file.is_file():
        raise FileNotFoundError(front_file)
    base = trimesh.load(front_file, force="mesh", process=False)
    if (not isinstance(base, trimesh.Trimesh) or
        len(base.vertices) < 100 or len(base.faces) < 100 or
        not np.isfinite(base.vertices).all()):
        raise ValueError("Front TripoSR mesh is empty or corrupt")
    if not isinstance(source_views, dict) or set(source_views) - set(YAW_RADIANS):
        raise ValueError("Only named observed back/left/right source images are allowed")
    geometries = [base]
    reports = {"front": {"source_mesh": str(front_file),
                         "source_model": "TripoSR", "observed_input": True}}
    accepted = []
    for role in ("back", "left", "right"):
        image = source_views.get(role)
        if image is None:
            reports[role] = {"provided": False, "status": "unobserved"}
            continue
        source = Path(image).resolve()
        if not source.is_file():
            raise FileNotFoundError(f"{role}: {source}")
        role_dir = root / role
        role_dir.mkdir(parents=True, exist_ok=True)
        # Independent segmentation and reconstruction are deliberately serial:
        # model inference subprocesses release T4 GPU memory between views.
        segmented = create_person_alpha(str(source), str(role_dir / "alpha"))
        alpha = segmented.get("rgba_png")
        if segmented.get("status") != "complete" or not alpha or not Path(alpha).is_file():
            raise RuntimeError(f"{role}: true input alpha segmentation failed")
        mesh_path = reconstruct_avatar(
            str(alpha), str(role_dir / "triposr"),
            profile=profile, model_save_format="obj", remove_background=False,
        )
        view = trimesh.load(mesh_path, force="mesh", process=False)
        if not isinstance(view, trimesh.Trimesh) or len(view.faces) < 100:
            raise ValueError(f"{role}: unusable TripoSR mesh")
        transformed, metrics = register_observed_geometry(
            np.asarray(base.vertices), np.asarray(view.vertices), role,
        )
        record = {**metrics, "input_image": str(source),
                  "source_mesh": str(Path(mesh_path).resolve()),
                  "source_model": "TripoSR",
                  "input_view_observed": True,
                  "mesh_geometry_inferred": True}
        if metrics["accepted"]:
            copied = view.copy()
            copied.vertices = transformed
            geometries.append(copied)
            accepted.append(role)
            record["status"] = "registered"
        else:
            record["status"] = "rejected_alignment"
            record["reason"] = "independent geometry not consistent with canonical front"
        reports[role] = record

    combined = trimesh.util.concatenate(geometries)
    mesh_out = root / "registered_observed_views.obj"
    combined.export(mesh_out)
    if not mesh_out.is_file() or mesh_out.stat().st_size < 128:
        raise RuntimeError("Commercially licensed multiview output is missing")
    manifest = root / "licensed_multiview.json"
    details = {
        "contract": "vtuber-commercial-triposr-multiview-v1",
        "geometry_provider": "VAST-AI-Research/TripoSR (MIT source and weights)",
        "registered_views": accepted,
        "views": reports,
        "front_only": not accepted,
        "observed_cameras_calibrated": False,
        "inferred_views_are_observed": False,
        "noncommercial_checkpoints_used": False,
        "geometry_mesh": str(mesh_out),
        "quality_limitations": (
            "Single-view TripoSR estimates unseen geometry; separate observed "
            "views improve constraints but are not metric camera calibration."
        ),
    }
    manifest.write_text(json.dumps(details, ensure_ascii=False, indent=2,
                                   allow_nan=False), encoding="utf-8")
    return {"status": "complete", "mesh_obj": str(mesh_out),
            "provenance_json": str(manifest),
            "output_path": str(mesh_out), "registered_views": accepted,
            "source_model": "TripoSR multiview (MIT)"}
