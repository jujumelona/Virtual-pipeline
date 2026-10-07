"""Unit tests for SpringBone configuration.

Tests for VRMC_springBone 1.0 schema compliance:
- Uses 'joints' array (not 'jointEdges')
- Uses 'stiffness' (not 'stiffiness')
- Each joint has required fields: stiffness, gravityDir, dragForce
"""

import pytest
from vtuber_pipeline.avatar.springbone import (
    generate_springbone_config,
    classify_springbone_chains,
    apply_springbone_preset,
    SPRING_BONE_PRESETS
)


class TestSpringBonePresets:
    """Tests for SpringBone presets."""
    
    def test_preset_has_stiffness_not_stiffiness(self):
        """Verify all presets use 'stiffness' not 'stiffiness'."""
        for bone_class, preset in SPRING_BONE_PRESETS.items():
            assert "stiffness" in preset, f"Preset '{bone_class}' missing 'stiffness'"
            assert "stiffiness" not in preset, f"Preset '{bone_class}' has typo 'stiffiness'"
    
    def test_preset_has_required_fields(self):
        """Verify all presets have required fields."""
        required_fields = ["stiffness", "gravity", "drag", "hit_radius"]
        for bone_class, preset in SPRING_BONE_PRESETS.items():
            for field in required_fields:
                assert field in preset, f"Preset '{bone_class}' missing '{field}'"


class TestGenerateSpringboneConfig:
    """Tests for generate_springbone_config function."""
    
    def test_springbone_extension_schema(self, tmp_path):
        """Test that generated config follows VRMC_springBone 1.0 schema."""
        result = generate_springbone_config(
            mesh_path="test.glb",
            output_dir=str(tmp_path)
        )
        
        # Check top-level structure
        assert result["status"] == "complete"
        assert "springs" in result
        assert "specVersion" in result
        assert result["specVersion"] == "1.0"
    
    def test_springs_have_joints_not_joint_edges(self, tmp_path):
        """Test that springs use 'joints' array, not 'jointEdges'."""
        result = generate_springbone_config(
            mesh_path="test.glb",
            output_dir=str(tmp_path)
        )
        
        # Each spring must have 'joints', not 'jointEdges'
        for spring in result["springs"]:
            assert "joints" in spring, f"Spring '{spring.get('name')}' missing 'joints'"
            assert "jointEdges" not in spring, f"Spring '{spring.get('name')}' has deprecated 'jointEdges'"
    
    def test_joint_has_correct_fields(self, tmp_path):
        """Test that joints have all required VRMC_springBone 1.0 fields."""
        result = generate_springbone_config(
            mesh_path="test.glb",
            output_dir=str(tmp_path)
        )
        
        # If there are any joints, verify their structure
        for spring in result["springs"]:
            for joint in spring.get("joints", []):
                # Must have 'stiffness' (not 'stiffiness')
                assert "stiffness" in joint, f"Joint missing 'stiffness'"
                assert "stiffiness" not in joint, f"Joint has typo 'stiffiness'"
                
                # Must have 'gravityDir'
                assert "gravityDir" in joint, f"Joint missing 'gravityDir'"
                
                # Must have 'dragForce'
                assert "dragForce" in joint, f"Joint missing 'dragForce'"
    
    def test_config_written_to_file(self, tmp_path):
        """Test that config is written to springbone.json."""
        import json
        from pathlib import Path
        
        result = generate_springbone_config(
            mesh_path="test.glb",
            output_dir=str(tmp_path)
        )
        
        springbone_file = Path(tmp_path) / "springbone.json"
        assert springbone_file.exists(), "springbone.json not created"
        
        with open(springbone_file) as f:
            loaded = json.load(f)
        
        assert loaded["status"] == "complete"
        assert "springs" in loaded


class TestClassifySpringboneChains:
    """Tests for classify_springbone_chains function."""
    
    def test_returns_list(self):
        """Test that function returns a list."""
        result = classify_springbone_chains(
            mesh_path="test.glb",
            skeleton={}
        )
        assert isinstance(result, list)
    
    def test_chain_structure(self):
        """Test that returned chains have correct structure."""
        result = classify_springbone_chains(
            mesh_path="test.glb",
            skeleton={}
        )
        
        for chain in result:
            assert "name" in chain, "Chain missing 'name'"
            assert "joints" in chain, "Chain missing 'joints'"
            assert isinstance(chain["joints"], list), "'joints' must be a list"


class TestApplySpringbonePreset:
    """Tests for apply_springbone_preset function."""
    
    def test_default_preset(self):
        """Test applying default preset."""
        preset = apply_springbone_preset("hair")
        assert preset["stiffness"] == 0.5
        assert preset["gravity"] == 0.1
    
    def test_custom_preset_merge(self):
        """Test merging custom preset."""
        preset = apply_springbone_preset("hair", {"stiffness": 0.8})
        assert preset["stiffness"] == 0.8  # Custom value
        assert preset["gravity"] == 0.1  # Original value preserved
    
    def test_unknown_class_uses_hair_default(self):
        """Test unknown class falls back to hair preset."""
        preset = apply_springbone_preset("unknown_class")
        assert preset["stiffness"] == 0.5  # Hair preset default
