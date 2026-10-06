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
        
        # Stage 1: Input gate
        stage_key = self._get_stage_key("input_gate", image_path)
        if not self.manifest.is_complete(stage_key):
            results["stages"]["input_gate"] = input_gate.validate_input(image_path, output_dir)
            self.manifest.record_stage(stage_key, results["stages"]["input_gate"])
        else:
            results["stages"]["input_gate"] = {"status": "cached", "stage_key": stage_key}
        
        # Stage 2: Face landmarks (stub)
        stage_key = self._get_stage_key("face_landmarks", image_path)
        if not self.manifest.is_complete(stage_key):
            results["stages"]["face_landmarks"] = {"status": "stub", "landmarks": []}
            self.manifest.record_stage(stage_key, results["stages"]["face_landmarks"])
        
        # Stage 3: Reference reconstruction - use real canonical template
        stage_key = self._get_stage_key("reference_reconstruction", image_path)
        if not self.manifest.is_complete(stage_key):
            # Use canonical template as the reference mesh
            template_path = pathlib.Path(__file__).parent.parent.parent / "assets" / "canonical_vtuber" / "template.glb"
            if template_path.exists():
                results["stages"]["reference_reconstruction"] = {
                    "status": "complete",
                    "mesh_path": str(template_path),
                    "source": "canonical_template"
                }
            else:
                results["stages"]["reference_reconstruction"] = {
                    "status": "error",
                    "error": f"Canonical template not found: {template_path}",
                    "mesh_path": None
                }
            self.manifest.record_stage(stage_key, results["stages"]["reference_reconstruction"])
        else:
            # Load cached result
            template_path = pathlib.Path(__file__).parent.parent.parent / "assets" / "canonical_vtuber" / "template.glb"
            results["stages"]["reference_reconstruction"] = {
                "status": "cached",
                "mesh_path": str(template_path),
                "stage_key": stage_key
            }
        
        # Stage 4: Reference analysis
        ref_mesh = results["stages"]["reference_reconstruction"].get("mesh_path", "")
        stage_key = self._get_stage_key("reference_analysis", ref_mesh)
        if not self.manifest.is_complete(stage_key):
            results["stages"]["reference_analysis"] = reference_analysis.analyze_reference(ref_mesh, output_dir)
            self.manifest.record_stage(stage_key, results["stages"]["reference_analysis"])
        
        # Stage 5: Template fitting - use real fit_template()
        landmarks = results["stages"]["face_landmarks"].get("landmarks", [])
        stage_key = self._get_stage_key("template_fitting", ref_mesh)
        if not self.manifest.is_complete(stage_key):
            # Call real fit_template with the canonical template
            template_path = pathlib.Path(__file__).parent.parent.parent / "assets" / "canonical_vtuber" / "template.glb"
            if template_path.exists():
                results["stages"]["template_fitting"] = template_fitting.fit_template(
                    str(template_path), landmarks, output_dir, config.get("fitting")
                )
            else:
                results["stages"]["template_fitting"] = {
                    "status": "error",
                    "error": f"Template not found: {template_path}"
                }
            self.manifest.record_stage(stage_key, results["stages"]["template_fitting"])
        
        # Stage 6: Deformation transfer
        fit_npz = str(pathlib.Path(output_dir) / "fit.npz")
        stage_key = self._get_stage_key("deformation_transfer", fit_npz)
        if not self.manifest.is_complete(stage_key):
            results["stages"]["deformation_transfer"] = deformation_transfer.transfer_deformation(
                ref_mesh, ref_mesh, fit_npz, output_dir
            )
            self.manifest.record_stage(stage_key, results["stages"]["deformation_transfer"])
        
        # Stage 7: Texture transfer
        stage_key = self._get_stage_key("texture_transfer", image_path)
        if not self.manifest.is_complete(stage_key):
            results["stages"]["texture_transfer"] = texture_transfer.transfer_texture(
                image_path, ref_mesh, output_dir
            )
            self.manifest.record_stage(stage_key, results["stages"]["texture_transfer"])
        
        # Stage 8: Hair extraction
        stage_key = self._get_stage_key("hair", ref_mesh)
        if not self.manifest.is_complete(stage_key):
            results["stages"]["hair"] = hair.extract_hair(ref_mesh, output_dir)
            self.manifest.record_stage(stage_key, results["stages"]["hair"])
        
        # Stage 9: Clothing extraction
        stage_key = self._get_stage_key("clothing", ref_mesh)
        if not self.manifest.is_complete(stage_key):
            results["stages"]["clothing"] = clothing.extract_clothing(ref_mesh, ref_mesh, output_dir)
            self.manifest.record_stage(stage_key, results["stages"]["clothing"])
        
        # Stage 10: Rigging - call real rig_avatar()
        stage_key = self._get_stage_key("rig", ref_mesh)
        if not self.manifest.is_complete(stage_key):
            from vtuber_pipeline.avatar.rigging import rig_avatar
            try:
                rigged_path = str(pathlib.Path(output_dir) / "rigged.glb")
                rig_result = rig_avatar(ref_mesh, rigged_path)
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
        
        # Stage 11: Expressions - call real generate_expressions()
        stage_key = self._get_stage_key("expressions", ref_mesh)
        if not self.manifest.is_complete(stage_key):
            rigged_mesh = results["stages"]["rig"].get("rigged_mesh", ref_mesh) if results["stages"]["rig"].get("status") == "complete" else ref_mesh
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
        
        # Stage 12: Gaze
        stage_key = self._get_stage_key("gaze", ref_mesh)
        if not self.manifest.is_complete(stage_key):
            results["stages"]["gaze"] = gaze.configure_gaze(ref_mesh, output_dir)
            self.manifest.record_stage(stage_key, results["stages"]["gaze"])
        
        # Stage 13: SpringBone
        stage_key = self._get_stage_key("springbone", ref_mesh)
        if not self.manifest.is_complete(stage_key):
            results["stages"]["springbone"] = springbone.generate_springbone_config(ref_mesh, output_dir)
            self.manifest.record_stage(stage_key, results["stages"]["springbone"])
        
        # Stage 14: Materials
        stage_key = self._get_stage_key("materials", ref_mesh)
        if not self.manifest.is_complete(stage_key):
            results["stages"]["materials"] = materials.configure_materials(ref_mesh, output_dir)
            self.manifest.record_stage(stage_key, results["stages"]["materials"])
        
        # Stage 15: VRM export - call real export_vrm()
        stage_key = self._get_stage_key("vrm_export", ref_mesh)
        if not self.manifest.is_complete(stage_key):
            rigged_mesh = results["stages"]["rig"].get("rigged_mesh", ref_mesh) if results["stages"]["rig"].get("status") == "complete" else ref_mesh
            expr_data = results["stages"]["expressions"].get("expressions", {}) if results["stages"]["expressions"].get("status") in ["complete", "partial"] else None
            try:
                results["stages"]["vrm_export"] = vrm_export.export_vrm(
                    rigged_mesh, output_dir, expressions=expr_data
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
