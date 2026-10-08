"""VRM 1.0 builder using pygltflib.

This module provides functions for building VRM 1.0 files from rigged GLB meshes
without requiring Blender. It constructs the VRMC_vrm extension with humanoid
bone mapping, expression presets, and look-at configuration.

VRM 1.0 specification: https://github.com/vrm-c/vrm-specification
"""

import base64
import json
import pathlib
from typing import Dict, Any, List, Optional, Tuple
import numpy as np

from vtuber_pipeline.core.gltf import load_gltf

# pygltflib for glTF manipulation
try:
    from pygltflib import (
        GLTF2, Buffer, BufferView, Accessor, Node, Mesh, Primitive, Skin,
        Attributes, Sparse, AccessorSparseIndices, AccessorSparseValues,
    )
    from pygltflib import ARRAY_BUFFER, ELEMENT_ARRAY_BUFFER, FLOAT, UNSIGNED_INT, UNSIGNED_BYTE
    PYGLTFLIB_AVAILABLE = True
except ImportError:
    GLTF2 = None
    PYGLTFLIB_AVAILABLE = False


# VRM 1.0 humanoid bone mapping (VRMC_vrm spec)
VRM_HUMANOID_BONES = [
    "hips",
    "spine",
    "chest",
    "upperChest",
    "neck",
    "head",
    "leftEye",
    "rightEye",
    "jaw",
    "leftShoulder",
    "leftUpperArm",
    "leftLowerArm",
    "leftHand",
    "leftUpperLeg",
    "leftLowerLeg",
    "leftFoot",
    "leftToes",
    "rightShoulder",
    "rightUpperArm",
    "rightLowerArm",
    "rightHand",
    "rightUpperLeg",
    "rightLowerLeg",
    "rightFoot",
    "rightToes",
]

# VRM 1.0 expression presets
VRM_EXPRESSION_PRESETS = [
    "happy",
    "angry",
    "sad",
    "relaxed",
    "surprised",
    "aa",
    "ih",
    "ou",
    "ee",
    "oh",
    "blink",
    "blinkLeft",
    "blinkRight",
    "lookUp",
    "lookDown",
    "lookLeft",
    "lookRight",
    "neutral",
]


def create_gltf_from_mesh(
    rigged_glb_path: str,
    morph_targets: Optional[Dict[str, List[Tuple[int, List[float]]]]] = None
) -> Tuple["GLTF2", bytearray]:
    """Load a rigged GLB and optionally add morph targets for expressions.
    
    Args:
        rigged_glb_path: Path to the rigged GLB file.
        morph_targets: Optional dict mapping expression names to morph data.
            Each morph target is a list of (vertex_index, [dx, dy, dz]) tuples.
    
    Returns:
        Tuple of (GLTF2 object, binary buffer data).
    """
    if not PYGLTFLIB_AVAILABLE:
        raise ImportError("pygltflib이 설치되지 않았습니다. pip install pygltflib")
    
    # Load the existing rigged GLB
    gltf = load_gltf(rigged_glb_path)
    
    # Get the binary buffer
    buffer_data = bytearray(gltf.binary_blob())
    
    # If morph targets are provided, add them to the mesh
    if morph_targets and len(morph_targets) > 0:
        gltf, buffer_data = _add_morph_targets(gltf, buffer_data, morph_targets)
    
    return gltf, buffer_data


