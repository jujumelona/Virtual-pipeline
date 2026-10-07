"""VRM 1.0 validation for generated avatars and accessory-preserved VRMs."""

import pathlib
from typing import Dict, Any, Optional

import numpy as np
from pygltflib import GLTF2


OFFICIAL_REQUIRED_BONES = [
    "hips", "spine", "head",
    "leftUpperLeg", "leftLowerLeg", "leftFoot",
    "rightUpperLeg", "rightLowerLeg", "rightFoot",
    "leftUpperArm", "leftLowerArm", "leftHand",
    "rightUpperArm", "rightLowerArm", "rightHand",
]

PRODUCT_REQUIRED_BONES = [
    "hips", "spine", "chest", "neck", "head",
    "leftEye", "rightEye",
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
    """Validate VRM/glTF plus an optional stricter product contract."""

    def __init__(self, vrm_path: str, *, product_contract: bool = True):
        self.vrm_path = pathlib.Path(vrm_path)
        self.product_contract = bool(product_contract)
        self._gltf: Optional[GLTF2] = None
        self._vrm: Dict[str, Any] = {}

    def parse_vrm(self) -> Dict[str, Any]:
        if self._gltf is not None:
            return self._vrm
        self._gltf = GLTF2().load(str(self.vrm_path))
        extensions = self._gltf.extensions or {}
        self._vrm = (
            extensions.get("VRMC_vrm", {})
            if isinstance(extensions, dict)
            else {}
        )
        if not isinstance(self._vrm, dict):
            self._vrm = {}
        return self._vrm

    def validate_gltf_structure(self) -> Dict[str, Any]:
        """Run pygltflib structural checks before VRM-specific validation."""
        if self._gltf is None:
            self.parse_vrm()
        try:
            from pygltflib.validator import validate as validate_gltf

            validate_gltf(self._gltf)
            return {"valid": True, "error": None}
        except Exception as exc:
            return {"valid": False, "error": str(exc)}

    def validate_vrm_schema(self) -> Dict[str, Any]:
        vrm = self.parse_vrm()
        version = vrm.get("specVersion") if vrm else None
        meta = vrm.get("meta") if isinstance(vrm, dict) else None
        humanoid = vrm.get("humanoid") if isinstance(vrm, dict) else None

        meta_valid = (
            isinstance(meta, dict)
            and isinstance(meta.get("name"), str)
            and bool(meta.get("name"))
            and isinstance(meta.get("authors"), list)
            and bool(meta.get("authors"))
            and all(
                isinstance(author, str) and author
                for author in meta["authors"]
            )
            and isinstance(meta.get("licenseUrl"), str)
            and bool(meta.get("licenseUrl"))
            and meta.get("avatarPermission", "onlyAuthor")
                in {
                    "onlyAuthor",
                    "onlySeparatelyLicensedPerson",
                    "everyone",
                }
            and meta.get("commercialUsage", "personalNonProfit")
                in {
                    "personalNonProfit",
                    "personalProfit",
                    "corporation",
                }
            and meta.get("creditNotation", "required")
                in {"required", "unnecessary"}
            and meta.get("modification", "prohibited")
                in {
                    "prohibited",
                    "allowModification",
                    "allowModificationRedistribution",
                }
        )
        valid = (
            version == "1.0"
            and meta_valid
            and isinstance(humanoid, dict)
        )
        return {
            "valid": valid,
            "spec_version": version,
            "meta_valid": meta_valid,
            "error": (
                None
                if valid
                else "VRMC_vrm requires specVersion=1.0, valid meta, and humanoid"
            ),
        }

    def validate_humanoid_bones(self) -> Dict[str, Any]:
        vrm = self.parse_vrm()
        bones = (vrm.get("humanoid") or {}).get("humanBones") or {}
        node_count = len(self._gltf.nodes or []) if self._gltf else 0

        present = []
        invalid_nodes = []
        duplicate_nodes = []
        used_nodes = {}

        for name, binding in bones.items() if isinstance(bones, dict) else []:
            node = binding.get("node") if isinstance(binding, dict) else None
            if isinstance(node, int) and 0 <= node < node_count:
                present.append(name)
                if node in used_nodes:
                    duplicate_nodes.append((used_nodes[node], name, node))
                else:
                    used_nodes[node] = name
            else:
                invalid_nodes.append(name)

        required = (
            PRODUCT_REQUIRED_BONES
            if self.product_contract
            else OFFICIAL_REQUIRED_BONES
        )
        missing = [name for name in required if name not in present]
        valid = not missing and not invalid_nodes and not duplicate_nodes
        return {
            "valid": valid,
            "present": present,
            "missing": missing,
            "invalid_nodes": invalid_nodes,
            "duplicate_nodes": duplicate_nodes,
            "error": (
                None
                if valid
                else "Missing/invalid/duplicate humanoid bones"
            ),
        }

    def validate_humanoid_rest_pose(self) -> Dict[str, Any]:
        """Validate product hierarchy and T-pose geometry."""
        if not self.product_contract:
            return {"valid": True, "skipped": True, "error": None}
        vrm = self.parse_vrm()
        bones = (vrm.get("humanoid") or {}).get("humanBones") or {}
        if not isinstance(bones, dict):
            return {"valid": False, "error": "humanBones must be an object"}

        node_for = {
            name: binding.get("node")
            for name, binding in bones.items()
            if isinstance(binding, dict)
            and isinstance(binding.get("node"), int)
        }
        nodes = self._gltf.nodes or [] if self._gltf else []
        parent_of: Dict[int, int] = {}
        for parent_idx, node in enumerate(nodes):
            for child in node.children or []:
                if child in parent_of:
                    return {
                        "valid": False,
                        "error": f"node {child} has multiple parents",
                    }
                parent_of[int(child)] = parent_idx

        expected_parent = {
            "spine": "hips",
            "chest": "spine",
            "upperChest": "chest",
            "neck": "upperChest",
            "head": "neck",
            "leftEye": "head",
            "rightEye": "head",
            "leftShoulder": "upperChest",
            "leftUpperArm": "leftShoulder",
            "leftLowerArm": "leftUpperArm",
            "leftHand": "leftLowerArm",
            "rightShoulder": "upperChest",
            "rightUpperArm": "rightShoulder",
            "rightLowerArm": "rightUpperArm",
            "rightHand": "rightLowerArm",
            "leftUpperLeg": "hips",
            "leftLowerLeg": "leftUpperLeg",
            "leftFoot": "leftLowerLeg",
            "rightUpperLeg": "hips",
            "rightLowerLeg": "rightUpperLeg",
            "rightFoot": "rightLowerLeg",
        }
        bad_hierarchy = []
        for child_name, parent_name in expected_parent.items():
            child_idx = node_for.get(child_name)
            parent_idx = node_for.get(parent_name)
            if child_idx is None or parent_idx is None:
                bad_hierarchy.append(f"{child_name}->{parent_name}:missing")
                continue
            if parent_of.get(child_idx) != parent_idx:
                bad_hierarchy.append(f"{child_name}->{parent_name}")

        def local_matrix(node):
            matrix = np.eye(4, dtype=float)
            if getattr(node, "matrix", None):
                raw = np.asarray(node.matrix, dtype=float).reshape(4, 4).T
                return raw
            translation = np.asarray(
                node.translation or [0.0, 0.0, 0.0],
                dtype=float,
            )
            scale = np.asarray(
                node.scale or [1.0, 1.0, 1.0],
                dtype=float,
            )
            x, y, z, w = [
                float(v)
                for v in (node.rotation or [0.0, 0.0, 0.0, 1.0])
            ]
            rotation = np.array([
                [1 - 2*y*y - 2*z*z, 2*x*y - 2*z*w, 2*x*z + 2*y*w],
                [2*x*y + 2*z*w, 1 - 2*x*x - 2*z*z, 2*y*z - 2*x*w],
                [2*x*z - 2*y*w, 2*y*z + 2*x*w, 1 - 2*x*x - 2*y*y],
            ])
            matrix[:3, :3] = rotation @ np.diag(scale)
            matrix[:3, 3] = translation
            return matrix

        children = {i: list(node.children or []) for i, node in enumerate(nodes)}
        roots = [i for i in range(len(nodes)) if i not in parent_of]
        worlds = [np.eye(4, dtype=float) for _ in nodes]

        def visit(index: int, parent_world: np.ndarray) -> None:
            worlds[index] = parent_world @ local_matrix(nodes[index])
            for child in children[index]:
                visit(int(child), worlds[index])

        for root in roots:
            visit(root, np.eye(4, dtype=float))

        positions = {
            name: worlds[index][:3, 3]
            for name, index in node_for.items()
            if 0 <= index < len(worlds)
        }
        required_position_names = [
            "hips", "head",
            "leftShoulder", "leftUpperArm", "leftLowerArm", "leftHand",
            "rightShoulder", "rightUpperArm", "rightLowerArm", "rightHand",
        ]
        missing_positions = [
            name for name in required_position_names
            if name not in positions
        ]

        pose_errors = []
        if not missing_positions:
            body_height = max(
                float(abs(positions["head"][1] - positions["hips"][1])),
                1e-6,
            )
            left_chain = [
                positions["leftShoulder"],
                positions["leftUpperArm"],
                positions["leftLowerArm"],
                positions["leftHand"],
            ]
            right_chain = [
                positions["rightShoulder"],
                positions["rightUpperArm"],
                positions["rightLowerArm"],
                positions["rightHand"],
            ]
            max_y_spread = 0.06 * body_height
            if np.ptp([p[1] for p in left_chain]) > max_y_spread:
                pose_errors.append("left arm is not in T-pose")
            if np.ptp([p[1] for p in right_chain]) > max_y_spread:
                pose_errors.append("right arm is not in T-pose")
            if not (
                positions["leftHand"][0] > positions["leftShoulder"][0]
            ):
                pose_errors.append("left arm does not extend toward +X")
            if not (
                positions["rightHand"][0] < positions["rightShoulder"][0]
            ):
                pose_errors.append("right arm does not extend toward -X")

        valid = not bad_hierarchy and not missing_positions and not pose_errors
        return {
            "valid": valid,
            "bad_hierarchy": bad_hierarchy,
            "missing_positions": missing_positions,
            "pose_errors": pose_errors,
            "error": (
                None
                if valid
                else "Invalid humanoid hierarchy/rest pose"
            ),
        }

    def _validate_morph_bind(self, bind: Dict[str, Any]) -> bool:
        if self._gltf is None:
            return False
        node_idx = bind.get("node")
        target_idx = bind.get("index")
        weight = bind.get("weight", 1.0)

        if (
            not isinstance(node_idx, int)
            or not (0 <= node_idx < len(self._gltf.nodes or []))
        ):
            return False
        if not isinstance(weight, (int, float)) or not (0.0 <= float(weight) <= 1.0):
            return False

        node = self._gltf.nodes[node_idx]
        mesh_idx = getattr(node, "mesh", None)
        if (
            not isinstance(mesh_idx, int)
            or not (0 <= mesh_idx < len(self._gltf.meshes or []))
        ):
            return False

        mesh = self._gltf.meshes[mesh_idx]
        if not mesh.primitives:
            return False
        targets = mesh.primitives[0].targets or []
        return (
            isinstance(target_idx, int)
            and 0 <= target_idx < len(targets)
        )

    def validate_expressions(self) -> Dict[str, Any]:
        vrm = self.parse_vrm()
        expressions = vrm.get("expressions") if vrm else None
        presets = (
            (expressions or {}).get("preset") or {}
            if isinstance(expressions, dict)
            else {}
        )

        # VRM expressions are optional at the specification level.
        if not self.product_contract and not expressions:
            return {
                "valid": True,
                "present": [],
                "missing": [],
                "invalid_binds": [],
                "optional_absent": True,
                "error": None,
            }

        present = []
        invalid_binds = []

        if isinstance(presets, dict):
            for name, expr in presets.items():
                if not isinstance(expr, dict):
                    invalid_binds.append(name)
                    continue

                morph_binds = expr.get("morphTargetBinds")
                material_binds = expr.get("materialColorBinds")
                texture_binds = expr.get("textureTransformBinds")

                if morph_binds is not None:
                    valid_morphs = (
                        isinstance(morph_binds, list)
                        and len(morph_binds) > 0
                        and all(
                            isinstance(bind, dict)
                            and self._validate_morph_bind(bind)
                            for bind in morph_binds
                        )
                    )
                    if not valid_morphs:
                        invalid_binds.append(name)
                        continue
                elif self.product_contract:
                    # Our required product presets are morph-driven.
                    invalid_binds.append(name)
                    continue
                elif not material_binds and not texture_binds:
                    # A spec-level expression may be empty, but if present
                    # without any bind it contributes nothing; keep it valid.
                    pass

                present.append(name)

        missing = (
            [name for name in REQUIRED_EXPRESSIONS if name not in present]
            if self.product_contract
            else []
        )
        valid = not missing and not invalid_binds
        return {
            "valid": valid,
            "present": present,
            "missing": missing,
            "invalid_binds": invalid_binds,
            "error": (
                None
                if valid
                else f"Missing/invalid expression binds: "
                     f"{sorted(set(missing + invalid_binds))}"
            ),
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
            "error": (
                None
                if valid
                else "Embedded avatar material/texture/image is missing"
            ),
        }

    def _read_dense_accessor(self, accessor_index: int) -> np.ndarray:
        """Read a dense embedded-buffer accessor without changing its ordering."""
        if self._gltf is None:
            self.parse_vrm()
        gltf = self._gltf
        accessor = gltf.accessors[accessor_index]
        if accessor.sparse is not None:
            raise ValueError("Sparse JOINTS_0/WEIGHTS_0 accessors are unsupported")
        if accessor.bufferView is None:
            raise ValueError("Accessor has no bufferView")
        view = gltf.bufferViews[accessor.bufferView]
        if view.buffer not in (0, None):
            raise ValueError("Skin accessor must use embedded buffer 0")
        blob = gltf.binary_blob()
        if blob is None:
            raise ValueError("VRM has no embedded binary buffer")

        component_map = {
            5121: (np.uint8, 1),
            5123: (np.dtype("<u2"), 2),
            5125: (np.dtype("<u4"), 4),
            5126: (np.dtype("<f4"), 4),
        }
        if accessor.componentType not in component_map:
            raise ValueError(
                f"Unsupported accessor componentType: {accessor.componentType}"
            )
        dtype, component_size = component_map[accessor.componentType]
        component_count = {
            "SCALAR": 1,
            "VEC2": 2,
            "VEC3": 3,
            "VEC4": 4,
            "MAT4": 16,
        }.get(accessor.type)
        if component_count is None:
            raise ValueError(f"Unsupported accessor type: {accessor.type}")

        element_size = component_size * component_count
        stride = int(view.byteStride or element_size)
        if stride < element_size:
            raise ValueError("Accessor byteStride is smaller than element size")

        base = int(view.byteOffset or 0) + int(accessor.byteOffset or 0)
        end = base + stride * max(int(accessor.count) - 1, 0) + element_size
        if base < 0 or end > len(blob):
            raise ValueError("Accessor exceeds embedded binary buffer")

        rows = np.empty(
            (int(accessor.count), component_count),
            dtype=dtype,
        )
        for row in range(int(accessor.count)):
            offset = base + row * stride
            rows[row] = np.frombuffer(
                blob,
                dtype=dtype,
                count=component_count,
                offset=offset,
            )
        return rows

    def validate_skinning(self) -> Dict[str, Any]:
        if self._gltf is None:
            self.parse_vrm()
        gltf = self._gltf
        if not gltf or not gltf.skins:
            return {
                "valid": False,
                "skin": False,
                "joint_weights": False,
                "hair_shell": False,
                "error": "VRM has no skin",
            }

        if len(gltf.skins) != 1:
            return {
                "valid": False,
                "skin": True,
                "joint_weights": False,
                "hair_shell": False,
                "error": f"Expected one avatar skin, found {len(gltf.skins)}",
            }

        target = None
        for mesh in gltf.meshes or []:
            for primitive in mesh.primitives or []:
                attrs = primitive.attributes
                joints_idx = getattr(attrs, "JOINTS_0", None)
                weights_idx = getattr(attrs, "WEIGHTS_0", None)
                if joints_idx is not None and weights_idx is not None:
                    if target is not None:
                        return {
                            "valid": False,
                            "skin": True,
                            "joint_weights": False,
                            "hair_shell": False,
                            "error": "Product avatar must use one skinned primitive",
                        }
                    target = (mesh, primitive, joints_idx, weights_idx)

        if target is None:
            return {
                "valid": False,
                "skin": True,
                "joint_weights": False,
                "hair_shell": False,
                "error": "Skin has no JOINTS_0/WEIGHTS_0 primitive",
            }

        mesh, _primitive, joints_idx, weights_idx = target
        joints = self._read_dense_accessor(joints_idx)
        weights = self._read_dense_accessor(weights_idx).astype(np.float64)
        if joints.shape != weights.shape or joints.shape[1] != 4:
            return {
                "valid": False,
                "skin": True,
                "joint_weights": False,
                "hair_shell": False,
                "error": "JOINTS_0/WEIGHTS_0 shape mismatch",
            }
        if not np.all(np.isfinite(weights)):
            return {
                "valid": False,
                "skin": True,
                "joint_weights": False,
                "hair_shell": False,
                "error": "WEIGHTS_0 contains non-finite values",
            }

        sums = weights.sum(axis=1)
        normalized = bool(np.allclose(sums, 1.0, atol=1e-4))
        nonnegative = bool(np.all(weights >= -1e-7))

        skin = gltf.skins[0]
        skin_joints = list(skin.joints or [])
        node_names = [
            (gltf.nodes[node_idx].name or "")
            for node_idx in skin_joints
        ]
        hair_joint_slots = {
            slot
            for slot, name in enumerate(node_names)
            if name.lower().startswith("hair")
        }

        extras = mesh.extras or {}
        hair_start = (
            extras.get("hairVertexStart")
            if isinstance(extras, dict)
            else None
        )
        hair_count = (
            extras.get("hairVertexCount")
            if isinstance(extras, dict)
            else None
        )
        shell_valid = False
        shell_reason = None

        if not isinstance(hair_start, int) or not (0 < hair_start < len(joints)):
            shell_reason = "hairVertexStart metadata is missing or invalid"
        elif hair_count != len(joints) - hair_start:
            shell_reason = "hairVertexCount metadata does not match vertex count"
        elif not hair_joint_slots:
            shell_reason = "Skin contains no secondary hair joints"
        else:
            hair_slot_array = np.asarray(sorted(hair_joint_slots), dtype=joints.dtype)
            body_hair = np.isin(joints[:hair_start], hair_slot_array) & (
                weights[:hair_start] > 1e-6
            )
            shell_hair = np.isin(joints[hair_start:], hair_slot_array) & (
                weights[hair_start:] > 1e-4
            )
            if np.any(body_hair):
                shell_reason = "Canonical body/skull contains SpringBone hair weights"
            elif not np.any(shell_hair):
                shell_reason = "Hair shell has no effective secondary-bone weights"
            else:
                shell_valid = True

        valid = normalized and nonnegative and shell_valid
        return {
            "valid": valid,
            "skin": True,
            "joint_weights": normalized and nonnegative,
            "hair_shell": shell_valid,
            "hair_vertex_start": hair_start,
            "hair_vertex_count": hair_count,
            "error": None if valid else (
                shell_reason
                or "Skin weights are not finite, non-negative and normalized"
            ),
        }

    def validate_look_at(self) -> Dict[str, Any]:
        vrm = self.parse_vrm()
        present = "lookAt" in vrm
        look_at = vrm.get("lookAt") if present else None

        if not self.product_contract and not present:
            return {
                "valid": True,
                "optional_absent": True,
                "error": None,
            }

        if not isinstance(look_at, dict):
            return {"valid": False, "error": "lookAt must be an object"}

        kind = look_at.get("type")
        offset = look_at.get("offsetFromHeadBone")

        if self.product_contract:
            valid = (
                kind == "bone"
                and isinstance(offset, list)
                and len(offset) == 3
                and all(isinstance(v, (int, float)) for v in offset)
            )
        else:
            valid = True
            if kind is not None and kind not in {"bone", "expression"}:
                valid = False
            if offset is not None and (
                not isinstance(offset, list)
                or len(offset) != 3
                or not all(isinstance(v, (int, float)) for v in offset)
            ):
                valid = False

        return {
            "valid": valid,
            "type": kind,
            "offset": offset,
            "error": (
                None
                if valid
                else "Invalid VRMC_vrm lookAt contract"
            ),
        }

    def validate_springbone(self) -> Dict[str, Any]:
        if self._gltf is None:
            self.parse_vrm()

        extensions = self._gltf.extensions or {} if self._gltf else {}
        present = (
            isinstance(extensions, dict)
            and "VRMC_springBone" in extensions
        )

        if not present:
            if self.product_contract:
                return {
                    "valid": False,
                    "groups": [],
                    "errors": ["VRMC_springBone extension is missing"],
                    "error": "VRMC_springBone extension is missing",
                }
            return {
                "valid": True,
                "groups": [],
                "optional_absent": True,
                "errors": [],
                "error": None,
            }

        spring = extensions.get("VRMC_springBone", {})
        if not isinstance(spring, dict) or spring.get("specVersion") != "1.0":
            return {
                "valid": False,
                "groups": [],
                "errors": ["VRMC_springBone specVersion must be 1.0"],
                "error": "VRMC_springBone specVersion must be 1.0",
            }

        errors = []
        for key in ("colliders", "colliderGroups"):
            if key in spring and (
                not isinstance(spring[key], list)
                or len(spring[key]) == 0
            ):
                errors.append(f"{key} must be omitted or contain at least one item")

        springs = spring.get("springs")
        if springs is not None and (
            not isinstance(springs, list) or len(springs) == 0
        ):
            errors.append("springs must be omitted or contain at least one item")
            springs = []

        node_count = len(self._gltf.nodes or []) if self._gltf else 0
        valid_springs = []

        for index, item in enumerate(springs or []):
            if not isinstance(item, dict):
                errors.append(f"spring[{index}] must be an object")
                continue

            joints = item.get("joints", [])
            minimum_joints = 2 if self.product_contract else 1
            if not isinstance(joints, list) or len(joints) < minimum_joints:
                errors.append(
                    f"spring[{index}] has fewer than {minimum_joints} joints"
                )
                continue

            if "colliderGroups" in item and (
                not isinstance(item["colliderGroups"], list)
                or len(item["colliderGroups"]) == 0
            ):
                errors.append(
                    f"spring[{index}].colliderGroups must be omitted or non-empty"
                )

            bad = []
            for joint in joints:
                if not isinstance(joint, dict):
                    bad.append(None)
                    continue

                node = joint.get("node")
                if not isinstance(node, int) or not (0 <= node < node_count):
                    bad.append(node)
                    continue

                gravity_dir = joint.get("gravityDir")
                if gravity_dir is not None and (
                    not isinstance(gravity_dir, list)
                    or len(gravity_dir) != 3
                    or not all(
                        isinstance(value, (int, float))
                        for value in gravity_dir
                    )
                ):
                    bad.append(node)
                    continue

                drag = joint.get("dragForce")
                if drag is not None and (
                    not isinstance(drag, (int, float))
                    or not (0.0 <= float(drag) <= 1.0)
                ):
                    bad.append(node)
                    continue

                for nonnegative in (
                    "hitRadius", "stiffness", "gravityPower"
                ):
                    value = joint.get(nonnegative)
                    if value is not None and (
                        not isinstance(value, (int, float))
                        or float(value) < 0.0
                    ):
                        bad.append(node)
                        break

            if bad:
                errors.append(
                    f"spring[{index}] has invalid joints: {bad}"
                )
            else:
                valid_springs.append(
                    item.get("name", f"spring_{index}")
                )

        if self.product_contract and not valid_springs:
            errors.append("No valid SpringBone chain")

        valid = not errors
        return {
            "valid": valid,
            "groups": valid_springs,
            "errors": errors,
            "error": None if valid else "; ".join(errors),
        }

    def run_all(self) -> Dict[str, Any]:
        checks = {
            "gltf_structure": self.validate_gltf_structure(),
            "vrm_schema": self.validate_vrm_schema(),
            "humanoid_bones": self.validate_humanoid_bones(),
            "humanoid_rest_pose": self.validate_humanoid_rest_pose(),
            "expressions": self.validate_expressions(),
            "look_at": self.validate_look_at(),
            "springbone": self.validate_springbone(),
        }

        if self.product_contract:
            checks["materials"] = self.validate_materials()
            checks["skinning"] = self.validate_skinning()

        passed = all(
            check.get("valid", False)
            for check in checks.values()
        )
        return {
            "status": "complete" if passed else "error",
            "vrm_path": str(self.vrm_path),
            "passed": passed,
            "product_contract": self.product_contract,
            "checks": checks,
        }


def validate_vrm(
    vrm_path: str,
    output_dir: str,
    *,
    product_contract: bool = True,
) -> Dict[str, Any]:
    """Run VRM validation and persist validation/report.json."""
    report_dir = pathlib.Path(output_dir) / "validation"
    report_dir.mkdir(parents=True, exist_ok=True)
    path = pathlib.Path(vrm_path)

    if not path.is_file() or path.stat().st_size == 0:
        result = {
            "status": "error",
            "vrm_path": vrm_path,
            "passed": False,
            "product_contract": product_contract,
            "checks": {"file_exists": {"valid": False}},
            "error": f"VRM file missing or empty: {vrm_path}",
        }
    else:
        try:
            result = VRMValidator(
                vrm_path,
                product_contract=product_contract,
            ).run_all()
        except Exception as exc:
            result = {
                "status": "error",
                "vrm_path": vrm_path,
                "passed": False,
                "product_contract": product_contract,
                "checks": {},
                "error": str(exc),
            }

    _write_validation_report(report_dir, result)
    return result


def generate_validation_report(
    vrm_path: str,
    output_dir: str,
    *,
    product_contract: bool = True,
) -> str:
    validate_vrm(
        vrm_path,
        output_dir,
        product_contract=product_contract,
    )
    return str(pathlib.Path(output_dir) / "validation" / "report.json")


def _write_validation_report(
    report_dir: pathlib.Path,
    result: Dict[str, Any],
) -> None:
    from vtuber_pipeline.core.utils import save_json

    save_json(result, str(report_dir / "report.json"))
