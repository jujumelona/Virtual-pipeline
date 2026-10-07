"""Fail-closed avatar build orchestrator."""

import hashlib
import json
import pathlib
from typing import Dict, Any, Optional, Callable


class AvatarPipeline:
    """Run only stages that materially contribute to the final VRM.

    Mainline:
    input gate/landmarks → TripoSR → canonical fitting → texture → rig →
    expressions → gaze → SpringBone → VRM export → strict validation.
    """

    CACHE_SCHEMA = "avatar-pipeline-v6"

    def __init__(self, output_dir: str, config: Optional[Dict[str, Any]] = None):
        self.output_dir = pathlib.Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.config = {} if config is None else config
        from vtuber_pipeline.core.manifest import PipelineManifest
        self.manifest = PipelineManifest(output_dir)
        self.code_fingerprint = self._compute_code_fingerprint()

    def _compute_code_fingerprint(self) -> str:
        """Hash current avatar pipeline source so code changes invalidate caches."""
        digest = hashlib.sha256()
        avatar_dir = pathlib.Path(__file__).resolve().parent
        for path in sorted(avatar_dir.glob("*.py")):
            digest.update(path.name.encode("utf-8"))
            digest.update(path.read_bytes())
        core_manifest = avatar_dir.parent / "core" / "manifest.py"
        if core_manifest.is_file():
            digest.update(core_manifest.name.encode("utf-8"))
            digest.update(core_manifest.read_bytes())

        # Dependency/model pins are part of the computational contract. A
        # package/model revision change must never reuse artifacts produced by
        # the previous runtime.
        repo_root = avatar_dir.parent.parent
        for contract_path in (
            repo_root / "pyproject.toml",
            repo_root / "third_party.lock.json",
        ):
            if contract_path.is_file():
                digest.update(contract_path.name.encode("utf-8"))
                digest.update(contract_path.read_bytes())
        return digest.hexdigest()

    def _fingerprint(self, value: Any) -> str:
        path = pathlib.Path(value) if isinstance(value, str) else None
        if path is not None and path.is_file():
            digest = hashlib.sha256()
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            return f"file:{digest.hexdigest()}"
        try:
            return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
        except Exception:
            return repr(value)

    def _get_stage_key(self, stage_name: str, *inputs: Any) -> str:
        payload = [self.CACHE_SCHEMA, self.code_fingerprint, stage_name]
        payload.extend(self._fingerprint(value) for value in inputs)
        return hashlib.sha256("\n".join(payload).encode("utf-8")).hexdigest()[:24]

    def _run_stage(
        self,
        name: str,
        inputs: tuple[Any, ...],
        fn: Callable[[], Dict[str, Any]],
    ) -> Dict[str, Any]:
        key = self._get_stage_key(name, *inputs)
        if self.manifest.is_complete(key):
            cached = self.manifest.get_stage(key)
            if cached:
                restored = dict(cached)
                restored["cache_hit"] = True
                restored["stage_key"] = key
                return restored

        result = fn()
        if not isinstance(result, dict):
            result = {"status": "error", "error": f"{name} returned a non-dict result"}
        result.setdefault("stage_name", name)
        result["stage_key"] = key

        # Normalize artifact paths for strict resume integrity checks.
        artifact_keys = (
            "output_path",
            "vrm_path",
            "rigged_mesh",
            "fitted_mesh",
            "texture_png",
            "uv_path",
            "mesh_path",
            "fit_npz",
            "face_png",
            "body_png",
        )
        artifacts = []
        for artifact_key in artifact_keys:
            artifact = result.get(artifact_key)
            if isinstance(artifact, str) and artifact:
                if artifact not in artifacts:
                    artifacts.append(artifact)

        if not result.get("output_path") and artifacts:
            result["output_path"] = artifacts[0]
        result["artifact_paths"] = artifacts
        self.manifest.record_stage(key, result)
        return result

    @staticmethod
    def _fail(results: Dict[str, Any], stage: str, reason: str) -> Dict[str, Any]:
        results["status"] = "failed"
        results["failed_stages"] = [stage]
        results["failed_reason"] = reason
        return results

    def build(
        self,
        image_path: str,
        output_dir: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if output_dir is not None:
            requested = pathlib.Path(output_dir).expanduser().resolve()
            bound = self.output_dir.expanduser().resolve()
            if requested != bound:
                return {
                    "status": "failed",
                    "image_path": image_path,
                    "output_dir": str(bound),
                    "stages": {},
                    "failed_stages": ["orchestrator"],
                    "failed_reason": (
                        "AvatarPipeline is bound to one output directory; "
                        f"requested={requested}, bound={bound}"
                    ),
                }
        output_dir = str(self.output_dir)

        def config_failure(reason: str) -> Dict[str, Any]:
            return {
                "status": "failed",
                "image_path": image_path,
                "output_dir": output_dir,
                "stages": {},
                "failed_stages": ["orchestrator"],
                "failed_reason": reason,
            }

        if not isinstance(self.config, dict):
            return config_failure("AvatarPipeline config must be an object")
        if config is not None and not isinstance(config, dict):
            return config_failure("build config override must be an object")

        cfg = {**self.config, **(config or {})}
        allowed_top = {
            "profile",
            "commercial_usage",
            "reconstruction",
            "fitting",
        }
        unknown_top = sorted(set(cfg) - allowed_top)
        if unknown_top:
            return config_failure(
                f"Unknown avatar config keys: {unknown_top}"
            )

        profile = cfg.get("profile", "commercial")
        if profile not in {"commercial", "production", "development"}:
            return config_failure(
                f"Unsupported profile: {profile!r}"
            )

        commercial_usage = cfg.get("commercial_usage", "corporation")
        if commercial_usage not in {
            "personalNonProfit",
            "personalProfit",
            "corporation",
        }:
            return config_failure(
                f"Unsupported commercial_usage: {commercial_usage!r}"
            )

        from vtuber_pipeline.avatar.reconstruction import TRIPOSR_MODEL_REVISION

        reconstruction_raw = cfg.get("reconstruction", {})
        if reconstruction_raw is None:
            reconstruction_cfg = {}
        elif isinstance(reconstruction_raw, dict):
            reconstruction_cfg = reconstruction_raw
        else:
            return config_failure("reconstruction config must be an object")

        unknown_reconstruction = sorted(
            set(reconstruction_cfg)
            - {"model_save_format", "remove_background"}
        )
        if unknown_reconstruction:
            return config_failure(
                "Unknown reconstruction config keys: "
                f"{unknown_reconstruction}"
            )

        model_save_format = reconstruction_cfg.get(
            "model_save_format",
            "obj",
        )
        if not isinstance(model_save_format, str):
            return config_failure(
                "reconstruction.model_save_format must be a string"
            )
        if model_save_format not in {"obj", "glb"}:
            return config_failure(
                "reconstruction.model_save_format must be 'obj' or 'glb'"
            )

        remove_background = reconstruction_cfg.get(
            "remove_background",
            True,
        )
        if not isinstance(remove_background, bool):
            return config_failure(
                "reconstruction.remove_background must be boolean"
            )

        fitting_raw = cfg.get("fitting", {})
        if fitting_raw is None:
            fitting_cfg = {}
        elif isinstance(fitting_raw, dict):
            fitting_cfg = fitting_raw
        else:
            return config_failure("fitting config must be an object")

        reconstruction_options = {
            "profile": profile,
            "model_save_format": model_save_format,
            "remove_background": remove_background,
            "model_revision": TRIPOSR_MODEL_REVISION,
        }

        results: Dict[str, Any] = {
            "status": "running",
            "image_path": image_path,
            "output_dir": output_dir,
            "stages": {},
        }

        from vtuber_pipeline.avatar.input_gate import validate_input
        from vtuber_pipeline.avatar.reconstruction import reconstruct_avatar
        from vtuber_pipeline.avatar.template_mesh import get_template_path
        from vtuber_pipeline.avatar.template_fitting import fit_template
        from vtuber_pipeline.avatar.texture_transfer import transfer_texture
        from vtuber_pipeline.avatar.rigging import rig_avatar
        from vtuber_pipeline.avatar.expressions import generate_expressions, validate_expressions
        from vtuber_pipeline.avatar.gaze import configure_gaze
        from vtuber_pipeline.avatar.springbone import generate_springbone_config
        from vtuber_pipeline.avatar.vrm_export import export_vrm
        from vtuber_pipeline.avatar.validator import validate_vrm

        # 1. Input gate also performs face detection and persists landmarks.
        gate = self._run_stage(
            "input_gate",
            (image_path,),
            lambda: validate_input(image_path, output_dir),
        )
        results["stages"]["input_gate"] = gate
        if gate.get("status") != "complete" or not gate.get("valid"):
            return self._fail(results, "input_gate", gate.get("errors") or gate.get("error") or "input rejected")
        landmarks = gate.get("landmarks", [])
        if len(landmarks) < 28:
            return self._fail(results, "input_gate", "fewer than 28 facial landmarks")

        # 2. Real input reconstruction. No canonical fallback is permitted.
        reconstruction_dir = str(pathlib.Path(output_dir) / "reconstruction")
        def reconstruct_stage() -> Dict[str, Any]:
            try:
                mesh_path = reconstruct_avatar(
                    image_path,
                    reconstruction_dir,
                    profile=profile,
                    model_save_format=model_save_format,
                    remove_background=remove_background,
                )
                return {
                    "status": "complete",
                    "mesh_path": mesh_path,
                    "output_path": mesh_path,
                    "source": "triposr",
                    "model_options": dict(reconstruction_options),
                }
            except Exception as exc:
                return {"status": "error", "error": str(exc), "source": "triposr"}

        reconstruction = self._run_stage(
            "reference_reconstruction",
            (image_path, reconstruction_options),
            reconstruct_stage,
        )
        results["stages"]["reference_reconstruction"] = reconstruction
        if reconstruction.get("status") != "complete":
            return self._fail(results, "reference_reconstruction", reconstruction.get("error", "TripoSR failed"))
        reference_mesh = reconstruction["mesh_path"]

        # 3. Fit one stable CC0-derived canonical topology to the reference.
        try:
            template_path = str(get_template_path())
        except Exception as exc:
            return self._fail(results, "template_fitting", f"canonical template unavailable: {exc}")

        fitting = self._run_stage(
            "template_fitting",
            (template_path, reference_mesh, landmarks, fitting_cfg),
            lambda: fit_template(
                template_path,
                landmarks,
                output_dir,
                fitting_cfg,
                reference_mesh_path=reference_mesh,
            ),
        )
        results["stages"]["template_fitting"] = fitting
        if fitting.get("status") != "complete":
            return self._fail(results, "template_fitting", fitting.get("error", "template fitting failed"))
        fitted_mesh = fitting.get("fitted_mesh")
        if not fitted_mesh or not pathlib.Path(fitted_mesh).is_file():
            return self._fail(results, "template_fitting", "fitted mesh artifact is missing")
        results["fitted_mesh"] = fitted_mesh

        # 4. Project source appearance onto the fitted canonical topology.
        texture = self._run_stage(
            "texture_transfer",
            (image_path, fitted_mesh, gate.get("bbox")),
            lambda: transfer_texture(
                image_path,
                fitted_mesh,
                output_dir,
                face_bbox=gate.get("bbox"),
            ),
        )
        results["stages"]["texture_transfer"] = texture
        if texture.get("status") != "complete":
            return self._fail(results, "texture_transfer", texture.get("error", "texture transfer failed"))
        texture_path = texture.get("texture_png")
        uv_path = texture.get("uv_path")
        if not texture_path or not pathlib.Path(texture_path).is_file():
            return self._fail(results, "texture_transfer", "texture artifact is missing")
        if not uv_path or not pathlib.Path(uv_path).is_file():
            return self._fail(results, "texture_transfer", "texture UV artifact is missing")

        # 5. Build the humanoid skin plus a localized secondary hair chain.
        rigged_path = str(pathlib.Path(output_dir) / "rigged.glb")
        def rig_stage() -> Dict[str, Any]:
            try:
                path = rig_avatar(
                    fitted_mesh,
                    rigged_path,
                    texture_path=texture_path,
                    uv_path=uv_path,
                )
                return {"status": "complete", "rigged_mesh": path, "output_path": path}
            except Exception as exc:
                return {"status": "error", "error": str(exc)}

        rig = self._run_stage(
            "rig",
            (fitted_mesh, texture_path, uv_path),
            rig_stage,
        )
        results["stages"]["rig"] = rig
        if rig.get("status") != "complete":
            return self._fail(results, "rig", rig.get("error", "rigging failed"))
        rigged_mesh = rig["rigged_mesh"]

        # 6. Generate required broadcast expressions and reject empty morphs.
        def expression_stage() -> Dict[str, Any]:
            generated = generate_expressions(rigged_mesh)
            if generated.get("status") == "error":
                return generated
            expression_map = generated.get("expressions", {})
            validation = validate_expressions(expression_map, output_dir)
            empty = [
                name for name, item in expression_map.items()
                if name in validation.get("required_expressions", [])
                and not item.get("morph_targets")
            ]
            ok = bool(validation.get("pass")) and not empty
            return {
                "status": "complete" if ok else "error",
                "expressions": expression_map,
                "validation": validation,
                "empty_expressions": empty,
                "error": None if ok else f"missing or empty required morphs: {empty or validation.get('missing_expressions', [])}",
            }

        expressions = self._run_stage("expressions", (rigged_mesh,), expression_stage)
        results["stages"]["expressions"] = expressions
        if expressions.get("status") != "complete":
            return self._fail(results, "expressions", expressions.get("error", "expression generation failed"))

        # 7. Read actual eye/head nodes for VRM lookAt.
        gaze = self._run_stage(
            "gaze",
            (rigged_mesh,),
            lambda: configure_gaze(rigged_mesh, output_dir),
        )
        results["stages"]["gaze"] = gaze
        if gaze.get("status") != "complete":
            return self._fail(results, "gaze", gaze.get("error", "gaze configuration failed"))

        # 8. Build SpringBone from actual secondary rig nodes.
        spring = self._run_stage(
            "springbone",
            (rigged_mesh,),
            lambda: generate_springbone_config(rigged_mesh, output_dir),
        )
        results["stages"]["springbone"] = spring
        if spring.get("status") != "complete":
            return self._fail(results, "springbone", spring.get("error") or spring.get("warning") or "SpringBone chain missing")

        # 9. Export VRM using only normalized contracts from prior stages.
        export = self._run_stage(
            "vrm_export",
            (rigged_mesh, expressions["expressions"], gaze.get("config"), spring, commercial_usage),
            lambda: export_vrm(
                rigged_mesh,
                output_dir,
                expressions=expressions["expressions"],
                commercial_usage=commercial_usage,
                springbone_config=spring,
                gaze_config=gaze.get("config"),
            ),
        )
        results["stages"]["vrm_export"] = export
        if export.get("status") != "complete":
            return self._fail(results, "vrm_export", export.get("error") or export.get("errors") or "VRM export failed")
        vrm_path = export.get("vrm_path")

        # 10. Product validator is mandatory; spec-optional features that are
        # required by this project (expressions/lookAt/SpringBone) must exist.
        validation = self._run_stage(
            "validator",
            (vrm_path,),
            lambda: validate_vrm(vrm_path, output_dir),
        )
        results["stages"]["validator"] = validation
        if validation.get("status") != "complete" or not validation.get("passed"):
            return self._fail(results, "validator", validation.get("error") or "strict VRM validation failed")

        results["status"] = "complete"
        results["vrm_path"] = vrm_path
        results["validation"] = validation
        return results


def build_avatar(
    image_path: str,
    output_dir: str,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build one avatar through the fail-closed mainline."""
    return AvatarPipeline(output_dir, config).build(image_path)
