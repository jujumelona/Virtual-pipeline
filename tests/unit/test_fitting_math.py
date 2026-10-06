"""Unit tests for template fitting math."""

import pytest
from vtuber_pipeline.avatar.template_fitting import FittingObjective, fit_template


class TestFittingObjective:
    """Tests for FittingObjective dataclass."""
    
    def test_default_lambda_values(self):
        """Test default lambda values."""
        objective = FittingObjective()
        
        assert objective.lambda_landmark == 1.0
        assert objective.lambda_surface == 0.5
        assert objective.lambda_laplacian == 0.1
        assert objective.lambda_symmetry == 0.2
    
    def test_custom_lambda_values(self):
        """Test custom lambda values."""
        objective = FittingObjective(
            lambda_landmark=2.0,
            lambda_surface=1.0,
            lambda_laplacian=0.2,
            lambda_symmetry=0.4
        )
        
        assert objective.lambda_landmark == 2.0
        assert objective.lambda_surface == 1.0
        assert objective.lambda_laplacian == 0.2
        assert objective.lambda_symmetry == 0.4
    
    def test_compute_total(self):
        """Test total energy computation."""
        objective = FittingObjective()
        
        total = objective.compute_total(
            e_landmark=1.0,
            e_surface=0.5,
            e_laplacian=0.1,
            e_symmetry=0.2
        )
        
        # E = 1.0*1.0 + 0.5*0.5 + 0.1*0.1 + 0.2*0.2 = 1.0 + 0.25 + 0.01 + 0.04 = 1.30
        assert total == pytest.approx(1.30)
    
    def test_zero_energies(self):
        """Test with zero energies."""
        objective = FittingObjective()
        
        total = objective.compute_total(0.0, 0.0, 0.0, 0.0)
        assert total == 0.0


class TestFitTemplate:
    """Tests for fit_template function."""
    
    def test_fit_template_returns_dict(self, tmp_path):
        """Test fit_template returns a dictionary."""
        result = fit_template(
            template_path="template.glb",
            landmarks_2d=[[50, 50]],
            output_dir=str(tmp_path)
        )
        
        assert isinstance(result, dict)
    
    def test_fit_template_status(self, tmp_path):
        """Test fit_template returns status."""
        result = fit_template(
            template_path="template.glb",
            landmarks_2d=[[50, 50]],
            output_dir=str(tmp_path)
        )
        
        assert "status" in result
    
    def test_fit_template_objective_weights(self, tmp_path):
        """Test fit_template includes objective weights."""
        result = fit_template(
            template_path="template.glb",
            landmarks_2d=[[50, 50]],
            output_dir=str(tmp_path)
        )
        
        assert "objective_weights" in result
        weights = result["objective_weights"]
        assert "lambda_landmark" in weights
        assert "lambda_surface" in weights
    
    def test_fit_template_custom_config(self, tmp_path):
        """Test fit_template with custom config."""
        config = {
            "fitting_objective": {
                "lambda_landmark": 2.0,
                "lambda_surface": 1.0
            }
        }
        
        result = fit_template(
            template_path="template.glb",
            landmarks_2d=[[50, 50]],
            output_dir=str(tmp_path),
            config=config
        )
        
        assert result["objective_weights"]["lambda_landmark"] == 2.0
        assert result["objective_weights"]["lambda_surface"] == 1.0
