"""Unit tests for pipeline stage contracts."""

import pytest
from vtuber_pipeline.core.contracts import (
    ImageContract,
    FaceLandmarksContract,
    ReferenceContract,
    FittingContract,
    RigContract,
    ExpressionContract,
    VRMContract,
    AttachmentContract,
)


class TestImageContract:
    """Tests for ImageContract."""
    
    def test_instantiation(self):
        """Test creating an ImageContract instance."""
        contract = ImageContract(
            input_hash="abc123",
            output_path="/output/image.json",
            stage_name="test_stage"
        )
        
        assert contract.input_hash == "abc123"
        assert contract.output_path == "/output/image.json"
        assert contract.stage_name == "test_stage"
        assert contract.status == "pending"
    
    def test_default_status(self):
        """Test default status is pending."""
        contract = ImageContract(
            input_hash="test",
            output_path="/output/test.json"
        )
        
        assert contract.status == "pending"
    
    def test_status_values(self):
        """Test all status values can be set."""
        for status in ['pending', 'running', 'complete', 'failed']:
            contract = ImageContract(
                input_hash="test",
                output_path="/output/test.json",
                status=status
            )
            assert contract.status == status


class TestFaceLandmarksContract:
    """Tests for FaceLandmarksContract."""
    
    def test_instantiation(self):
        """Test creating a FaceLandmarksContract instance."""
        contract = FaceLandmarksContract(
            input_hash="abc123",
            output_path="/output/landmarks.json",
            bbox=[0, 0, 100, 100],
            landmarks=[[50, 50]],
            score=0.95
        )
        
        assert contract.input_hash == "abc123"
        assert contract.bbox == [0, 0, 100, 100]
        assert contract.score == 0.95


class TestReferenceContract:
    """Tests for ReferenceContract."""
    
    def test_instantiation(self):
        """Test creating a ReferenceContract instance."""
        contract = ReferenceContract(
            input_hash="abc123",
            output_path="/output/reference.glb",
            mesh_path="/output/mesh.glb",
            texture_path="/output/texture.png"
        )
        
        assert contract.mesh_path == "/output/mesh.glb"
        assert contract.texture_path == "/output/texture.png"


class TestFittingContract:
    """Tests for FittingContract."""
    
    def test_instantiation(self):
        """Test creating a FittingContract instance."""
        contract = FittingContract(
            input_hash="abc123",
            output_path="/output/fitted.glb",
            fit_mesh_path="/output/fit.glb",
            deformation_graph_path="/output/fit.npz"
        )
        
        assert contract.fit_mesh_path == "/output/fit.glb"
        assert contract.deformation_graph_path == "/output/fit.npz"


class TestRigContract:
    """Tests for RigContract."""
    
    def test_instantiation(self):
        """Test creating a RigContract instance."""
        contract = RigContract(
            input_hash="abc123",
            output_path="/output/rigged.glb",
            bone_count=22,
            springbone_count=5
        )
        
        assert contract.bone_count == 22
        assert contract.springbone_count == 5


class TestExpressionContract:
    """Tests for ExpressionContract."""
    
    def test_instantiation(self):
        """Test creating an ExpressionContract instance."""
        contract = ExpressionContract(
            input_hash="abc123",
            output_path="/output/expressions.json",
            expression_count=13,
            expressions={"blink": {}}
        )
        
        assert contract.expression_count == 13
        assert "blink" in contract.expressions


class TestVRMContract:
    """Tests for VRMContract."""
    
    def test_instantiation(self):
        """Test creating a VRMContract instance."""
        contract = VRMContract(
            input_hash="abc123",
            output_path="/output/avatar.vrm",
            vrm_path="/output/avatar.vrm",
            validation_report_path="/output/validation/report.json"
        )
        
        assert contract.vrm_path == "/output/avatar.vrm"
        assert contract.validation_report_path == "/output/validation/report.json"


class TestAttachmentContract:
    """Tests for AttachmentContract."""
    
    def test_instantiation(self):
        """Test creating an AttachmentContract instance."""
        contract = AttachmentContract(
            input_hash="abc123",
            output_path="/output/attachments.json",
            accessory_meshes=["/output/hat.glb"],
            attachment_config_path="/output/attachment_config.json"
        )
        
        assert len(contract.accessory_meshes) == 1
        assert contract.attachment_config_path == "/output/attachment_config.json"
