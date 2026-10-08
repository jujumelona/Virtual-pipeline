"""Commercial-safe InstantMesh *reconstruction* from TripoSR-derived priors.

Use only TencentARC/InstantMesh LRM weights. NEVER invoke the official run.py
here: its Zero123++ v1.2 multiview generator has CC-BY-NC-4.0 weights.
The six views here are synthetic renderings of TripoSR geometry; they are NOT
independent views of the original subject and must retain low confidence.
"""
from __future__ import annotations
import json
from pathlib import Path


AZIMUTHS = (30, 90, 150, 210, 270, 330)
ELEVATIONS = (20, -10, 20, -10, 20, -10)


def _render_coarse_views(coarse_obj: str, front_rgba: str):
    import cv2
    import numpy as np
    import trimesh
    from PIL import Image

    mesh = trimesh.load(coarse_obj, force="mesh", process=False)
    if not isinstance(mesh, trimesh.Trimesh) or len(mesh.faces) < 100:
        raise ValueError("TripoSR prior does not contain a useful triangle mesh")
    raw = np.asarray(mesh.vertices, dtype=np.float64)
    if not np.isfinite(raw).all():
        raise ValueError("TripoSR prior has nonfinite coordinates")
    # TripoSR is Y-up; InstantMesh camera utilities are Z-up.
    oriented = np.stack((raw[:, 0], -raw[:, 2], raw[:, 1]), axis=1)
    extent = np.ptp(oriented, axis=0)
    scale = max(float(extent.max()), 1e-8)
    coords = (oriented - np.median(oriented, axis=0)) * (1.8 / scale)
    faces = np.asarray(mesh.faces, dtype=np.int64)

    colors = None
    try:
        rgba = np.asarray(mesh.visual.to_color().vertex_colors)
        if len(rgba) == len(coords) and np.ptp(rgba[:, :3]) > 10:
            colors = rgba[:, :3].astype(np.uint8)
    except Exception:
        pass
    if colors is None:
        # Front-painted colors are only an approximate visual prior. Backside
        # colors are NOT asserted to have been observed.
        front = np.asarray(Image.open(front_rgba).convert("RGBA"))
        h, w = front.shape[:2]
        x = coords[:, 0]
        y = coords[:, 2]
        px = np.clip(np.rint((x / 2.0 + 0.5) * (w - 1)).astype(int), 0, w - 1)
        py = np.clip(np.rint((0.5 - y / 2.0) * (h - 1)).astype(int), 0, h - 1)
        colors = front[py, px, :3].copy()
        colors[front[py, px, 3] < 10] = (190, 190, 190)

    backgrounds = []
    for azimuth, elevation in zip(AZIMUTHS, ELEVATIONS):
        a = np.deg2rad(float(azimuth))
        e = np.deg2rad(float(elevation))
        eye = np.array([4 * np.cos(e) * np.cos(a),
                        4 * np.cos(e) * np.sin(a), 4 * np.sin(e)])
        backward = eye / np.linalg.norm(eye)
        forward_right = np.cross(np.array([0., 0., 1.]), backward)
        forward_right /= max(float(np.linalg.norm(forward_right)), 1e-8)
        up = np.cross(backward, forward_right)
        cam = np.stack((forward_right, up, backward), axis=1)
        transformed = (coords - eye) @ cam
        depth = -transformed[:, 2]
        depth = np.maximum(depth, 1e-5)
        focal = 0.5 / np.tan(np.deg2rad(15.0))
        points = np.stack(((transformed[:, 0] / depth * focal + .5) * 320,
                           (.5 - transformed[:, 1] / depth * focal) * 320), axis=1)
        image = np.full((320, 320, 3), 255, dtype=np.uint8)
        # Painter order uses the mean camera depth; this is a *visual prior*
        # for the LRM, not a visibility-accurate source-image reconstruction.
        face_depth = depth[faces].mean(axis=1)
        for index in np.argsort(face_depth)[::-1]:
            tri = faces[index]
            if np.any(transformed[tri, 2] >= -1e-3):
                continue
            polygon = np.rint(points[tri]).astype(np.int32)
            if np.all((polygon[:, 0] < 0) | (polygon[:, 0] >= 320)):
                continue
            mean_color = colors[tri].mean(axis=0).astype(np.uint8)
            cv2.fillConvexPoly(image, polygon, mean_color.tolist())
        backgrounds.append(image)

    return np.stack(backgrounds, axis=0)


def reconstruct_lrm_from_coarse(
    front_rgba: str, coarse_obj: str, config_path: str, model_checkpoint: str,
    output_dir: str,
) -> dict:
    """Invoke actual official InstantMesh large LRM without Zero123++ weights."""
    import numpy as np
    import torch
    from omegaconf import OmegaConf
    from src.utils.train_util import instantiate_from_config
    from src.utils.camera_util import get_zero123plus_input_cameras
    from src.utils.mesh_util import save_obj

    for candidate in (front_rgba, coarse_obj, config_path, model_checkpoint):
        if not Path(candidate).is_file():
            raise FileNotFoundError(candidate)
    if not torch.cuda.is_available():
        raise RuntimeError("InstantMesh LRM requires the selected Colab T4 CUDA runtime")
    stacked = _render_coarse_views(coarse_obj, front_rgba)
    if stacked.shape != (6, 320, 320, 3):
        raise RuntimeError("Generated reference stack is not six 320x320 RGB views")

    config = OmegaConf.load(config_path)
    model = instantiate_from_config(config.model_config)
    data = torch.load(model_checkpoint, map_location="cpu", weights_only=False)
    if not isinstance(data, dict) or "state_dict" not in data:
        raise RuntimeError("InstantMesh checkpoint has no state_dict")
    state = {k[14:]: v for k, v in data["state_dict"].items()
             if k.startswith("lrm_generator.")}
    if not state:
        raise RuntimeError("InstantMesh checkpoint has no LRM weights")
    model.load_state_dict(state, strict=True)
    model = model.cuda()
    model.init_flexicubes_geometry(torch.device("cuda"), fovy=30.0)
    model.eval()

    view_tensor = torch.from_numpy(stacked).permute(0, 3, 1, 2).contiguous()
    images = view_tensor.float().div(255).unsqueeze(0).cuda()
    cameras = get_zero123plus_input_cameras(batch_size=1, radius=4.0).cuda()
    with torch.inference_mode():
        planes = model.forward_planes(images, cameras)
        vertices, faces, vertex_colors = model.extract_mesh(
            planes, use_texture_map=False, **config.infer_config
        )
    del model, planes, view_tensor, images
    torch.cuda.empty_cache()
    root = Path(output_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    output = root / "multiview_mesh.obj"
    save_obj(vertices, faces, vertex_colors, str(output))
    if not output.is_file() or output.stat().st_size < 128:
        raise RuntimeError("InstantMesh LRM produced no OBJ mesh")
    cam = root / "instantmesh_camera.json"
    cam.write_text(json.dumps({
        "origin_model": "TencentARC/InstantMesh LRM only",
        "input_prior": "TripoSR projected into six synthetic views",
        "observed_view": False,
        "observed_views": ["front"],
        "inferred_views": ["six_approximated_from_triposr"],
        "independent_geometry_evidence": False,
        "used_zero123plus": False,
        "commercial_dependency_status": "no CC-BY-NC Zero123++ checkpoint invoked",
        "units": "unknown",
        "camera": "synthetic 30deg FOV, not physically calibrated",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"mesh_obj": str(output), "camera_json": str(cam),
            "render_dir": str(root)}
