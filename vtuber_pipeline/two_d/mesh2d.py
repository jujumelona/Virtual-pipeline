"""Contour-constrained adaptive 2D meshes with all disconnected components.

A triangle is included only when nearly all its rasterized area belongs to
the observed part; concave silhouettes and separated hair islands must not
be bridged by unconstrained Delaunay triangles.
"""
import json
from pathlib import Path

import numpy as np


def _triangle_coverage(binary, coords, cv2) -> float:
    points = np.rint(coords).astype(np.int32)
    h, w = binary.shape
    x0 = max(0, int(points[:, 0].min()))
    y0 = max(0, int(points[:, 1].min()))
    x1 = min(w, int(points[:, 0].max()) + 1)
    y1 = min(h, int(points[:, 1].max()) + 1)
    if x0 >= x1 or y0 >= y1:
        return 0.0
    footprint = np.zeros((y1 - y0, x1 - x0), dtype=np.uint8)
    cv2.fillConvexPoly(footprint, points - [x0, y0], color=1)
    total = int(footprint.sum())
    if not total:
        return 0.0
    covered = int(np.count_nonzero(
        (footprint > 0) & (binary[y0:y1, x0:x1] > 0),
    ))
    return covered / total


def generate_meshes(parts_json: str, output_dir: str) -> dict:
    import cv2
    from scipy.spatial import Delaunay
    from PIL import Image

    obj = json.loads(Path(parts_json).read_text(encoding="utf-8"))
    width, height = obj["width"], obj["height"]
    output = []
    for part in obj["parts"]:
        binary = np.uint8(np.asarray(
            Image.open(part["mask_png"]).convert("L"),
        ) > 32)
        if binary.shape != (height, width):
            raise ValueError(f"{part['semantic_id']}: mask has different canvas dimensions")
        contours, _ = cv2.findContours(
            binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE,
        )
        if not contours:
            continue
        fine = any(
            name in part["semantic_id"]
            for name in ("eye", "mouth", "hair", "face")
        )
        step = 12 if fine else 32
        points_all = []
        triangles_all = []
        component_count = 0
        for contour in sorted(contours, key=cv2.contourArea, reverse=True):
            if cv2.contourArea(contour) < 8:
                continue
            approx = cv2.approxPolyDP(
                contour, 1.0 if fine else 3.0, True,
            )[:, 0, :]
            x, y, body_w, body_h = cv2.boundingRect(contour)
            points = [tuple(map(float, p)) for p in approx]
            for gy in range(y + step // 2, y + body_h, step):
                for gx in range(x + step // 2, x + body_w, step):
                    if binary[min(gy, height - 1), min(gx, width - 1)]:
                        points.append((float(gx), float(gy)))
            points = list(dict.fromkeys(points))
            if len(points) < 3:
                continue
            vertices = np.asarray(points, dtype=float)
            triangles = Delaunay(vertices).simplices
            accepted = [
                [int(vertex + len(points_all)) for vertex in tri]
                for tri in triangles
                if _triangle_coverage(binary, vertices[tri], cv2) >= 0.92
            ]
            if not accepted:
                continue
            points_all.extend(points)
            triangles_all.extend(accepted)
            component_count += 1

        if not triangles_all:
            raise ValueError("cannot triangulate " + part["semantic_id"])
        output.append({
            "semantic_id": part["semantic_id"],
            "rgba_png": part["rgba_png"],
            "z_order": part["z_order"],
            "vertices_xy": [list(p) for p in points_all],
            "uv": [[float(x / width), float(y / height)] for x, y in points_all],
            "triangles": triangles_all,
            "connected_components": component_count,
        })

    if not output:
        raise ValueError("no triangulated part meshes")
    dest = Path(output_dir) / "meshes2d.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps({"width": width, "height": height, "meshes": output}, indent=2),
        encoding="utf-8",
    )
    return {"meshes_json": str(dest)}