def _add_morph_targets(
    gltf: "GLTF2",
    buffer_data: bytearray,
    morph_targets: Dict[str, List[Tuple[int, List[float]]]]
) -> Tuple["GLTF2", bytearray]:
    """Add morph targets (shape keys) to the glTF mesh.
    
    Args:
        gltf: The GLTF2 object.
        buffer_data: The binary buffer data.
        morph_targets: Dict mapping expression names to morph data.
    
    Returns:
        Updated (GLTF2, buffer_data) tuple.
    """
    # Find the first mesh with primitives
    if not gltf.meshes or not gltf.meshes[0].primitives:
        return gltf, buffer_data
    
    mesh = gltf.meshes[0]
    primitive = mesh.primitives[0]
    
    # Get vertex count from POSITION accessor
    position_accessor = gltf.accessors[primitive.attributes.POSITION]
    vertex_count = position_accessor.count
    
    # Create sparse accessors for each morph target
    morph_accessors = []
    morph_names = []
    
    for expr_name, morph_data in morph_targets.items():
        # Handle both formats:
        # - Dict with 'morph_targets' key (from generate_expressions)
        # - Direct list of tuples (legacy format)
        if isinstance(morph_data, dict):
            actual_morph_data = morph_data.get('morph_targets', [])
        else:
            actual_morph_data = morph_data
            
        if not actual_morph_data:
            # Empty morph - create zero delta accessor
            accessor_idx = _create_zero_morph_accessor(gltf, buffer_data, vertex_count)
            morph_accessors.append(accessor_idx)
            morph_names.append(expr_name)
            continue
        
        # Create sparse accessor for non-zero morphs
        accessor_idx = _create_sparse_morph_accessor(
            gltf, buffer_data, actual_morph_data, vertex_count
        )
        morph_accessors.append(accessor_idx)
        morph_names.append(expr_name)
    
    # Update primitive with morph targets
    if morph_accessors:
        # Add targets to primitive
        primitive.targets = []
        for accessor_idx in morph_accessors:
            primitive.targets.append(Attributes(POSITION=accessor_idx))
        
        # Set morph target names on mesh extras
        if mesh.extras is None:
            mesh.extras = {}
        mesh.extras["targetNames"] = morph_names
    
    return gltf, buffer_data


def _create_zero_morph_accessor(
    gltf: "GLTF2",
    buffer_data: bytearray,
    vertex_count: int
) -> int:
    """Create an accessor for a zero-delta morph target (no effect).
    
    Args:
        gltf: The GLTF2 object.
        buffer_data: Binary buffer data.
        vertex_count: Number of vertices.
    
    Returns:
        Index of the created accessor.
    """
    # Create zero deltas
    zeros = np.zeros((vertex_count, 3), dtype=np.float32)
    zeros_bytes = zeros.tobytes()
    
    # Add to buffer with glTF's 4-byte alignment.
    while len(buffer_data) % 4:
        buffer_data.append(0)
    byte_offset = len(buffer_data)
    buffer_data.extend(zeros_bytes)
    
    # Create BufferView
    bv = BufferView(
        buffer=0,
        byteOffset=byte_offset,
        byteLength=len(zeros_bytes),
        target=ARRAY_BUFFER
    )
    gltf.bufferViews.append(bv)
    bv_idx = len(gltf.bufferViews) - 1
    
    # Create Accessor
    acc = Accessor(
        bufferView=bv_idx,
        componentType=FLOAT,
        count=vertex_count,
        type="VEC3",
        max=[0.0, 0.0, 0.0],
        min=[0.0, 0.0, 0.0]
    )
    gltf.accessors.append(acc)
    
    return len(gltf.accessors) - 1


def _create_sparse_morph_accessor(
    gltf: "GLTF2",
    buffer_data: bytearray,
    morph_data: List[Tuple[int, List[float]]],
    vertex_count: int
) -> int:
    """Create a glTF sparse POSITION accessor for one morph target."""
    # glTF sparse indices must be strictly increasing. Merge repeated
    # vertex contributions deterministically before serialization.
    merged: Dict[int, np.ndarray] = {}
    for raw_index, raw_delta in morph_data:
        index = int(raw_index)
        delta = np.asarray(raw_delta, dtype=np.float32)
        if delta.shape != (3,) or not np.all(np.isfinite(delta)):
            raise ValueError(
                f"Invalid morph delta for vertex {index}: {raw_delta!r}"
            )
        if index in merged:
            merged[index] = merged[index] + delta
        else:
            merged[index] = delta.copy()

    sorted_indices = sorted(merged)
    indices = np.asarray(sorted_indices, dtype=np.uint32)
    values = np.asarray([merged[index] for index in sorted_indices], dtype=np.float32)

    if len(indices) == 0:
        return _create_zero_morph_accessor(gltf, buffer_data, vertex_count)

    if np.any(indices < 0) or np.any(indices >= vertex_count):
        raise ValueError("Morph target contains an out-of-range vertex index")
    if values.shape != (len(indices), 3):
        raise ValueError(
            f"Morph target values must have shape (N, 3), got {values.shape}"
        )

    # glTF bufferView offsets must be 4-byte aligned for these component types.
    while len(buffer_data) % 4:
        buffer_data.append(0)
    indices_offset = len(buffer_data)
    indices_bytes = indices.tobytes()
    buffer_data.extend(indices_bytes)

    while len(buffer_data) % 4:
        buffer_data.append(0)
    values_offset = len(buffer_data)
    values_bytes = values.tobytes()
    buffer_data.extend(values_bytes)

    # Sparse index/value bufferViews are not regular vertex/index bindings, so
    # leave target unset.
    gltf.bufferViews.append(BufferView(
        buffer=0,
        byteOffset=indices_offset,
        byteLength=len(indices_bytes),
    ))
    bv_indices_idx = len(gltf.bufferViews) - 1

    gltf.bufferViews.append(BufferView(
        buffer=0,
        byteOffset=values_offset,
        byteLength=len(values_bytes),
    ))
    bv_values_idx = len(gltf.bufferViews) - 1

    value_min = np.minimum(values.min(axis=0), 0.0).tolist()
    value_max = np.maximum(values.max(axis=0), 0.0).tolist()
    sparse_accessor = Accessor(
        count=vertex_count,
        type="VEC3",
        componentType=FLOAT,
        min=value_min,
        max=value_max,
        sparse=Sparse(
            count=len(indices),
            indices=AccessorSparseIndices(
                bufferView=bv_indices_idx,
                componentType=UNSIGNED_INT,
            ),
            values=AccessorSparseValues(
                bufferView=bv_values_idx,
            ),
        ),
    )
    gltf.accessors.append(sparse_accessor)
    return len(gltf.accessors) - 1

