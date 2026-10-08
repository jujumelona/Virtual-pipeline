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



def test_7d_rigid_fit_abnormal_optimizer_preserves_verified_coarse_mesh(
    tmp_path, monkeypatch,
):
    """Reported Colab ABNORMAL must not discard a valid finite fit.

    Real trimesh + scipy KDTree and sparse deformation solve are executed.
    Only the optimization exit record is injected to reproduce the exact
    L-BFGS-B false negative observed with a changing nearest-neighbor loss.
    """
    import types
    import trimesh
    import scipy.optimize

    template = trimesh.creation.icosphere(subdivisions=2, radius=1)
    source_path = tmp_path / "canonical.glb"
    template.export(source_path)

    ref = template.copy()
    ref.apply_scale(1.35)
    ref.apply_translation([0.35, -0.22, 0.16])
    ref_path = tmp_path / "reference.obj"
    ref.export(ref_path)

    observations = []

    def abnormal(energy, x0, *, method, bounds, options):
        assert method == "Powell", "nonsmooth objective must be gradient-free"
        assert all(lo < hi for lo, hi in bounds)
        baseline = float(energy(np.asarray(x0, dtype=float)))
        assert np.isfinite(baseline)
        observations.append(baseline)
        return types.SimpleNamespace(
            x=np.asarray(x0, dtype=float),
            success=False,
            nit=7,
            status=2,
            fun=baseline,
            message="ABNORMAL: ",
        )

    monkeypatch.setattr(scipy.optimize, "minimize", abnormal)
    points = [
        [500.0 + 50.0 * np.cos(2*np.pi*i/28),
         300.0 + 65.0 * np.sin(2*np.pi*i/28)]
        for i in range(28)
    ]
    result = fit_template(
        str(source_path), points, str(tmp_path / "fitted"),
        reference_mesh_path=str(ref_path),
    )
    assert result["status"] == "complete", result
    assert result["rigid_solver"] == "bounded_powell"
    assert result["rigid_solver_success"] is False
    assert result["converged"] is False
    assert result["sparse_solve_success"] is True
    assert np.isfinite(result["objective_value"])
    assert result["rigid_selected_energy"] <= result["rigid_initial_energy"] + 1e-10
    assert observations
    assert (tmp_path / "fitted" / "fitted.glb").is_file()
    saved = trimesh.load(result["fitted_mesh"], force="mesh")
    assert len(saved.vertices) == len(template.vertices)
    assert np.isfinite(saved.vertices).all()


def test_rigid_fit_rejects_nonfinite_initial_reference_data(tmp_path):
    """A genuine geometry error must still fail closed, not pretend to fit."""
    import trimesh

    template = trimesh.creation.icosphere(subdivisions=1)
    source_path = tmp_path / "canonical.glb"
    template.export(source_path)
    result = fit_template(
        str(source_path),
        [[500 + i, 300 + i * 2] for i in range(28)],
        str(tmp_path / "output"),
        reference_mesh_path=str(tmp_path / "missing.obj"),
    )
    assert result["status"] == "error"
    assert result["error"]
