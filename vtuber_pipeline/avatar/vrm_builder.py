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

# pygltflib for glTF manipulation
try:
    from pygltflib import GLTF2, Buffer, BufferView, Accessor, Node, Mesh, Primitive, Skin
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
    gltf = GLTF2().load(rigged_glb_path)
    
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
            primitive.targets.append({
                "POSITION": accessor_idx
            })
        
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
    
    # Add to buffer
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
    """Create a sparse accessor for morph target with only affected vertices.
    
    Args:
        gltf: The GLTF2 object.
        buffer_data: Binary buffer data.
        morph_data: List of (vertex_index, [dx, dy, dz]) tuples.
        vertex_count: Total number of vertices.
    
    Returns:
        Index of the created accessor.
    """
    # Sort by vertex index
    sorted_data = sorted(morph_data, key=lambda x: x[0])
    
    # Extract indices and values
    indices = np.array([d[0] for d in sorted_data], dtype=np.uint32)
    values = np.array([d[1] for d in sorted_data], dtype=np.float32)
    
    count = len(indices)
    
    # Add indices to buffer
    indices_bytes = indices.tobytes()
    indices_offset = len(buffer_data)
    buffer_data.extend(indices_bytes)
    
    # Add values to buffer
    values_bytes = values.tobytes()
    values_offset = len(buffer_data)
    buffer_data.extend(values_bytes)
    
    # Create BufferView for indices
    bv_indices = BufferView(
        buffer=0,
        byteOffset=indices_offset,
        byteLength=len(indices_bytes),
        target=ARRAY_BUFFER
    )
    gltf.bufferViews.append(bv_indices)
    bv_indices_idx = len(gltf.bufferViews) - 1
    
    # Create BufferView for values
    bv_values = BufferView(
        buffer=0,
        byteOffset=values_offset,
        byteLength=len(values_bytes),
        target=ARRAY_BUFFER
    )
    gltf.bufferViews.append(bv_values)
    bv_values_idx = len(gltf.bufferViews) - 1
    
    # Create Accessor for indices
    acc_indices = Accessor(
        bufferView=bv_indices_idx,
        componentType=UNSIGNED_INT,
        count=count,
        type="SCALAR"
    )
    gltf.accessors.append(acc_indices)
    acc_indices_idx = len(gltf.accessors) - 1
    
    # Create Accessor for values
    max_vals = values.max(axis=0).tolist() if count > 0 else [0.0, 0.0, 0.0]
    min_vals = values.min(axis=0).tolist() if count > 0 else [0.0, 0.0, 0.0]
    
    acc_values = Accessor(
        bufferView=bv_values_idx,
        componentType=FLOAT,
        count=count,
        type="VEC3",
        max=max_vals,
        min=min_vals
    )
    gltf.accessors.append(acc_values)
    acc_values_idx = len(gltf.accessors) - 1
    
    # Create sparse accessor
    sparse_accessor = Accessor(
        count=vertex_count,
        type="VEC3",
        componentType=FLOAT,
        sparse={
            "count": count,
            "indices": {
                "bufferView": bv_indices_idx,
                "componentType": UNSIGNED_INT
            },
            "values": {
                "bufferView": bv_values_idx
            }
        }
    )
    gltf.accessors.append(sparse_accessor)
    
    return len(gltf.accessors) - 1