def create_vrm_extension(
    gltf: "GLTF2",
    bone_mapping: Optional[Dict[str, int]] = None,
    expressions: Optional[Dict[str, Any]] = None,
    look_at_config: Optional[Dict[str, Any]] = None,
    commercial_usage: str = "corporation",
) -> Dict[str, Any]:
    """Build the VRMC_vrm 1.0 extension from actual glTF nodes/targets."""
    allowed_commercial_usage = {
        "personalNonProfit",
        "personalProfit",
        "corporation",
    }
    if commercial_usage not in allowed_commercial_usage:
        raise ValueError(
            f"Invalid VRM commercialUsage: {commercial_usage!r}"
        )

    if bone_mapping is None:
        bone_mapping = _auto_detect_bone_mapping(gltf)

    human_bones = {
        bone_name: {"node": bone_mapping[bone_name]}
        for bone_name in VRM_HUMANOID_BONES
        if bone_name in bone_mapping
    }

    # Bind VRM expression presets to the morph targets actually added to mesh 0.
    expression_presets: Dict[str, Any] = {}
    target_names: List[str] = []
    if gltf.meshes:
        extras = gltf.meshes[0].extras or {}
        if isinstance(extras, dict):
            target_names = list(extras.get("targetNames", []) or [])
    mesh_node_idx = next(
        (i for i, node in enumerate(gltf.nodes or []) if getattr(node, "mesh", None) == 0),
        None,
    )
    if expressions and mesh_node_idx is not None:
        for preset in VRM_EXPRESSION_PRESETS:
            if preset in expressions and preset in target_names:
                target_index = target_names.index(preset)
                expression_presets[preset] = {
                    "morphTargetBinds": [{
                        "node": mesh_node_idx,
                        "index": target_index,
                        "weight": 1.0,
                    }],
                    "isBinary": False,
                }

    look_at_config = look_at_config or {}
    if not isinstance(look_at_config, dict):
        raise ValueError("look_at_config must be an object")

    look_at_type = str(look_at_config.get("type", "bone"))
    if look_at_type not in {"bone", "expression"}:
        raise ValueError(f"Invalid VRM lookAt type: {look_at_type!r}")

    offset = np.asarray(
        look_at_config.get("offsetFromHeadBone", [0.0, 0.06, 0.0]),
        dtype=float,
    )
    if offset.shape != (3,) or not np.all(np.isfinite(offset)):
        raise ValueError("lookAt offsetFromHeadBone must contain 3 finite numbers")

    yaw_limit = float(look_at_config.get("yaw_limit_deg", 30.0))
    pitch_limit = float(look_at_config.get("pitch_limit_deg", 20.0))
    if (
        not np.isfinite(yaw_limit)
        or not np.isfinite(pitch_limit)
        or yaw_limit < 0.0
        or pitch_limit < 0.0
    ):
        raise ValueError("lookAt yaw/pitch limits must be finite and non-negative")

    # VRM 1.0 RangeMap maps a target yaw/pitch input angle to either eye-bone
    # rotation (degrees) or expression weight. The pipeline generates bone
    # look-at, so preserve the gaze stage's explicit eye-rotation limits as
    # outputScale instead of silently dropping them.
    horizontal_output = yaw_limit if look_at_type == "bone" else 1.0
    vertical_output = pitch_limit if look_at_type == "bone" else 1.0
    look_at = {
        "offsetFromHeadBone": offset.astype(float).tolist(),
        "type": look_at_type,
        "rangeMapHorizontalInner": {
            "inputMaxValue": 90.0,
            "outputScale": horizontal_output,
        },
        "rangeMapHorizontalOuter": {
            "inputMaxValue": 90.0,
            "outputScale": horizontal_output,
        },
        "rangeMapVerticalDown": {
            "inputMaxValue": 90.0,
            "outputScale": vertical_output,
        },
        "rangeMapVerticalUp": {
            "inputMaxValue": 90.0,
            "outputScale": vertical_output,
        },
    }

    vrm_extension: Dict[str, Any] = {
        "specVersion": "1.0",
        "humanoid": {"humanBones": human_bones},
        "meta": {
            "name": "VTuber Avatar",
            "version": "1.0",
            "authors": ["VTuber Pipeline"],
            "copyrightInformation": "Generated by VTuber Pipeline",
            "contactInformation": "",
            "licenseUrl": "https://vrm.dev/licenses/1.0/",
            "avatarPermission": "onlyAuthor",
            "allowExcessivelyViolentUsage": False,
            "allowExcessivelySexualUsage": False,
            "commercialUsage": commercial_usage,
            "creditNotation": "required",
            "allowRedistribution": False,
            "modification": "prohibited",
        },
        "lookAt": look_at,
    }
    if expression_presets:
        vrm_extension["expressions"] = {"preset": expression_presets}
    return vrm_extension

