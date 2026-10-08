"""Observed nonmetric depths influence only bounded front-surface Z positions."""
import numpy as np
import pytest

from vtuber_pipeline.avatar.relative_depth_constraint import correct_relative_front_depth


def _inputs(tmp_path):
    x = np.linspace(-.8, .8, 25)
    xx, yy = np.meshgrid(x, x)
    verts = np.column_stack((
        xx.ravel(), yy.ravel(),
        (.4 * (1 - xx * xx - yy * yy) + .025 * xx).ravel(),
    ))
    normals = np.zeros_like(verts)
    normals[:, 2] = 1.
    h, w = 128, 128
    u, v = np.meshgrid(np.arange(w), np.arange(h))
    depth = np.exp(-((u-64.)**2 + (v-64.)**2) / (2 * 31.**2))
    depth_path = tmp_path / "depth_front.npy"
    np.save(depth_path, depth.astype(np.float32))
    source = tmp_path / "original-front.png"
    source.write_bytes(b"observed-source-provenance")
    constraints = {
        "registration": {"confidence": .8},
        "observed_views": {"front": {
            "observed_view": True, "relative_depth_only": True,
            "source_image": str(source), "depth_npy": str(depth_path),
        }},
    }
    reference = {"images": {"front": {
        "path": str(source), "size": [w, h],
        "alpha_foreground_bbox": [12, 12, 116, 116],
    }}}
    return verts, normals, constraints, reference


def test_original_image_depth_changes_3d_shape_without_metric_fabrication(tmp_path):
    vertices, normals, constraints, references = _inputs(tmp_path)
    result, evidence = correct_relative_front_depth(vertices, normals,
                                                     constraints, references)
    assert evidence["relative_depth_constraint"] == "bounded_gradient_step"
    assert evidence["relative_depth_metric_calibrated"] is False
    assert evidence["front_camera_calibrated"] is False
    assert evidence["modified_vertex_count"] > 0
    assert np.array_equal(result[:, :2], vertices[:, :2])
    delta = result[:, 2] - vertices[:, 2]
    assert np.max(np.abs(delta)) > 0
    assert np.max(np.abs(delta)) <= .002 * np.ptp(vertices[:, 1]) + 1e-10


def test_missing_observed_silhouette_does_not_invent_depth(tmp_path):
    vertices, normals, constraints, references = _inputs(tmp_path)
    references["images"]["front"]["alpha_foreground_bbox"] = None
    result, evidence = correct_relative_front_depth(vertices, normals,
                                                     constraints, references)
    assert np.array_equal(result, vertices)
    assert evidence["relative_depth_constraint"] == "skipped"


def test_wrong_camera_provenance_and_synthetic_depth_fail_closed(tmp_path):
    vertices, normals, constraints, references = _inputs(tmp_path)
    constraints["observed_views"]["front"]["source_image"] = "different-image.png"
    with pytest.raises(ValueError, match="do not match"):
        correct_relative_front_depth(vertices, normals, constraints, references)
    constraints["observed_views"]["front"]["source_image"] = references["images"]["front"]["path"]
    constraints["observed_views"]["front"]["observed_view"] = False
    with pytest.raises(ValueError, match="Synthetic or metric"):
        correct_relative_front_depth(vertices, normals, constraints, references)