def create_vrm_extension(
    gltf: "GLTF2",
    bone_mapping: Optional[Dict[str, int]] = None,
    expressions: Optional[Dict[str, Any]] = None,
    look_at_config: Optional[Dict[str, Any]] = None,
    commercial_usage: str = "corporation"
) -> Dict[str, Any]:
    """Build VRMC_vrm extension JSON for VRM 1.0.
    
    VRM 1.0 스펙에 맞게:
    - humanBones: object with bone names as keys (NOT humanoidBones list)
    - preset: object with expression names as keys (NOT presets)
    - licenseUrl: VRM 라이선스 문서 URL
    
    Args:
        gltf: The GLTF2 object with nodes containing bones.
        bone_mapping: Optional dict mapping VRM bone names to node indices.
            If not provided, will attempt to auto-detect from node names.
        expressions: Optional dict mapping expression names to morph target indices.
        look_at_config: Optional look-at configuration with:
            - "offsetFromHeadBone": [x, y, z] offset for eye gaze origin
            - "type": "expression" or "bone"
        commercial_usage: 상업용 사용 권한 (personalNonProfit, personalProfit, corporation)
    
    Returns:
        VRMC_vrm extension dictionary.
    """
    # Build humanoid bone mapping - VRM 1.0 uses humanBones as object
    if bone_mapping is None:
        bone_mapping = _auto_detect_bone_mapping(gltf)
    
    # VRM 1.0: humanBones is an object with bone names as keys
    human_bones = {}
    for bone_name in VRM_HUMANOID_BONES:
        if bone_name in bone_mapping:
            human_bones[bone_name] = {
                "node": bone_mapping[bone_name]
            }
    
    # Build expression presets - VRM 1.0 uses "preset" (singular)
    expression_presets = {}
    if expressions:
        for preset in VRM_EXPRESSION_PRESETS:
            if preset in expressions:
                expr_data = expressions[preset]
                if isinstance(expr_data, dict):
                    expression_presets[preset] = expr_data
                elif isinstance(expr_data, int):
                    # Just a morph target index
                    expression_presets[preset] = {
                        "morphTargetBinds": [{
                            "node": 0,  # Assume first mesh node
                            "index": expr_data
                        }]
                    }
    
    # Build look-at config
    if look_at_config is None:
        look_at_config = {
            "offsetFromHeadBone": [0.0, 0.06, 0.0],  # Default: slightly forward from head
            "type": "bone"  # Use bone rotation for look-at
        }
    
    # Build VRMC_vrm extension with correct VRM 1.0 schema
    vrm_extension = {
        "specVersion": "1.0",
        "humanoid": {
            "humanBones": human_bones  # VRM 1.0: object, not list
        },
        "meta": {
            "name": "VTuber Avatar",
            "version": "1.0",
            "authors": ["VTuber Pipeline"],
            "copyrightInformation": "Generated by VTuber Pipeline",
            "contactInformation": "",
            "licenseUrl": "https://vrm.dev/licenses/1.0/",  # VRM 1.0 license URL
            "avatarPermission": "onlyAuthor",
            "allowExcessivelyViolentUsage": False,
            "allowExcessivelySexualUsage": False,
            "commercialUsage": commercial_usage,  # 기본값: corporation
            "creditNotation": "required",
            "allowRedistribution": False,
            "modification": "prohibited"
        },
        "lookAt": {
            "offsetFromHeadBone": look_at_config.get("offsetFromHeadBone", [0.0, 0.06, 0.0]),
            "type": look_at_config.get("type", "bone")
        }
    }
    
    # Add expressions if present - VRM 1.0 uses "preset" (singular)
    if expression_presets:
        vrm_extension["expressions"] = {
            "preset": expression_presets  # VRM 1.0: "preset", not "presets"
        }
    
    return vrm_extension