def _auto_detect_bone_mapping(gltf: "GLTF2") -> Dict[str, int]:
    """Auto-detect bone mapping from node names.
    
    Args:
        gltf: The GLTF2 object.
    
    Returns:
        Dict mapping VRM bone names to node indices.
    """
    # Prefer exact VRM semantic names. Aliases are fallback-only and must
    # never overwrite an already resolved canonical node (notably "root"
    # used as a hips alias).
    node_names = {
        node.name: i
        for i, node in enumerate(gltf.nodes or [])
        if getattr(node, "name", None)
    }
    bone_mapping = {
        bone_name: node_names[bone_name]
        for bone_name in VRM_HUMANOID_BONES
        if bone_name in node_names
    }
    
    # Common bone name variations
    bone_name_variants = {
        "hips": ["hips", "Hips", "hip", "Hip", "root"],
        "spine": ["spine", "Spine", "spine1", "Spine1"],
        "chest": ["chest", "Chest", "spine2", "Spine2"],
        "upperChest": ["upperChest", "UpperChest", "spine3", "Spine3"],
        "neck": ["neck", "Neck"],
        "head": ["head", "Head"],
        "leftEye": ["leftEye", "LeftEye", "eye_L", "eye_L", "L_eye"],
        "rightEye": ["rightEye", "RightEye", "eye_R", "Eye_R", "R_eye"],
        "jaw": ["jaw", "Jaw"],
        "leftShoulder": ["leftShoulder", "LeftShoulder", "shoulder_L", "Shoulder_L"],
        "leftUpperArm": ["leftUpperArm", "LeftUpperArm", "upperarm_L", "UpperArm_L"],
        "leftLowerArm": ["leftLowerArm", "LeftLowerArm", "forearm_L", "ForeArm_L"],
        "leftHand": ["leftHand", "LeftHand", "hand_L", "Hand_L"],
        "leftUpperLeg": ["leftUpperLeg", "LeftUpperLeg", "thigh_L", "Thigh_L", "upperleg_L"],
        "leftLowerLeg": ["leftLowerLeg", "LeftLowerLeg", "shin_L", "Shin_L", "calf_L"],
        "leftFoot": ["leftFoot", "LeftFoot", "foot_L", "Foot_L"],
        "leftToes": ["leftToes", "LeftToes", "toe_L", "Toe_L"],
        "rightShoulder": ["rightShoulder", "RightShoulder", "shoulder_R", "Shoulder_R"],
        "rightUpperArm": ["rightUpperArm", "RightUpperArm", "upperarm_R", "UpperArm_R"],
        "rightLowerArm": ["rightLowerArm", "RightLowerArm", "forearm_R", "ForeArm_R"],
        "rightHand": ["rightHand", "RightHand", "hand_R", "Hand_R"],
        "rightUpperLeg": ["rightUpperLeg", "RightUpperLeg", "thigh_R", "Thigh_R", "upperleg_R"],
        "rightLowerLeg": ["rightLowerLeg", "RightLowerLeg", "shin_R", "Shin_R", "calf_R"],
        "rightFoot": ["rightFoot", "RightFoot", "foot_R", "Foot_R"],
        "rightToes": ["rightToes", "RightToes", "toe_R", "Toe_R"],
    }
    
    for i, node in enumerate(gltf.nodes or []):
        node_name = node.name or ""
        for vrm_bone, variants in bone_name_variants.items():
            if vrm_bone in bone_mapping:
                continue
            if node_name in variants:
                bone_mapping[vrm_bone] = i
                break
    
    return bone_mapping


