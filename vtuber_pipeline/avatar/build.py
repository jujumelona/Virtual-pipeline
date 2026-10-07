"""Avatar build orchestrator for VTuber Pipeline.

This module provides the AvatarPipeline class for orchestrating the
complete avatar creation pipeline from input image to VRM output.
"""

import pathlib
from typing import Dict, Any, Optional, List


class AvatarPipeline:
    """Orchestrates the complete avatar creation pipeline.
    
    Pipeline stages (in order):
    1. input_gate - Validate image and detect face
    2. face_landmarks - Extract facial landmarks (stub)
    3. reference_reconstruction - Reconstruct 3D mesh with TripoSR (stub)
    4. reference_analysis - Analyze reconstructed mesh
    5. template_fitting - Fit canonical template to mesh
    6. deformation_transfer - Transfer expressions to fitted mesh
    7. texture_transfer - Generate textures
    8. hair - Extract hair mesh
    9. clothing - Extract clothing mesh
    10. rig - Create humanoid rig (stub)
    11. expressions - Generate expression shape keys
    12. gaze - Configure eye look-at
    13. springbone - Configure SpringBone physics
    14. materials - Configure MToon materials
    15. vrm_export - Export to VRM format
    16. validator - Validate output VRM
    
    Each stage checks the manifest for cache hits before executing.
    """
    
    def __init__(self, output_dir: str, config: Optional[Dict[str, Any]] = None):
        """Initialize the avatar pipeline.
        
        Args:
            output_dir: Directory for all output files.
            config: Optional configuration dictionary.
        """
        self.output_dir = pathlib.Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.config = config or {}
        
        # Initialize manifest
        from vtuber_pipeline.core.manifest import PipelineManifest
        self.manifest = PipelineManifest(output_dir)
    
    def build(self, image_path: str, output_dir: Optional[str] = None, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Run the complete avatar build pipeline.
        
        Args:
            image_path: Path to the input image.
            output_dir: Optional output directory (uses self.output_dir if None).
            config: Optional stage configuration.
            
        Returns:
            Summary dictionary with all stage results.
        """
        output_dir = output_dir or str(self.output_dir)
        config = config or self.config
        
        results = {
            "status": "running",
            "image_path": image_path,
            "output_dir": output_dir,
            "stages": {}
        }
        
        # Import stage modules
        from vtuber_pipeline.avatar import input_gate, reference_analysis, template_fitting
        from vtuber_pipeline.avatar import deformation_transfer, texture_transfer, hair, clothing
        from vtuber_pipeline.avatar import expressions, gaze, springbone, materials, vrm_export, validator
        from vtuber_pipeline.avatar.template_mesh import get_template_path
        
        # Stage 1: Input gate
        stage_key = self._get_stage_key("input_gate", image_path)
        if not self.manifest.is_complete(stage_key):
            results["stages"]["input_gate"] = input_gate.validate_input(image_path, output_dir)
            self.manifest.record_stage(stage_key, results["stages"]["input_gate"])
        else:
            results["stages"]["input_gate"] = {"status": "cached", "stage_key": stage_key}
        
        # Stage 2: Face landmarks - call real AnimeFaceDetector
        stage_key = self._get_stage_key("face_landmarks", image_path)
        if not self.manifest.is_complete(stage_key):
            try:
                from vtuber_pipeline.avatar.face_detector import AnimeFaceDetector
                detector = AnimeFaceDetector()
                landmarks_result = detector.detect(image_path)
                results["stages"]["face_landmarks"] = {
                    "status": "complete",
                    "landmarks": landmarks_result.get("landmarks", []),
                    "bbox": landmarks_result.get("bbox", []),
                    "score": landmarks_result.get("score", 0.0)
                }
            except ImportError as e:
                results["stages"]["face_landmarks"] = {
                    "status": "error",
                    "error": f"Face detector not available: {e}",
                    "landmarks": []
                }
            except ValueError as e:
                results["stages"]["face_landmarks"] = {
                    "status": "error",
                    "error": str(e),
                    "landmarks": []
                }
            except Exception as e:
                results["stages"]["face_landmarks"] = {
                    "status": "error",
                    "error": str(e),
                    "landmarks": []
                }
            self.manifest.record_stage(stage_key, results["stages"]["face_landmarks"])
        
        # Stage 3: Reference reconstruction - try TripoSR first, fall back to canonical template
        import logging
        logger = logging.getLogger(__name__)
        stage_key = self._get_stage_key("reference_reconstruction", image_path)
        
        # Check for commercial/production profile
        is_production = config.get("profile") in ["commercial", "production"]
        
        if not self.manifest.is_complete(stage_key):
            try:
                from vtuber_pipeline.avatar.reconstruction import reconstruct_avatar
                reference_mesh = reconstruct_avatar(image_path, str(pathlib.Path(output_dir) / "reconstruction"), profile="commercial")
                results["stages"]["reference_reconstruction"] = {
                    "status": "complete",
                    "mesh_path": reference_mesh,
                    "output_path": reference_mesh,  # For manifest caching
                    "source": "triposr"
                }
            except Exception as e:
                logger.warning(f"TripoSR failed: {e}")
                
                # For commercial/production profile, fail instead of fallback
                if is_production:
                    results["stages"]["reference_reconstruction"] = {
                        "status": "error",
                        "error": f"TripoSR failed in production profile (no fallback allowed): {e}",
                        "source": "triposr"
                    }
                    results["status"] = "failed"
                    results["failed_stages"] = ["reference_reconstruction"]
                    self.manifest.record_stage(stage_key, results["stages"]["reference_reconstruction"])
                    return results
                
                # For non-production profiles, allow fallback to canonical template
                template_path = pathlib.Path(__file__).parent.parent.parent / "assets" / "canonical_vtuber" / "template.glb"
                results["stages"]["reference_reconstruction"] = {
                    "status": "fallback",
                    "mesh_path": str(template_path),
                    "output_path": str(template_path),  # For manifest caching
                    "source": "canonical_template",
                    "error": str(e)
                }
            self.manifest.record_stage(stage_key, results["stages"]["reference_reconstruction"])
        else:
            # Retrieve cached result from manifest
            cached_stage = self.manifest.get_stage(stage_key)
            if cached_stage and cached_stage.get("output_path"):
                cached_mesh_path = cached_stage["output_path"]
                # Determine source from cached status
                cached_status = cached_stage.get("status", "complete")
                results["stages"]["reference_reconstruction"] = {
                    "status": "cached",
                    "mesh_path": cached_mesh_path,
                    "source": "cached_tripsr" if cached_status == "complete" else "cached_fallback",
                    "stage_key": stage_key
                }
            else:
                # A cache entry without its artifact is invalid. Never substitute a
                # canonical template for a missing TripoSR result.
                results["stages"]["reference_reconstruction"] = {
                    "status": "error",
                    "error": "Cached reconstruction is missing output_path/artifact",
                    "stage_key": stage_key
                }
                results["status"] = "failed"
                results["failed_stages"] = ["reference_reconstruction"]
                return results
        
        # Stage 4: Reference analysis
        ref_mesh = results["stages"]["reference_reconstruction"].get("mesh_path", "")
        stage_key = self._get_stage_key("reference_analysis", ref_mesh)
        if not self.manifest.is_complete(stage_key):
            results["stages"]["reference_analysis"] = reference_analysis.analyze_reference(ref_mesh, output_dir)
            self.manifest.record_stage(stage_key, results["stages"]["reference_analysis"])
        
        # Stage 5: Template fitting - use real fit_template() with reference mesh
        landmarks = results["stages"]["face_landmarks"].get("landmarks", [])
        ref_mesh_path = results["stages"]["reference_reconstruction"].get("mesh_path", "")
        stage_key = self._get_stage_key("template_fitting", ref_mesh_path)
        if not self.manifest.is_complete(stage_key):
            # Resolve one canonical template path. get_template_path() creates the
            # MakeHuman-CC0-derived template in a writable cache when necessary.
            try:
                template_path = get_template_path()
                results["stages"]["template_fitting"] = template_fitting.fit_template(
                    str(template_path), landmarks, output_dir, config.get("fitting"),
                    reference_mesh_path=ref_mesh_path
                )
            except Exception as e:
                results["stages"]["template_fitting"] = {
                    "status": "error",
                    "error": f"Canonical template unavailable: {e}"
                }
            self.manifest.record_stage(stage_key, results["stages"]["template_fitting"])
        
        # CRITICAL FIX: Extract fitted_mesh from fitting result and use it for all downstream stages
        # Previously, downstream stages incorrectly used ref_mesh instead of fitted_mesh
        fitting_result = results["stages"]["template_fitting"]
        if fitting_result.get("status") != "complete":
            results["status"] = "failed"
            results["failed_stages"] = ["template_fitting"]
            return results
        fitted_mesh = fitting_result.get("fitted_mesh")
        fit_npz = fitting_result.get("fit_npz", str(pathlib.Path(output_dir) / "fit.npz"))
        
        # Validate fitted_mesh exists
        if fitted_mesh and pathlib.Path(fitted_mesh).exists():
            results["fitted_mesh"] = fitted_mesh
        else:
            results["status"] = "failed"
            results["failed_stages"] = ["template_fitting"]
            results["failed_reason"] = "template_fitting reported complete but fitted_mesh is missing"
            return results
        
        # Stage 6: Deformation transfer - use fitted_mesh
        stage_key = self._get_stage_key("deformation_transfer", fit_npz)
        if not self.manifest.is_complete(stage_key):
            template_path = get_template_path()
            results["stages"]["deformation_transfer"] = deformation_transfer.transfer_deformation(
                str(template_path), fitted_mesh, fit_npz, output_dir
            )
            self.manifest.record_stage(stage_key, results["stages"]["deformation_transfer"])
        
        # Stage 7: Texture transfer - use fitted_mesh
        stage_key = self._get_stage_key("texture_transfer", image_path)
        if not self.manifest.is_complete(stage_key):
            results["stages"]["texture_transfer"] = texture_transfer.transfer_texture(
                image_path, fitted_mesh, output_dir
            )
            self.manifest.record_stage(stage_key, results["stages"]["texture_transfer"])
        
        # Stage 8: Hair extraction comes from the reconstructed reference,
        # not the canonical body mesh.
        stage_key = self._get_stage_key("hair", ref_mesh_path)
        if not self.manifest.is_complete(stage_key):
            results["stages"]["hair"] = hair.extract_hair(ref_mesh_path, output_dir)
            self.manifest.record_stage(stage_key, results["stages"]["hair"])
        
        # Stage 9: Compare reconstructed appearance geometry against the fitted
        # canonical body so clothing is not trivially distance-zero.
        stage_key = self._get_stage_key("clothing", ref_mesh_path, fitted_mesh)
        if not self.manifest.is_complete(stage_key):
            results["stages"]["clothing"] = clothing.extract_clothing(ref_mesh_path, fitted_mesh, output_dir)
            self.manifest.record_stage(stage_key, results["stages"]["clothing"])
        
        # Stage 10: Rigging - call real rig_avatar() with fitted_mesh
        stage_key = self._get_stage_key("rig", fitted_mesh)
        if not self.manifest.is_complete(stage_key):
            from vtuber_pipeline.avatar.rigging import rig_avatar
            try:
                rigged_path = str(pathlib.Path(output_dir) / "rigged.glb")
                rig_result = rig_avatar(fitted_mesh, rigged_path)
                results["stages"]["rig"] = {
                    "status": "complete",
                    "rigged_mesh": rig_result,
                    "bone_count": 24
                }
            except ImportError as e:
                results["stages"]["rig"] = {
                    "status": "error",
                    "error": f"Missing dependency: {e}"
                }
            except Exception as e:
                results["stages"]["rig"] = {
                    "status": "error",
                    "error": str(e)
                }
            self.manifest.record_stage(stage_key, results["stages"]["rig"])
        
        # Stage 11: Expressions - call real generate_expressions() with fitted_mesh
        stage_key = self._get_stage_key("expressions", fitted_mesh)
        if not self.manifest.is_complete(stage_key):
            rigged_mesh = results["stages"]["rig"].get("rigged_mesh", fitted_mesh) if results["stages"]["rig"].get("status") == "complete" else fitted_mesh
            try:
                expr_result = expressions.generate_expressions(rigged_mesh)
                # Validate the generated expressions
                validation_result = expressions.validate_expressions(
                    expr_result.get("expressions", {}), output_dir
                )
                results["stages"]["expressions"] = {
                    "status": "complete" if validation_result.get("pass") else "partial",
                    "expressions": expr_result.get("expressions", {}),
                    "validation": validation_result
                }
            except Exception as e:
                results["stages"]["expressions"] = {
                    "status": "error",
                    "error": str(e)
                }
            self.manifest.record_stage(stage_key, results["stages"]["expressions"])
        
        # Stage 12: Gaze must use the rigged GLB so real leftEye/rightEye nodes exist.
        rigged_mesh = results["stages"]["rig"].get("rigged_mesh", fitted_mesh)
        stage_key = self._get_stage_key("gaze", rigged_mesh)
        if not self.manifest.is_complete(stage_key):
            results["stages"]["gaze"] = gaze.configure_gaze(rigged_mesh, output_dir)
            self.manifest.record_stage(stage_key, results["stages"]["gaze"])
        
        # Stage 13: SpringBone must inspect the rigged GLB because spring joints
        # are glTF nodes, not raw fitted vertices.
        rigged_mesh = results["stages"]["rig"].get("rigged_mesh", fitted_mesh)
        stage_key = self._get_stage_key("springbone", rigged_mesh)
        if not self.manifest.is_complete(stage_key):
            results["stages"]["springbone"] = springbone.generate_springbone_config(rigged_mesh, output_dir)
            self.manifest.record_stage(stage_key, results["stages"]["springbone"])
        
        # Stage 14: Materials - use fitted_mesh
        stage_key = self._get_stage_key("materials", fitted_mesh)
        if not self.manifest.is_complete(stage_key):
            results["stages"]["materials"] = materials.configure_materials(fitted_mesh, output_dir)
            self.manifest.record_stage(stage_key, results["stages"]["materials"])
        
        # Stage 15: VRM export - call real export_vrm()
        stage_key = self._get_stage_key("vrm_export", rigged_mesh)
        if not self.manifest.is_complete(stage_key):
            rigged_mesh = results["stages"]["rig"].get("rigged_mesh", ref_mesh) if results["stages"]["rig"].get("status") == "complete" else ref_mesh
            expr_data = results["stages"]["expressions"].get("expressions", {}) if results["stages"]["expressions"].get("status") in ["complete", "partial"] else None
            springbone_config = results["stages"]["springbone"] if results["stages"]["springbone"].get("status") == "complete" else None
            commercial_usage = config.get("commercial_usage", "corporation") if config else "corporation"
            try:
                results["stages"]["vrm_export"] = vrm_export.export_vrm(
                    rigged_mesh, output_dir, expressions=expr_data, commercial_usage=commercial_usage,
                    springbone_config=springbone_config
                )
            except Exception as e:
                results["stages"]["vrm_export"] = {
                    "status": "error",
                    "error": str(e)
                }
            self.manifest.record_stage(stage_key, results["stages"]["vrm_export"])
        
        # Stage 16: Validator - call real validate_vrm()
        vrm_path = results["stages"]["vrm_export"].get("vrm_path", str(pathlib.Path(output_dir) / "avatar.vrm"))
        stage_key = self._get_stage_key("validator", vrm_path)
        if not self.manifest.is_complete(stage_key):
            try:
                results["stages"]["validator"] = validator.validate_vrm(vrm_path, output_dir)
            except Exception as e:
                results["stages"]["validator"] = {
                    "passed": False,
                    "error": str(e)
                }
            self.manifest.record_stage(stage_key, results["stages"]["validator"])
        
        # Overall status - determine based on stage results
        # 'failed' if validation didn't pass
        # 'partial' if any stage is error/stub/fallback
        # 'complete' only if all stages succeeded
        
        validation_passed = results["stages"].get("validator", {}).get("passed", False)
        
        error_stages = [
            name for name, result in results["stages"].items()
            if isinstance(result, dict) and result.get("status") == "error"
        ]
        
        stub_stages = [
            name for name, result in results["stages"].items()
            if isinstance(result, dict) and result.get("status") == "stub"
        ]
        partial_stages = [
            name for name, result in results["stages"].items()
            if isinstance(result, dict) and result.get("status") in {"partial", "skipped"}
        ]
        fallback_stages = [
            name for name, result in results["stages"].items()
            if isinstance(result, dict) and result.get("status") == "fallback"
        ]
        
        if not validation_passed:
            results["status"] = "failed"
            results["failed_reason"] = "VRM validation did not pass"
        elif error_stages:
            results["status"] = "failed"
            results["failed_stages"] = error_stages
        elif stub_stages or partial_stages or fallback_stages:
            results["status"] = "partial"
            results["stub_stages"] = stub_stages
            results["partial_stages"] = partial_stages
            results["fallback_stages"] = fallback_stages
        else:
            results["status"] = "complete"
        
        # Add top-level convenience keys for easy access
        if results["status"] == "complete":
            if "vrm_export" in results["stages"] and results["stages"]["vrm_export"].get("status") == "complete":
                results["vrm_path"] = results["stages"]["vrm_export"]["vrm_path"]
            if "validator" in results["stages"]:
                results["validation"] = results["stages"]["validator"]
        
        return results
    
    def _get_stage_key(self, stage_name: str, *inputs) -> str:
        """Compute a stage key for the manifest.
        
        Args:
            stage_name: Name of the pipeline stage.
            *inputs: Input values for the stage.
            
        Returns:
            Unique stage key string.
        """
        import hashlib
        hash_input = f"{stage_name}:{':'.join(str(i) for i in inputs)}"
        return hashlib.sha256(hash_input.encode()).hexdigest()[:16]


def build_avatar(
    image_path: str,
    output_dir: str,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Convenience function to build an avatar.
    
    Args:
        image_path: Path to the input image.
        output_dir: Directory for output files.
        config: Optional configuration dictionary.
        
    Returns:
        Build results dictionary.
    """
    pipeline = AvatarPipeline(output_dir, config)
    return pipeline.build(image_path)
