"""Unit tests for input gate validation."""

import pytest
import tempfile
import pathlib
from PIL import Image


def create_test_image(width: int, height: int, path: pathlib.Path) -> None:
    """Create a test image with given dimensions."""
    img = Image.new('RGB', (width, height), color='white')
    img.save(path)


class TestValidateInput:
    """Tests for validate_input function."""
    
    def test_valid_256x256_image(self, tmp_path):
        """Test validation with a valid 256x256 image."""
        from vtuber_pipeline.avatar.input_gate import validate_input
        
        # Create test image
        image_path = tmp_path / "test.png"
        create_test_image(256, 256, image_path)
        
        # Run validation
        result = validate_input(str(image_path), str(tmp_path))
        
        # Check image was decoded
        assert result["checks"]["image_decodes"] == True
        assert result["width"] == 256
        assert result["height"] == 256
        
        # Check minimum resolution
        assert result["checks"]["min_resolution"] == True
        
        # Check aspect ratio
        assert result["checks"]["aspect_ratio"] == True
    
    def test_too_small_image(self, tmp_path):
        """Test validation rejects images below minimum resolution."""
        from vtuber_pipeline.avatar.input_gate import validate_input
        
        # Create test image below minimum
        image_path = tmp_path / "small.png"
        create_test_image(128, 128, image_path)
        
        # Run validation
        result = validate_input(str(image_path), str(tmp_path))
        
        # Check resolution check fails
        assert result["checks"]["min_resolution"] == False
        assert result["valid"] == False
    
    def test_wide_aspect_ratio(self, tmp_path):
        """Test validation with wide aspect ratio."""
        from vtuber_pipeline.avatar.input_gate import validate_input
        
        # Create wide image
        image_path = tmp_path / "wide.png"
        create_test_image(500, 250, image_path)
        
        # Run validation
        result = validate_input(str(image_path), str(tmp_path))
        
        # Check aspect ratio is within range
        assert result["aspect_ratio"] == 2.0
        assert result["checks"]["aspect_ratio"] == True
    
    def test_invalid_aspect_ratio(self, tmp_path):
        """Test validation rejects extreme aspect ratios."""
        from vtuber_pipeline.avatar.input_gate import validate_input
        
        # Create very wide image
        image_path = tmp_path / "wide.png"
        create_test_image(600, 200, image_path)
        
        # Run validation
        result = validate_input(str(image_path), str(tmp_path))
        
        # Check aspect ratio check fails
        assert result["aspect_ratio"] == 3.0
        assert result["checks"]["aspect_ratio"] == False
    
    def test_quality_json_written(self, tmp_path):
        """Test that quality.json is written."""
        from vtuber_pipeline.avatar.input_gate import validate_input
        
        # Create test image
        image_path = tmp_path / "test.png"
        create_test_image(256, 256, image_path)
        
        # Run validation
        validate_input(str(image_path), str(tmp_path))
        
        # Check quality.json was created
        quality_path = tmp_path / "quality.json"
        assert quality_path.exists()
    
    def test_input_hash_computed(self, tmp_path):
        """Test that input hash is computed."""
        from vtuber_pipeline.avatar.input_gate import validate_input
        
        # Create test image
        image_path = tmp_path / "test.png"
        create_test_image(256, 256, image_path)
        
        # Run validation
        result = validate_input(str(image_path), str(tmp_path))
        
        # Check hash was computed
        assert "input_hash" in result
        assert len(result["input_hash"]) == 64  # SHA256 hex string
