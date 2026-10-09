"""Fail-closed avatar build orchestrator."""

import hashlib
import json
import math
import pathlib
from typing import Dict, Any, Optional, Callable
from vtuber_pipeline.core.stage_progress import report_stage


class AvatarPipeline:
    """Run only stages that materially contribute to the final VRM.

    Mainline:
    input gate/landmarks → TripoSR → canonical fitting → texture → rig →
    expressions → gaze → SpringBone → VRM export → strict validation.
    """

    CACHE_SCHEMA = "avatar-pipeline-v8-licensed-observed-multiview"

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
        repo_root = avatar_dir.parent.parent
        # The orchestrator also calls Python outside avatar/. Changes to model
        # workers, perception, or shared stage contracts must invalidate the
        # cached successful stages before their Python call is bypassed.
        for directory in (
            avatar_dir,
            repo_root / "vtuber_pipeline" / "common",
            repo_root / "vtuber_pipeline" / "perception",
            repo_root / "tools" / "model_workers",
        ):
            if not directory.is_dir():
                continue
            for path in sorted(directory.glob("*.py")):
                digest.update(path.relative_to(repo_root).as_posix().encode("utf-8"))
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

    @staticmethod
    def _gate_landmark_contract_error(gate: Dict[str, Any]) -> Optional[str]:
        """A successful face gate MUST contain 28 finite 2D landmarks."""
        points = gate.get("landmarks")
        count = len(points) if isinstance(points, list) else 0
        if count != 28:
            return (
                f"input gate landmark contract mismatch: got {count}/28 "
                f"landmarks (reported landmark_count={gate.get('landmark_count')!r})"
            )
        if any(
            not isinstance(point, (list, tuple))
            or len(point) != 2
            or any(
                not isinstance(coordinate, (float, int))
                or isinstance(coordinate, bool)
                or not math.isfinite(coordinate)
                for coordinate in point
            )
            for point in points
        ):
            return "input gate landmark contract mismatch: invalid 2D coordinates"
        return None

    def _run_stage(
        self,
        name: str,
        inputs: tuple[Any, ...],
        fn: Callable[[], Dict[str, Any]],
    ) -> Dict[str, Any]:
        report_stage(name, "running")
        key = self._get_stage_key(name, *inputs)
        if self.manifest.is_complete(key):
            cached = self.manifest.get_stage(key)
            if cached:
                restored = dict(cached)
                if name == "input_gate" and self._gate_landmark_contract_error(restored):
                    report_stage(
                        name, "invalid_cache",
                        self._gate_landmark_contract_error(restored),
                    )
                    # Never restore a semantically incomplete face gate, even
                    # when the manifest says complete. Re-run detection.
                else:
                    restored["cache_hit"] = True
                    restored["stage_key"] = key
                    report_stage(name, "cached")
                    return restored

        try:
            result = fn()
        except Exception as exc:
            report_stage(name, "error", str(exc))
            raise
        if not isinstance(result, dict):
            result = {"status": "error", "error": f"{name} returned a non-dict result"}
        if name == "input_gate":
            count = len(result.get("landmarks", [])) if isinstance(
                result.get("landmarks"), list
            ) else 0
            report_stage(
                "face_landmarks", "checked",
                f"count={count}/28 median={result.get('landmark_score_median', 'unknown')} "
                f"valid={result.get('valid')}",
            )
            if result.get("status") == "complete":
                error = self._gate_landmark_contract_error(result)
                if error:
                    result["status"] = "error"
                    result["valid"] = False
                    result["error"] = error
                    result["errors"] = [error]
        result.setdefault("stage_name", name)
        result["stage_key"] = key

        # Normalize artifact paths for strict resume integrity checks.
        artifact_keys = (
            "output_path",
            "vrm_path",
            "rigged_mesh",
            "blend",
            "report_json",
            "fitted_mesh",
            "texture_png",
            "uv_path",
            "mesh_path",
            "fit_npz",
            "refined_glb",
            "hair_geometry_glb",
            "report_path",
            "landmarks_json",
            "camera_json",
            "face_png",
            "body_png",
            "rgba_png",
            "alpha_png",
            "depth_manifest",
            "depth_front",
            "depth_back",
            "depth_left",
            "depth_right",
            "mesh_obj",
            "provenance_json",
            "constraints_json",
            "aligned_multiview_glb",
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
        report_stage(name, str(result.get("status", "unknown")), str(result.get("error") or ""))
        return result

    @staticmethod
    def _fail(results: Dict[str, Any], stage: str, reason: str) -> Dict[str, Any]:
        results["status"] = "failed"
        results["failed_stages"] = [stage]
        results["failed_reason"] = reason
        report_stage(stage, "failed", str(reason))
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
            "references",
            "rigging",
        }
        unknown_top = sorted(set(cfg) - allowed_top)
        if unknown_top:
            return config_failure(
                f"Unknown avatar config keys: {unknown_top}"
            )

        rigging_cfg = cfg.get("rigging", {})
        if not isinstance(rigging_cfg, dict) or set(rigging_cfg) - {"provider"}:
            return config_failure("rigging must be an object with only provider")
        rigging_provider = rigging_cfg.get("provider", "canonical")
        if rigging_provider not in {"canonical", "skintokens"}:
            return config_failure("rigging.provider must be canonical or skintokens")

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

        reference_raw = cfg.get("references") or {}
        if not isinstance(reference_raw, dict):
            return config_failure("references must be an object")
        unknown_references = sorted(
            set(reference_raw) -
            {"full_body", "face_image", "back_image", "left_image", "right_image", "texture_size"}
        )
        if unknown_references:
            return config_failure(
                f"Unknown references config keys: {unknown_references}"
            )
        full_body = reference_raw.get("full_body", False)
        if not isinstance(full_body, bool):
            return config_failure("references.full_body must be boolean")
        face_image = reference_raw.get("face_image")
        back_image = reference_raw.get("back_image")
        left_image = reference_raw.get("left_image")
        right_image = reference_raw.get("right_image")
        for ref_name, ref_value in (("face_image", face_image), ("back_image", back_image),
                                    ("left_image", left_image), ("right_image", right_image)):
            if ref_value is not None and (
                not isinstance(ref_value, str) or not ref_value.strip()
            ):
                return config_failure(f"references.{ref_name} must be a file path")
        texture_size = reference_raw.get("texture_size", 2048 if full_body else 1024)
        if type(texture_size) is not int or texture_size not in {1024, 2048}:
            return config_failure("references.texture_size must be 1024 or 2048")
        if full_body and not face_image:
            return config_failure(
                "full-body mode requires references.face_image, independently "
                "of the full-body front reference"
            )

        def input_digest(path: str | None) -> str | None:
            if not path:
                return None
            source_path = pathlib.Path(path)
            if not source_path.is_file():
                return f"missing:{source_path}"
            sha = hashlib.sha256()
            with source_path.open("rb") as file:
                for block in iter(lambda: file.read(1048576), b""):
                    sha.update(block)
            return sha.hexdigest()

        reference_digests = {
            "front": input_digest(image_path),
            "face": input_digest(face_image),
            "back": input_digest(back_image),
            "left": input_digest(left_image),
            "right": input_digest(right_image),
        }
        reference_options = {
            "full_body": full_body,
            "face_image": face_image,
            "back_image": back_image,
            "left_image": left_image,
            "right_image": right_image,
            "texture_size": texture_size,
        }

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

        import vtuber_pipeline.avatar.input_gate as input_gate_module
        validate_input = input_gate_module.validate_input
        source = pathlib.Path(validate_input.__code__.co_filename).resolve()
        expected_source = pathlib.Path(__file__).resolve().with_name("input_gate.py")
        contract = getattr(input_gate_module, "INPUT_GATE_CONTRACT", None)
        report_stage(
            "module_diagnostics", "log",
            f"input_gate runtime_file={source} expected_file={expected_source} "
            f"module_file={getattr(input_gate_module, '__file__', None)} "
            f"contract={contract!r}",
        )
        if contract != "scored-28-landmarks-v2":
            return self._fail(
                results, "input_gate",
                "stale input_gate Python module (missing scored-28-landmarks-v2 contract)",
            )
        if (
            source != expected_source
            and validate_input.__module__ == input_gate_module.__name__
        ):
            return self._fail(
                results, "input_gate",
                f"input_gate loaded from unexpected file: {source}",
            )
        from vtuber_pipeline.avatar.reference_quality import inspect_references
        from vtuber_pipeline.avatar.reconstruction import reconstruct_avatar
        from vtuber_pipeline.avatar.template_mesh import get_template_path
        from vtuber_pipeline.avatar.template_fitting import fit_template
        from vtuber_pipeline.perception.anime_alpha import create_person_alpha
        from vtuber_pipeline.avatar.depth_runner import estimate_depth
        from vtuber_pipeline.avatar.licensed_multiview import reconstruct_licensed_multiview
        from vtuber_pipeline.avatar.multiview_fitting import align_sources
        from vtuber_pipeline.avatar.texture_transfer import transfer_texture
        from vtuber_pipeline.avatar.rigging import rig_avatar
        from vtuber_pipeline.avatar.expressions import generate_expressions, validate_expressions
        from vtuber_pipeline.avatar.gaze import configure_gaze
        from vtuber_pipeline.avatar.springbone import generate_springbone_config
        from vtuber_pipeline.avatar.vrm_export import export_vrm
        from vtuber_pipeline.avatar.blender_bridge import export_blender_from_vrm
        from vtuber_pipeline.avatar.validator import validate_vrm

        # 0. Diagnose front/body, facial and optional back references.
        # No synthetic silhouettes, inferred viewpoints, or fake anatomy scores.
        references = self._run_stage(
            "reference_quality",
            (reference_digests, reference_options),
            lambda: inspect_references(
                image_path, face_image=face_image, back_image=back_image,
                left_image=left_image, right_image=right_image,
                full_body=full_body, output_dir=output_dir,
            ),
        )
        results["stages"]["reference_quality"] = references
        if references.get("status") != "complete":
            return self._fail(
                results, "reference_quality",
                "; ".join(references.get("errors") or ["Invalid source references"]),
            )

        # Full-body reconstruction consumes the same alpha as InstantMesh.
        # Do not reinterpret opaque backgrounds as geometry, and do not use
        # a fabricated white silhouette if ISNet fails.
        reconstruction_image = image_path
        if full_body:
            try:
                alpha = self._run_stage(
                    "person_alpha",
                    (reference_digests["front"],),
                    lambda: create_person_alpha(
                        image_path, str(pathlib.Path(output_dir) / "person_alpha"),
                    ),
                )
            except Exception as exc:
                return self._fail(results, "person_alpha", str(exc))
            results["stages"]["person_alpha"] = alpha
            if alpha.get("status") != "complete" or not pathlib.Path(alpha.get("rgba_png") or "").is_file():
                return self._fail(results, "person_alpha", alpha.get("error", "missing foreground RGBA"))
            reconstruction_image = alpha["rgba_png"]

        # 1. Detect 28 facial landmarks from the dedicated face image.
        # The source for TripoSR remains the complete front-body image.
        gate = self._run_stage(
            "input_gate",
            (input_digest(face_image or image_path),),
            lambda: validate_input(face_image or image_path, output_dir),
        )
        results["stages"]["input_gate"] = gate
        if gate.get("status") != "complete" or not gate.get("valid"):
            reasons = gate.get("errors") or gate.get("error") or "input rejected"
            if isinstance(reasons, list):
                reasons = "; ".join(str(reason) for reason in reasons)
            return self._fail(results, "input_gate", str(reasons))
        landmarks = gate["landmarks"]

        # Separate single-model child processes; no concurrent GPU weights.
        depth = None
        if full_body:
            try:
                depth = self._run_stage(
                    "relative_depth",
                    (reference_digests,),
                    lambda: estimate_depth(
                        image_path, back_image, left_image, right_image,
                        str(pathlib.Path(output_dir) / "depth"),
                    ),
                )
            except Exception as exc:
                return self._fail(results, "relative_depth", str(exc))
            results["stages"]["relative_depth"] = depth
            if depth.get("status") != "complete" or not pathlib.Path(depth.get("depth_manifest") or "").is_file():
                return self._fail(results, "relative_depth", depth.get("error", "depth manifest missing"))

        # 2. Real input reconstruction. No canonical fallback is permitted.
        reconstruction_dir = str(pathlib.Path(output_dir) / "reconstruction")
        def reconstruct_stage() -> Dict[str, Any]:
            try:
                mesh_path = reconstruct_avatar(
                    reconstruction_image,
                    reconstruction_dir,
                    profile=profile,
                    model_save_format=model_save_format,
                    remove_background=False if full_body else remove_background,
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
            (reference_digests["front"], reconstruction_image, reconstruction_options),
            reconstruct_stage,
        )
        results["stages"]["reference_reconstruction"] = reconstruction
        if reconstruction.get("status") != "complete":
            return self._fail(results, "reference_reconstruction", reconstruction.get("error", "TripoSR failed"))
        reference_mesh = reconstruction["mesh_path"]

        constraints_path = None
        observed_texture_sources = {}
        if full_body:
            # The commercial path must never require Zero123++, nvdiffrast,
            # Nvidia-proprietary LRM code, or CC-BY-NC model weights.
            # Reconstruct true user-supplied views serially using MIT TripoSR.
            supplied_views = {
                "back": back_image, "left": left_image, "right": right_image,
            }
            try:
                multiview = self._run_stage(
                    "licensed_multiview",
                    (reference_mesh, reference_digests, profile),
                    lambda: reconstruct_licensed_multiview(
                        reference_mesh, supplied_views,
                        str(pathlib.Path(output_dir) / "licensed_multiview"),
                        profile=profile,
                    ),
                )
            except Exception as exc:
                return self._fail(results, "licensed_multiview", str(exc))
            results["stages"]["licensed_multiview"] = multiview
            if (multiview.get("status") != "complete"
                    or not pathlib.Path(multiview.get("mesh_obj") or "").is_file()
                    or not pathlib.Path(multiview.get("provenance_json") or "").is_file()):
                return self._fail(
                    results, "licensed_multiview",
                    multiview.get("error", "licensed view mesh/provenance missing"),
                )
            # Reuse the same segmentation output for UV texture. Projecting
            # original opaque side photos would paint their backgrounds into
            # shoulders, arms, hair strands and garment seams.
            try:
                provenance = json.loads(pathlib.Path(
                    multiview["provenance_json"]).read_text(encoding="utf-8"))
                if provenance.get("contract") != "vtuber-commercial-triposr-multiview-v1":
                    raise ValueError("Unexpected commercially licensed texture provenance")
                for role, original in supplied_views.items():
                    if original is None:
                        continue
                    evidence = provenance.get("views", {}).get(role, {})
                    normalized = evidence.get("segmented_rgba")
                    if (pathlib.Path(evidence.get("input_image") or "").resolve()
                            != pathlib.Path(original).resolve()
                            or not isinstance(normalized, str)
                            or not pathlib.Path(normalized).is_file()):
                        raise ValueError(f"{role}: observed foreground cutout is missing")
                    observed_texture_sources[role] = normalized
            except (OSError, ValueError, KeyError, TypeError) as exc:
                return self._fail(results, "licensed_multiview", str(exc))

            try:
                aligned = self._run_stage(
                    "multiview_alignment",
                    (reference_mesh, multiview["mesh_obj"],
                     multiview["provenance_json"], depth["depth_manifest"],
                     references["report_path"]),
                    lambda: align_sources(
                        reference_mesh, multiview["mesh_obj"],
                        depth["depth_manifest"], references["report_path"],
                        str(pathlib.Path(output_dir) / "alignment"),
                        source_metadata=multiview["provenance_json"],
                    ),
                )
            except Exception as exc:
                return self._fail(results, "multiview_alignment", str(exc))
            results["stages"]["multiview_alignment"] = aligned
            if (aligned.get("status") != "complete"
                    or not pathlib.Path(aligned.get("constraints_json") or "").is_file()):
                return self._fail(
                    results, "multiview_alignment",
                    aligned.get("error", "registered licensed geometry missing"),
                )
            constraints_path = aligned["constraints_json"]

        # 3. Fit one stable CC0-derived canonical topology to the reference.
        try:
            template_path = str(get_template_path())
        except Exception as exc:
            return self._fail(results, "template_fitting", f"canonical template unavailable: {exc}")

        fitting = self._run_stage(
            "template_fitting",
            (template_path, reference_mesh, landmarks, fitting_cfg, constraints_path),
            lambda: fit_template(
                template_path,
                landmarks,
                output_dir,
                fitting_cfg,
                reference_mesh_path=reference_mesh,
                **({"reference_constraints_json": constraints_path}
                   if constraints_path is not None else {}),
            ),
        )
        results["stages"]["template_fitting"] = fitting
        if fitting.get("status") != "complete":
            return self._fail(results, "template_fitting", fitting.get("error", "template fitting failed"))
        fitted_mesh = fitting.get("fitted_mesh")
        if not fitted_mesh or not pathlib.Path(fitted_mesh).is_file():
            return self._fail(results, "template_fitting", "fitted mesh artifact is missing")
        results["fitted_mesh"] = fitted_mesh

        # 3b. Apply bounded multiview surface corrections to the canonical
        # vertex topology. No TripoSR/InstantMesh mesh substitution is allowed.
        if full_body:
            from vtuber_pipeline.avatar.surface_refine import refine_anatomy
            try:
                refined = self._run_stage(
                    "surface_refine",
                    (fitted_mesh, constraints_path, references["report_path"],
                     input_digest(reconstruction_image), observed_texture_sources),
                    lambda: refine_anatomy(
                        fitted_mesh, constraints_path, references["report_path"],
                        str(pathlib.Path(output_dir) / "surface_refine"),
                        front_rgba_path=reconstruction_image,
                        observed_rgba_by_role=observed_texture_sources,
                    ),
                )
            except Exception as exc:
                return self._fail(results, "surface_refine", str(exc))
            results["stages"]["surface_refine"] = refined
            surface_path = refined.get("refined_glb")
            hair_path = refined.get("hair_geometry_glb")
            if refined.get("status") != "complete" or not surface_path or not pathlib.Path(surface_path).is_file():
                return self._fail(results, "surface_refine", refined.get("error", "refined anatomical GLB missing"))
            if not hair_path or not pathlib.Path(hair_path).is_file():
                return self._fail(results, "surface_refine", "separate hair ribbons are missing")
            fitted_mesh = surface_path
            results["refined_mesh"] = surface_path
            results["hair_geometry_glb"] = hair_path

        # 4. Project source appearance onto the fitted canonical topology.
        texture = self._run_stage(
            "texture_transfer",
            (reference_digests, observed_texture_sources,
             fitted_mesh, gate.get("bbox"), texture_size, full_body),
            lambda: transfer_texture(
                reconstruction_image if full_body else image_path,
                fitted_mesh,
                output_dir,
                face_bbox=gate.get("bbox"),
                face_image_path=face_image,
                back_image_path=observed_texture_sources.get("back") if full_body else back_image,
                **({"left_image_path": observed_texture_sources["left"]}
                   if full_body and "left" in observed_texture_sources else
                   {"left_image_path": left_image} if left_image else {}),
                **({"right_image_path": observed_texture_sources["right"]}
                   if full_body and "right" in observed_texture_sources else
                   {"right_image_path": right_image} if right_image else {}),
                full_body=full_body,
                texture_size=texture_size,
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
                    **({"hair_mesh_path": results["hair_geometry_glb"]}
                       if full_body else {}),
                )
                return {"status": "complete", "rigged_mesh": path, "output_path": path}
            except Exception as exc:
                return {"status": "error", "error": str(exc)}

        rig = self._run_stage(
            "rig",
            (fitted_mesh, texture_path, uv_path, results.get("hair_geometry_glb")),
            rig_stage,
        )
        results["stages"]["rig"] = rig
        if rig.get("status") != "complete":
            return self._fail(results, "rig", rig.get("error", "rigging failed"))
        rigged_mesh = rig["rigged_mesh"]

        # Optional real SkinTokens skin-only enhancement runs after our canonical
        # VRM skeleton is built. Its output is promoted ONLY if exact geometry,
        # UVs, node palette and hair binding contracts remain valid. There is no
        # silent fall-back when the user explicitly selected this provider.
        if rigging_provider == "skintokens":
            try:
                from vtuber_pipeline.avatar.skintokens_bridge import (
                    runtime_identity, run_skintokens_skin_only,
                )
                skintokens_identity = runtime_identity()
            except Exception as exc:
                return self._fail(results, "skintokens_skin", str(exc))
            skintokens = self._run_stage(
                "skintokens_skin",
                (rigged_mesh, skintokens_identity),
                lambda: run_skintokens_skin_only(
                    rigged_mesh, str(pathlib.Path(output_dir) / "skintokens"),
                    identity=skintokens_identity,
                ),
            )
            results["stages"]["skintokens_skin"] = skintokens
            if (skintokens.get("status") != "complete"
                    or not pathlib.Path(skintokens.get("rigged_mesh") or "").is_file()):
                return self._fail(results, "skintokens_skin",
                                  skintokens.get("error") or "SkinTokens produced no validated rig")
            rigged_mesh = skintokens["rigged_mesh"]
            results["rigged_mesh"] = rigged_mesh

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

        # The pure exporter is an intermediate serialization step. Final
        # broadcast VRM MUST survive native Blender skin/shape-key validation.
        blender = self._run_stage(
            "blender_vrm_export", (vrm_path,),
            lambda: export_blender_from_vrm(vrm_path, output_dir),
        )
        results["stages"]["blender_vrm_export"] = blender
        if blender.get("status") != "complete":
            return self._fail(results, "blender_vrm_export",
                              blender.get("error", "native Blender export failed"))
        vrm_path = blender["vrm_path"]
        results["blend_path"] = blender["blend"]

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

        # MD 6.10: write the SAME validated production-result contract as the
        # Inochi2D and Live2D routes. No invalid .vrm may be marked complete.
        from vtuber_pipeline.common.schemas import BuildResult
        try:
            completion = BuildResult(
                mode="3d", status="complete",
                primary_file=vrm_path,
                editable_file=results.get("blend_path"),
                intermediate_dir=output_dir,
            )
            completion_path = completion.write(output_dir)
        except Exception as exc:
            return self._fail(results, "completion_contract", str(exc))
        results["status"] = "complete"
        results["vrm_path"] = vrm_path
        results["validation"] = validation
        results["production_result_json"] = completion_path
        results["build_result"] = completion.__dict__
        return results


def build_avatar(
    image_path: str,
    output_dir: str,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build one avatar through the fail-closed mainline."""
    return AvatarPipeline(output_dir, config).build(image_path)
