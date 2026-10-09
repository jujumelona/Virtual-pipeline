"""Actual input alpha supplies the silhouette term without fictional pose data."""
import numpy as np
from PIL import Image, ImageDraw
import pytest

from vtuber_pipeline.avatar.observed_silhouette_constraint import (
    correct_observed_front_silhouette,
)


def test_front_alpha_constrains_canonical_xy_but_not_depth(tmp_path):
    photo = Image.new("RGBA", (64, 128), (100, 80, 80, 0))
    draw = ImageDraw.Draw(photo)
    # A silhouette that is narrower at the waist than at the shoulders.
    draw.polygon([(14, 10), (50, 10), (50, 37), (34, 54),
                  (34, 85), (50, 110), (50, 121), (14, 121),
                  (14, 110), (29, 85), (29, 54), (14, 37)],
                 fill=(190, 100, 95, 255))
    observed = tmp_path / "alpha.png"
    photo.save(observed)
    x = np.linspace(-1, 1, 20)
    y = np.linspace(0, 2, 26)
    xx, yy = np.meshgrid(x, y)
    vertices = np.column_stack((xx.ravel(), yy.ravel(),
                                np.zeros(xx.size)))
    normals = np.tile([0., 0., 1.], (len(vertices), 1))
    corrected, report = correct_observed_front_silhouette(
        vertices, normals, str(observed))
    assert report["silhouette_constraint"] == "observed_alpha_bounded_step"
    assert report["outside_vertices"] > 0
    assert report["modified_vertex_count"] > 0
    assert np.array_equal(vertices[:, 2], corrected[:, 2])
    assert np.max(np.linalg.norm(corrected[:, :2] - vertices[:, :2], axis=1)) <= .003 * 2 + 1e-12


def test_opaque_photo_never_invents_foreground_mask(tmp_path):
    image = tmp_path / "opaque.png"
    Image.new("RGBA", (64, 64), (255, 120, 99, 255)).save(image)
    vertices = np.array([[a, b, 0.] for a in range(8) for b in range(8)])
    normals = np.tile([0., 0., 1.], (len(vertices), 1))
    result, report = correct_observed_front_silhouette(vertices, normals, str(image))
    assert report["silhouette_constraint"] == "skipped"
    assert np.array_equal(result, vertices)


def test_silhouette_rejects_nonfinite_geometry(tmp_path):
    with pytest.raises(ValueError, match="finite matching"):
        correct_observed_front_silhouette(
            np.array([[np.nan, 0., 0.]]),
            np.array([[0., 0., 1.]]),
            None,
        )