def _auto_detect_bone_mapping(gltf: "GLTF2") -> Dict[str, int]:
    """Auto-detect bone mapping from node names.
    
    Args:
        gltf: The GLTF2 object.
    
    Returns:
        Dict mapping VRM bone names to node indices.
    """
    bone_mapping = {}
    
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
    
    for i, node in enumerate(gltf.nodes):
        node_name = node.name or ""
        for vrm_bone, variants in bone_name_variants.items():
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
    springbone_config: Optional[Dict[str, Any]] = None
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
        springbone_config: Optional springbone configuration dict with:
            - "springbone_groups": List of springbone group configs
    
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
            commercial_usage=commercial_usage
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
            if springbone_extension["springs"]:
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
    """Build VRMC_springBone 1.0 JSON from normalized spring config.

    Joint ``node`` values may be glTF node indices or node names. Names are
    resolved against the exported glTF and unresolved joints are rejected.
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
    name_to_index.update({k: v for k, v in bone_mapping.items() if isinstance(v, int)})

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
                raise ValueError(f"Unresolved SpringBone joint node: {node_ref!r}")

            normalized_joints.append({
                "node": node_idx,
                "hitRadius": float(joint.get("hitRadius", 0.02)),
                "stiffness": float(joint.get("stiffness", 0.5)),
                "gravityPower": float(joint.get("gravityPower", 0.1)),
                "gravityDir": list(joint.get("gravityDir", [0.0, -1.0, 0.0])),
                "dragForce": float(joint.get("dragForce", 0.2)),
            })

        if normalized_joints:
            normalized_springs.append({
                "name": spring.get("name", f"spring_{len(normalized_springs)}"),
                "joints": normalized_joints,
                "colliderGroups": list(spring.get("colliderGroups", [])),
            })

    return {
        "specVersion": "1.0",
        "colliders": colliders,
        "colliderGroups": collider_groups,
        "springs": normalized_springs,
    }

def validate_vrm(vrm_path: str) -> Dict[str, Any]:
    """Validate a VRM file.
    
    Checks:
    1. File exists and size > 0
    2. VRMC_vrm extension present
    3. Humanoid bone mapping defined
    4. Expression presets defined (if any)
    
    Args:
        vrm_path: Path to the VRM file.
    
    Returns:
        Dictionary with validation results.
    """
    result = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "checks": {}
    }
    
    vrm_file = pathlib.Path(vrm_path)
    
    # Check file exists
    if not vrm_file.exists():
        result["valid"] = False
        result["errors"].append(f"VRM 파일이 존재하지 않습니다: {vrm_path}")
        return result
    
    # Check file size
    file_size = vrm_file.stat().st_size
    result["file_size_bytes"] = file_size
    result["checks"]["file_exists"] = file_size > 0
    if file_size == 0:
        result["valid"] = False
        result["errors"].append("VRM 파일 크기가 0 bytes입니다")
        return result
    
    # Load and check VRM extension
    if not PYGLTFLIB_AVAILABLE:
        result["warnings"].append("pygltflib이 설치되지 않아 내부 검증을 건너뜁니다")
        return result
    
    try:
        gltf = GLTF2().load(vrm_path)
        
        # Check VRMC_vrm extension
        has_vrm = gltf.extensions and "VRMC_vrm" in gltf.extensions
        result["checks"]["vrm_extension"] = has_vrm
        
        if not has_vrm:
            result["valid"] = False
            result["errors"].append("VRMC_vrm 확장이 없습니다")
        else:
            vrm_ext = gltf.extensions["VRMC_vrm"]
            
            # Check humanoid - VRM 1.0 uses humanBones (object)
            humanoid = vrm_ext.get("humanoid", {})
            bones = humanoid.get("humanBones", {})
            result["checks"]["humanoid_bones"] = len(bones) > 0
            result["humanoid_bone_count"] = len(bones)
            
            if len(bones) == 0:
                result["valid"] = False
                result["errors"].append("휴머노이드 뼈대 매핑이 없습니다")
            
            # Check expressions - VRM 1.0 uses preset (singular)
            expressions = vrm_ext.get("expressions", {})
            presets = expressions.get("preset", {})
            result["checks"]["expressions"] = True  # Expressions are optional
            result["expression_count"] = len(presets)
            
            if presets:
                result["warnings"].append(f"표정 프리셋 {len(presets)}개 발견")
        
    except Exception as e:
        result["valid"] = False
        result["errors"].append(f"VRM 검증 오류: {str(e)}")
    
    return result
