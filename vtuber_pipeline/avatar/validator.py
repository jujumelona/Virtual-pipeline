"""Strict product-level validation for generated VRM 1.0 avatars."""

import pathlib
from typing import Dict, Any, Optional

from pygltflib import GLTF2


REQUIRED_BONES = [
    "hips", "spine", "chest", "neck", "head",
    "leftShoulder", "leftUpperArm", "leftLowerArm", "leftHand",
    "rightShoulder", "rightUpperArm", "rightLowerArm", "rightHand",
    "leftUpperLeg", "leftLowerLeg", "leftFoot",
    "rightUpperLeg", "rightLowerLeg", "rightFoot",
]
REQUIRED_EXPRESSIONS = [
    "happy", "angry", "sad", "relaxed", "surprised",
    "aa", "ih", "ou", "ee", "oh",
    "blink", "blinkLeft", "blinkRight",
]


class VRMValidator:
    """Validate both VRM schema structure and this product contract."""

    def __init__(self, vrm_path: str):
        self.vrm_path = pathlib.Path(vrm_path)
        self._gltf: Optional[GLTF2] = None
        self._vrm: Dict[str, Any] = {}

    def parse_vrm(self) -> Dict[str, Any]:
        if self._gltf is not None:
            return self._vrm
        self._gltf = GLTF2().load(str(self.vrm_path))
        extensions = self._gltf.extensions or {}
        self._vrm = extensions.get("VRMC_vrm", {}) if isinstance(extensions, dict) else {}
        if not isinstance(self._vrm, dict):
            self._vrm = {}
        return self._vrm

    def validate_vrm_schema(self) -> Dict[str, Any]:
        vrm = self.parse_vrm()
        version = vrm.get("specVersion") if vrm else None
        valid = version == "1.0"
        return {
            "valid": valid, "spec_version": version,
            "error": None if valid else "VRMC_vrm specVersion must be 1.0",
        }

    def validate_humanoid_bones(self) -> Dict[str, Any]:
        vrm = self.parse_vrm()
        bones = (vrm.get("humanoid") or {}).get("humanBones") or {}
        node_count = len(self._gltf.nodes or []) if self._gltf else 0
        present = []
        invalid_nodes = []
        for name, binding in bones.items() if isinstance(bones, dict) else []:
            node = binding.get("node") if isinstance(binding, dict) else None
            if isinstance(node, int) and 0 <= node < node_count:
                present.append(name)
            else:
                invalid_nodes.append(name)
        missing = [name for name in REQUIRED_BONES if name not in present]
        valid = not missing and not invalid_nodes
        return {
            "valid": valid, "present": present, "missing": missing,
            "invalid_nodes": invalid_nodes,
            "error": None if valid else f"Missing/invalid humanoid bones: {missing + invalid_nodes}",
        }

    def _validate_morph_bind(self, bind: Dict[str, Any]) -> bool:
        if self._gltf is None:
            return False
        node_idx = bind.get("node")
        target_idx = bind.get("index")
        if not isinstance(node_idx, int) or not (0 <= node_idx < len(self._gltf.nodes or [])):
            return False
        node = self._gltf.nodes[node_idx]
        mesh_idx = getattr(node, "mesh", None)
        if not isinstance(mesh_idx, int) or not (0 <= mesh_idx < len(self._gltf.meshes or [])):
            return False
        mesh = self._gltf.meshes[mesh_idx]
        if not mesh.primitives:
            return False
        targets = mesh.primitives[0].targets or []
        return isinstance(target_idx, int) and 0 <= target_idx < len(targets)

    def validate_expressions(self) -> Dict[str, Any]:
        vrm = self.parse_vrm()
        presets = ((vrm.get("expressions") or {}).get("preset") or {}) if vrm else {}
        present = []
        invalid_binds = []
        if isinstance(presets, dict):
            for name, expr in presets.items():
                binds = expr.get("morphTargetBinds", []) if isinstance(expr, dict) else []
                if binds and all(self._validate_morph_bind(bind) for bind in binds):
                    present.append(name)
                else:
                    invalid_binds.append(name)
        missing = [name for name in REQUIRED_EXPRESSIONS if name not in present]
        valid = not missing and not invalid_binds
        return {
            "valid": valid, "present": present, "missing": missing,
            "invalid_binds": invalid_binds,
            "error": None if valid else f"Missing/invalid expression binds: {sorted(set(missing + invalid_binds))}",
        }

    def validate_materials(self) -> Dict[str, Any]:
        if self._gltf is None:
            self.parse_vrm()
        gltf = self._gltf
        valid = bool(gltf and gltf.materials and gltf.textures and gltf.images)
        return {
            "valid": valid,
            "material_count": len(gltf.materials or []) if gltf else 0,
            "texture_count": len(gltf.textures or []) if gltf else 0,
            "image_count": len(gltf.images or []) if gltf else 0,
            "error": None if valid else "Embedded avatar material/texture/image is missing",
        }

    def validate_skinning(self) -> Dict[str, Any]:
        if self._gltf is None:
            self.parse_vrm()
        gltf = self._gltf
        has_skin = bool(gltf and gltf.skins)
        has_weights = False
        if gltf:
            for mesh in gltf.meshes or []:
                for primitive in mesh.primitives or []:
                    attrs = primitive.attributes
                    if (
                        getattr(attrs, "JOINTS_0", None) is not None and
                        getattr(attrs, "WEIGHTS_0", None) is not None
                    ):
                        has_weights = True
                        break
        valid = has_skin and has_weights
        return {
            "valid": valid, "skin": has_skin, "joint_weights": has_weights,
            "error": None if valid else "Skin or JOINTS_0/WEIGHTS_0 is missing",
        }

    def validate_look_at(self) -> Dict[str, Any]:
        vrm = self.parse_vrm()
        look_at = vrm.get("lookAt") or {}
        kind = look_at.get("type")
        offset = look_at.get("offsetFromHeadBone")
        valid = kind in {"bone", "expression"} and isinstance(offset, list) and len(offset) == 3
        return {
            "valid": valid, "type": kind, "offset": offset,
            "error": None if valid else "lookAt requires valid type and 3D offsetFromHeadBone",
        }

    def validate_springbone(self) -> Dict[str, Any]:
        if self._gltf is None:
            self.parse_vrm()
        extensions = self._gltf.extensions or {} if self._gltf else {}
        spring = extensions.get("VRMC_springBone", {}) if isinstance(extensions, dict) else {}
        springs = spring.get("springs", []) if isinstance(spring, dict) else []
        node_count = len(self._gltf.nodes or []) if self._gltf else 0
        valid_springs = []
        errors = []
        for index, item in enumerate(springs if isinstance(springs, list) else []):
            joints = item.get("joints", []) if isinstance(item, dict) else []
            if len(joints) < 2:
                errors.append(f"spring[{index}] has fewer than 2 joints")
                continue
            bad = []
            for joint in joints:
                node = joint.get("node") if isinstance(joint, dict) else None
                required = ("hitRadius", "stiffness", "gravityPower", "gravityDir", "dragForce")
                if (
                    not isinstance(node, int) or not (0 <= node < node_count) or
                    any(field not in joint for field in required)
                ):
                    bad.append(node)
            if bad:
                errors.append(f"spring[{index}] has invalid joints: {bad}")
            else:
                valid_springs.append(item.get("name", f"spring_{index}"))
        valid = bool(valid_springs) and not errors
        return {
            "valid": valid, "groups": valid_springs, "errors": errors,
            "error": None if valid else ("; ".join(errors) or "No valid SpringBone chain"),
        }

    def run_all(self) -> Dict[str, Any]:
        checks = {
            "vrm_schema": self.validate_vrm_schema(),
            "humanoid_bones": self.validate_humanoid_bones(),
            "expressions": self.validate_expressions(),
            "materials": self.validate_materials(),
            "skinning": self.validate_skinning(),
            "look_at": self.validate_look_at(),
            "springbone": self.validate_springbone(),
        }
        passed = all(check.get("valid", False) for check in checks.values())
        return {
            "status": "complete" if passed else "error",
            "vrm_path": str(self.vrm_path),
            "passed": passed,
            "checks": checks,
        }


def validate_vrm(vrm_path: str, output_dir: str) -> Dict[str, Any]:
    """Run strict validation and persist validation/report.json."""
    report_dir = pathlib.Path(output_dir) / "validation"
    report_dir.mkdir(parents=True, exist_ok=True)
    path = pathlib.Path(vrm_path)
    if not path.is_file() or path.stat().st_size == 0:
        result = {
            "status": "error", "vrm_path": vrm_path, "passed": False,
            "checks": {"file_exists": {"valid": False}},
            "error": f"VRM file missing or empty: {vrm_path}",
        }
    else:
        try:
            result = VRMValidator(vrm_path).run_all()
        except Exception as exc:
            result = {
                "status": "error", "vrm_path": vrm_path, "passed": False,
                "checks": {}, "error": str(exc),
            }
    _write_validation_report(report_dir, result)
    return result


def generate_validation_report(vrm_path: str, output_dir: str) -> str:
    validate_vrm(vrm_path, output_dir)
    return str(pathlib.Path(output_dir) / "validation" / "report.json")


def _write_validation_report(report_dir: pathlib.Path, result: Dict[str, Any]) -> None:
    from vtuber_pipeline.core.utils import save_json
    save_json(result, str(report_dir / "report.json"))
