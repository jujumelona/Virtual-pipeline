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
        from vtuber_pipeline.avatar.validator import validate_vrm
        
        # Stage 1: Normalize
        normalized_path = str(pathlib.Path(output_dir) / "normalized.glb")
        results["stages"]["normalize"] = normalize.normalize_glb(
            accessory_glb, normalized_path
        )
        if results["stages"]["normalize"].get("status") != "complete":
            results["status"] = "failed"
            results["failed_stages"] = ["normalize"]
            return results
        
        # Stage 2: Anchors
        results["stages"]["anchors"] = anchors.generate_anchor_manifest(
            base_vrm, output_dir
        )
        if results["stages"]["anchors"].get("status") != "complete":
            results["status"] = "failed"
            results["failed_stages"] = ["anchors"]
            return results
        
        # Stage 3: Fit
        anchor_name = config.get("anchor_name", "HEAD_TOP")
        anchor_manifest = results["stages"]["anchors"]
        results["stages"]["fit"] = fitting.fit_accessory(
            normalized_path, anchor_name, anchor_manifest, output_dir
        )
        
        # Stage 4: Collision against the avatar in world space.
        fitted_path = results["stages"]["fit"].get("output_path", normalized_path)
        fit_result = results["stages"]["fit"]
        if fit_result.get("status") != "complete":
            results["status"] = "failed"
            results["failed_stages"] = ["fit"]
            return results

        results["stages"]["collision"] = collision.resolve_collision(
            fitted_path,
            base_vrm,
            world_transform=fit_result.get("world_transform"),
        )
        collision_result = results["stages"]["collision"]
        if collision_result.get("status") != "complete":
            results["status"] = "failed"
            results["failed_stages"] = ["collision"]
            return results

        # Fold one push-out step into the bone-relative attachment translation.
        local_transform = dict(fit_result.get("transform", {}))
        if collision_result.get("resolved"):
            import numpy as np

            world_push = np.asarray(
                collision_result.get("pushout_vector", [0.0, 0.0, 0.0]),
                dtype=float,
            )
            world_to_local = fit_result.get("world_to_local_linear")
            if world_to_local is None:
                results["status"] = "failed"
                results["failed_stages"] = ["collision"]
                results["failed_reason"] = (
                    "collision push-out exists but anchor world-to-local transform is missing"
                )
                return results

            local_push = np.asarray(world_to_local, dtype=float) @ world_push
            base_translation = np.asarray(
                local_transform.get("translation", [0.0, 0.0, 0.0]),
                dtype=float,
            )
            local_transform["translation"] = (
                base_translation + local_push
            ).astype(float).tolist()
        
        # Stage 5: Physics
        results["stages"]["physics"] = physics.add_physics_chain(
            fitted_path, output_dir, config.get("physics")
        )
        
        # Stage 6: Bake
        output_vrm = str(pathlib.Path(output_dir) / "combined.vrm")
        attachment_cfg = {
            pathlib.Path(fitted_path).stem: {
                **local_transform,
                "parent_bone": fit_result.get("parent_bone", "head"),
            }
        }
        results["stages"]["bake"] = bake.bake_accessories(
            base_vrm,
            [fitted_path],
            output_vrm,
            attachment_config=attachment_cfg,
        )
        if results["stages"]["bake"].get("status") != "complete":
            results["status"] = "failed"
            results["failed_stages"] = ["bake"]
            return results
        if not pathlib.Path(output_vrm).is_file():
            results["status"] = "failed"
            results["failed_stages"] = ["bake"]
            results["failed_reason"] = "bake reported complete but combined.vrm is missing"
            return results

        # Re-import the merged file and apply the same strict product contract
        # used by Avatar Mode. This catches broken index/buffer remaps.
        results["stages"]["validator"] = validate_vrm(
            output_vrm,
            output_dir,
            product_contract=False,
        )
        if (
            results["stages"]["validator"].get("status") != "complete"
            or not results["stages"]["validator"].get("passed")
        ):
            results["status"] = "failed"
            results["failed_stages"] = ["validator"]
            results["failed_reason"] = (
                results["stages"]["validator"].get("error")
                or "strict validation failed after accessory bake"
            )
            return results
        
        # Overall status
        failed_stages = [
            name for name, result in results["stages"].items()
            if isinstance(result, dict) and result.get("status") == "error"
        ]
        incomplete_stages = [
            name for name, result in results["stages"].items()
            if isinstance(result, dict) and result.get("status") in {"stub", "partial"}
        ]
        
        if failed_stages:
            results["status"] = "failed"
            results["failed_stages"] = failed_stages
        elif incomplete_stages:
            results["status"] = "partial"
            results["incomplete_stages"] = incomplete_stages
        else:
            results["status"] = "complete"
            results["output_vrm"] = output_vrm
        
        return results