def export_vrm(
    rigged_glb_path: str,
    output_dir: str,
    expressions: Optional[Dict[str, Any]] = None,
    bone_mapping: Optional[Dict[str, int]] = None,
    commercial_usage: str = "corporation",
    springbone_config: Optional[Dict[str, Any]] = None,
    look_at_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Export rigged mesh to VRM 1.0 format.
    
    This function:
    1. Loads the rigged GLB
    2. Adds morph targets for expressions (if provided)
    3. Builds the VRMC_vrm extension
    4. Builds the VRMC_springBone extension (if config provided)
    5. Merges the extensions into the glTF JSON
    6. Writes the result as a .vrm binary file
    
    Args:
        rigged_glb_path: Path to the rigged GLB file.
        output_dir: Directory to write output files.
        expressions: Optional dict of expression morph data.
            Each key is an expression name, value is either:
            - List of (vertex_index, [dx, dy, dz]) tuples
            - Dict with morphTargetBinds structure
        bone_mapping: Optional dict mapping VRM bone names to node indices.
        commercial_usage: 상업용 사용 권한 (personalNonProfit, personalProfit, corporation).
            기본값은 "corporation"입니다.
        springbone_config: Optional normalized VRMC_springBone configuration.
        look_at_config: Optional VRM look-at configuration derived from eye bones.
    
    Returns:
        Dictionary with export results including:
        - "status": "complete", "error", or "validation_failed"
        - "vrm_path": Path to the output VRM file
        - "vrm_extension": The VRMC_vrm extension data
        - "springbone_extension": The VRMC_springBone extension data (if any)
    """
    result = {
        "status": "pending",
        "rigged_glb_path": rigged_glb_path,
        "output_dir": output_dir
    }
    
    # Create output directory
    pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Check pygltflib availability
    if not PYGLTFLIB_AVAILABLE:
        result["status"] = "error"
        result["error"] = "pygltflib이 설치되지 않았습니다. pip install pygltflib"
        return result
    
    try:
        # Step 1: Load rigged GLB and add morph targets
        gltf, buffer_data = create_gltf_from_mesh(
            rigged_glb_path,
            morph_targets=expressions if expressions else None
        )
        
        # Step 2: Build VRMC_vrm extension with commercial_usage
        vrm_extension = create_vrm_extension(
            gltf,
            bone_mapping=bone_mapping,
            expressions=expressions,
            look_at_config=look_at_config,
            commercial_usage=commercial_usage,
        )
        
        # Step 3: Add VRM extension to glTF
        if gltf.extensionsUsed is None:
            gltf.extensionsUsed = []
        if "VRMC_vrm" not in gltf.extensionsUsed:
            gltf.extensionsUsed.append("VRMC_vrm")
        
        if gltf.extensions is None:
            gltf.extensions = {}
        gltf.extensions["VRMC_vrm"] = vrm_extension
        
        # Step 3.5: Build and add VRMC_springBone extension if config provided
        springbone_extension = None
        if springbone_config and springbone_config.get("springs"):
            springbone_extension = create_springbone_extension(
                gltf,
                springs=springbone_config.get("springs", []),
                colliders=springbone_config.get("colliders", []),
                collider_groups=springbone_config.get("colliderGroups", []),
                bone_mapping=bone_mapping,
            )
            if springbone_extension.get("springs"):
                if "VRMC_springBone" not in gltf.extensionsUsed:
                    gltf.extensionsUsed.append("VRMC_springBone")
                gltf.extensions["VRMC_springBone"] = springbone_extension
        
        # Step 4: Update buffer size
        if gltf.buffers:
            gltf.buffers[0].byteLength = len(buffer_data)
        
        # Step 5: Write VRM file (always as avatar.vrm for consistency)
        # VRM 1.0: save_binary() 후 .vrm으로 리네임
        output_path = pathlib.Path(output_dir) / "avatar.vrm"
        temp_glb = pathlib.Path(output_dir) / "avatar.glb"
        
        # Set binary blob and save
        gltf.set_binary_blob(bytes(buffer_data))
        gltf.save_binary(str(temp_glb))
        
        # Rename to .vrm
        if temp_glb.exists():
            temp_glb.rename(output_path)
        
        # Verify file was created
        if output_path.exists() and output_path.stat().st_size > 0:
            result["status"] = "complete"
            result["vrm_path"] = str(output_path)
            result["vrm_extension"] = vrm_extension
            if springbone_extension:
                result["springbone_extension"] = springbone_extension
            result["file_size_bytes"] = output_path.stat().st_size
        else:
            result["status"] = "error"
            result["error"] = "VRM 파일이 생성되지 않았습니다"
            
    except FileNotFoundError as e:
        result["status"] = "error"
        result["error"] = f"입력 파일을 찾을 수 없습니다: {rigged_glb_path}"
    except Exception as e:
        result["status"] = "error"
        result["error"] = f"VRM 내보내기 오류: {str(e)}"
    
    # Write report
    _write_vrm_builder_report(output_dir, result)
    
    return result


def _write_vrm_builder_report(output_dir: str, result: Dict[str, Any]) -> None:
    """Write vrm_builder_report.json to output directory."""
    from vtuber_pipeline.core.utils import save_json
    
    output_path = pathlib.Path(output_dir) / "vrm_builder_report.json"
    save_json(result, str(output_path))


def create_springbone_extension(
    gltf: "GLTF2",
    springs: Optional[List[Dict[str, Any]]] = None,
    colliders: Optional[List[Dict[str, Any]]] = None,
    collider_groups: Optional[List[Dict[str, Any]]] = None,
    bone_mapping: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    """Build schema-valid VRMC_springBone 1.0 JSON.

    Optional arrays are omitted when empty because the official schema requires
    minItems=1 whenever those properties are present.
    """
    springs = springs or []
    colliders = colliders or []
    collider_groups = collider_groups or []
    bone_mapping = bone_mapping or {}

    name_to_index = {
        node.name: i
        for i, node in enumerate(gltf.nodes or [])
        if getattr(node, "name", None)
    }
    name_to_index.update({
        k: v for k, v in bone_mapping.items() if isinstance(v, int)
    })

    normalized_springs: List[Dict[str, Any]] = []
    for spring in springs:
        normalized_joints: List[Dict[str, Any]] = []
        for joint in spring.get("joints", []):
            node_ref = joint.get("node")
            if isinstance(node_ref, str):
                node_idx = name_to_index.get(node_ref)
            elif isinstance(node_ref, int):
                node_idx = node_ref
            else:
                node_idx = None

            if node_idx is None or not (0 <= node_idx < len(gltf.nodes or [])):
                raise ValueError(
                    f"Unresolved SpringBone joint node: {node_ref!r}"
                )

            gravity_dir = list(joint.get("gravityDir", [0.0, -1.0, 0.0]))
            if len(gravity_dir) != 3:
                raise ValueError("SpringBone gravityDir must contain 3 numbers")

            normalized_joints.append({
                "node": node_idx,
                "hitRadius": max(0.0, float(joint.get("hitRadius", 0.02))),
                "stiffness": max(0.0, float(joint.get("stiffness", 0.5))),
                "gravityPower": max(
                    0.0, float(joint.get("gravityPower", 0.1))
                ),
                "gravityDir": [float(v) for v in gravity_dir],
                "dragForce": min(
                    1.0, max(0.0, float(joint.get("dragForce", 0.2)))
                ),
            })

        if not normalized_joints:
            continue

        item: Dict[str, Any] = {
            "name": spring.get(
                "name", f"spring_{len(normalized_springs)}"
            ),
            "joints": normalized_joints,
        }
        spring_collider_groups = list(spring.get("colliderGroups", []))
        if spring_collider_groups:
            item["colliderGroups"] = spring_collider_groups
        if spring.get("center") is not None:
            item["center"] = int(spring["center"])
        normalized_springs.append(item)

    extension: Dict[str, Any] = {
        "specVersion": "1.0",
    }
    if colliders:
        extension["colliders"] = colliders
    if collider_groups:
        extension["colliderGroups"] = collider_groups
    if normalized_springs:
        extension["springs"] = normalized_springs
    return extension
