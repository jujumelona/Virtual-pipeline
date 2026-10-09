"""Real front/back/side photo alpha must constrain canonical body, not invented cameras."""
import numpy as np
from PIL import Image, ImageDraw
import pytest

from vtuber_pipeline.avatar.observed_silhouette_constraint import (
    correct_observed_multiview_silhouettes,
)


def _reference(path):
    im = Image.new("RGBA", (96, 128), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    draw.polygon([(5, 8), (90, 8), (90, 32), (56, 55), (55, 80),
                  (90, 109), (90, 124), (5, 124), (5, 109), (39, 80),
                  (40, 55), (5, 32)], fill=(120, 90, 170, 255))
    im.save(path)
    return str(path)


def test_observed_independent_multiview_constrains_original_geometry(tmp_path):
    screen_x = np.linspace(-1., 1., 24)
    screen_y = np.linspace(0., 2., 18)
    xx, yy = np.meshgrid(screen_x, screen_y)
    coords = np.column_stack((xx.ravel(), yy.ravel(), np.linspace(-.9, .9, xx.size)))
    # Mark four actual visible normal regions; individual camera role must
    # touch only vertices with its own outward normal.
    coords = np.tile(coords, (4, 1))
    normals = np.zeros_like(coords)
    group = coords.shape[0] // 4
    normals[:group, 2] = 1.
    normals[group:2*group, 2] = -1.
    normals[2*group:3*group, 0] = -1.
    normals[3*group:, 0] = 1.
    paths = {role: _reference(tmp_path / (role + ".png"))
             for role in ("front", "back", "left", "right")}
    refined, report = correct_observed_multiview_silhouettes(coords, normals, paths)
    assert refined.shape == coords.shape
    assert report["constraint"] == "observed_orthographic_rgba_multiview"
    assert report["camera_calibrated"] is False
    assert report["metric_depth_calibrated"] is False
    assert set(report["roles"]) == set(paths)
    assert any(item.get("modified_vertex_count", 0) for item in report["roles"].values())
    assert np.max(np.linalg.norm(refined - coords, axis=1)) <= .003 * 2 + 1e-9
    assert np.isfinite(refined).all()


def test_multiview_refuses_fabricated_role_and_missing_cutout(tmp_path):
    coordinates = np.zeros((20, 3))
    normals = np.ones_like(coordinates)
    with pytest.raises(ValueError, match="camera roles"):
        correct_observed_multiview_silhouettes(
            coordinates, normals, {"synthetic_novel_view": "image.png"})
    with pytest.raises(FileNotFoundError, match="cutout missing"):
        correct_observed_multiview_silhouettes(
            coordinates, normals, {"back": str(tmp_path / "missing.png")})
