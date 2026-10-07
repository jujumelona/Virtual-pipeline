"""Unit tests for current fail-closed template-fitting math."""

import numpy as np
import pytest

from vtuber_pipeline.avatar.template_fitting import (
    FittingObjective,
    coarse_similarity_transform,
    fit_template,
)


class TestFittingObjective:
    def test_default_lambda_values(self):
        objective = FittingObjective()
        assert objective.lambda_landmark == 1.0
        assert objective.lambda_surface == 0.5
        assert objective.lambda_laplacian == 0.1
        assert objective.lambda_symmetry == 0.2

    def test_compute_total(self):
        objective = FittingObjective()
        total = objective.compute_total(
            e_landmark=1.0,
            e_surface=0.5,
            e_laplacian=0.1,
            e_symmetry=0.2,
        )
        assert total == pytest.approx(1.30)


def test_fit_template_missing_template_is_error(tmp_path):
    result = fit_template(
        template_path=str(tmp_path / "missing-template.glb"),
        landmarks_2d=[[50.0, 50.0] for _ in range(28)],
        output_dir=str(tmp_path / "out"),
        reference_mesh_path=str(tmp_path / "missing-reference.obj"),
    )
    assert result["status"] == "error"
    assert result["objective_weights"]["lambda_surface"] == 0.5




def test_fit_template_custom_objective_options_are_applied(tmp_path):
    custom = {
        "lambda_landmark": 1.7,
        "lambda_surface": 0.6,
        "lambda_laplacian": 0.12,
        "lambda_symmetry": 0.25,
    }
    result = fit_template(
        template_path=str(tmp_path / "missing-template.glb"),
        landmarks_2d=[[50.0, 50.0] for _ in range(28)],
        output_dir=str(tmp_path / "out"),
        config={"fitting_objective": custom},
        reference_mesh_path=str(tmp_path / "missing-reference.obj"),
    )

    assert result["status"] == "error"
    assert result["objective_weights"] == custom


def test_fit_template_existing_template_requires_reference(tmp_path):
    import trimesh

    template = tmp_path / "template.glb"
    trimesh.creation.box(extents=[1.0, 2.0, 1.0]).export(template)

    result = fit_template(
        template_path=str(template),
        landmarks_2d=[[50.0, 50.0] for _ in range(28)],
        output_dir=str(tmp_path / "out"),
        reference_mesh_path=str(tmp_path / "missing-reference.obj"),
    )

    assert result["status"] == "error"
    assert "Reference mesh is required" in result["error"]


def test_coarse_similarity_uses_real_mesh_geometry(tmp_path):
    import trimesh

    source_path = tmp_path / "source.glb"
    target_path = tmp_path / "target.glb"

    source = trimesh.creation.box(extents=[1.0, 2.0, 1.0])
    source.export(source_path)

    target = source.copy()
    target.apply_scale(2.0)
    translation = np.array([3.0, -1.5, 0.75])
    target.apply_translation(translation)
    target.export(target_path)

    result = coarse_similarity_transform(
        str(source_path),
        str(target_path),
    )

    assert result["status"] == "complete", result
    assert result["scale"] == pytest.approx(2.0, rel=1e-5)
    assert np.asarray(result["translation"]) == pytest.approx(
        translation,
        rel=1e-5,
        abs=1e-5,
    )
    assert result["scale_basis"] == "head_xz"
