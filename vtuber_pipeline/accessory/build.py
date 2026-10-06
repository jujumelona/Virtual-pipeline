"""Accessory build orchestrator for VTuber Pipeline.

This module provides the AccessoryPipeline class for orchestrating the
complete accessory processing pipeline.
"""

import pathlib
from typing import Dict, Any, Optional, List


class AccessoryPipeline:
    """Orchestrates the accessory processing pipeline.
    
    Pipeline stages (in order):
    1. normalize - Normalize accessory GLB
    2. anchors - Generate anchor manifest
    3. fit - Fit accessory to anchor
    4. collision - Check and resolve collisions
    5. physics - Add physics configuration
    6. bake - Bake into base VRM
    """
    
    def __init__(self, output_dir: str, config: Optional[Dict[str, Any]] = None):
        """Initialize the accessory pipeline.
        
        Args:
            output_dir: Directory for output files.
            config: Optional configuration dictionary.
        """
        self.output_dir = pathlib.Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.config = config or {}
    
    def build(
        self,
        base_vrm: str,
        accessory_glb: str,
        output_dir: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Run the complete accessory build pipeline.
        
        Args:
            base_vrm: Path to the base VRM file.
            accessory_glb: Path to the accessory GLB file.
            output_dir: Optional output directory.
            config: Optional stage configuration.
            
        Returns:
            Summary dictionary with all stage results.
        """
        output_dir = output_dir or str(self.output_dir)
        config = config or self.config
        
        results = {
            "status": "running",
            "base_vrm": base_vrm,
            "accessory_glb": accessory_glb,
            "output_dir": output_dir,
            "stages": {}
        }
        
        # Import stage modules
        from vtuber_pipeline.accessory import normalize, anchors, fitting
        from vtuber_pipeline.accessory import collision, physics, bake
        
        # Stage 1: Normalize
        normalized_path = str(pathlib.Path(output_dir) / "normalized.glb")
        results["stages"]["normalize"] = normalize.normalize_glb(
            accessory_glb, normalized_path
        )
        
        # Stage 2: Anchors
        results["stages"]["anchors"] = anchors.generate_anchor_manifest(
            base_vrm, output_dir
        )
        
        # Stage 3: Fit
        anchor_name = config.get("anchor_name", "HEAD_TOP")
        anchor_manifest = results["stages"]["anchors"]
        results["stages"]["fit"] = fitting.fit_accessory(
            normalized_path, anchor_name, anchor_manifest, output_dir
        )
        
        # Stage 4: Collision
        fitted_path = results["stages"]["fit"].get("output_path", normalized_path)
        results["stages"]["collision"] = collision.check_collision(
            fitted_path, base_vrm
        )
        
        # Stage 5: Physics
        results["stages"]["physics"] = physics.add_physics_chain(
            fitted_path, output_dir, config.get("physics")
        )
        
        # Stage 6: Bake
        output_vrm = str(pathlib.Path(output_dir) / "combined.vrm")
        results["stages"]["bake"] = bake.bake_accessories(
            base_vrm, [fitted_path], output_vrm
        )
        
        # Overall status
        failed_stages = [
            name for name, result in results["stages"].items()
            if isinstance(result, dict) and result.get("status") == "error"
        ]
        
        if failed_stages:
            results["status"] = "failed"
            results["failed_stages"] = failed_stages
        else:
            results["status"] = "complete"
        
        return results
