"""Avatar rigging module for VTuber Pipeline."""

import pathlib
import numpy as np
from typing import Dict, List, Tuple, Any

# Optional dependency - trimesh for mesh operations
try:
    import trimesh
    TRIMESH_AVAILABLE = True
except ImportError:
    trimesh = None
    TRIMESH_AVAILABLE = False

# Optional dependency - pygltflib for glTF manipulation
try:
    from pygltflib import GLTF2, Skin, Node, Accessor, BufferView, Buffer
    from pygltflib import ARRAY_BUFFER, ELEMENT_ARRAY_BUFFER, FLOAT, UNSIGNED_INT, UNSIGNED_SHORT
    PYGLTFLIB_AVAILABLE = True
except ImportError:
    GLTF2 = None
    PYGLTFLIB_AVAILABLE = False


def create_humanoid_skeleton(mesh_bounds: np.ndarray) -> Dict[str, Any]:
    """
    메시 바운드에서 휴머노이드 뼈대 계층 구조를 생성합니다.
    
    Args:
        mesh_bounds: (2, 3) 배열 - [min_bounds, max_bounds]
    
    Returns:
        Dict with 'joints', 'parents', 'positions', 'names'
    """
    min_bounds = mesh_bounds[0]
    max_bounds = mesh_bounds[1]
    
    # 메시 중심과 높이 계산
    center_x = (min_bounds[0] + max_bounds[0]) / 2
    center_z = (min_bounds[2] + max_bounds[2]) / 2
    height = max_bounds[1] - min_bounds[1]
    
    # 뼈대 위치 계산 (Y축 기준, 메시 바닥에서부터)
    base_y = min_bounds[1]
    half_span = max(
        float(max_bounds[0] - center_x),
        float(center_x - min_bounds[0]),
        height * 0.2,
    )
    shoulder_offset = min(height * 0.13, half_span * 0.38)
    hand_offset = max(shoulder_offset + height * 0.22, half_span * 0.92)
    upper_arm_offset = shoulder_offset + (hand_offset - shoulder_offset) * 0.36
    lower_arm_offset = shoulder_offset + (hand_offset - shoulder_offset) * 0.72
    arm_y = base_y + height * 0.72

    # VRM 휴머노이드 뼈대 정의 (이름, 부모 인덱스, 위치)
    # 위치는 부모 기준 로컬 좌표가 아닌 월드 좌표로 정의
    bones = [
        # 이름, 부모 인덱스, 월드 위치 (X, Y, Z)
        ("hips", -1, np.array([center_x, base_y + height * 0.50, center_z])),
        ("spine", 0, np.array([center_x, base_y + height * 0.55, center_z])),
        ("chest", 1, np.array([center_x, base_y + height * 0.65, center_z])),
        ("upperChest", 2, np.array([center_x, base_y + height * 0.72, center_z])),
        ("neck", 3, np.array([center_x, base_y + height * 0.78, center_z])),
        ("head", 4, np.array([center_x, base_y + height * 0.85, center_z])),
        
        # 눈 (머리 앞쪽)
        ("leftEye", 5, np.array([center_x + height * 0.03, base_y + height * 0.88, center_z + height * 0.05])),
        ("rightEye", 5, np.array([center_x - height * 0.03, base_y + height * 0.88, center_z + height * 0.05])),
        
        # 왼쪽 팔: VRM rest pose requires a T-pose, +X is model-left.
        ("leftShoulder", 3, np.array([center_x + shoulder_offset, arm_y, center_z])),
        ("leftUpperArm", 8, np.array([center_x + upper_arm_offset, arm_y, center_z])),
        ("leftLowerArm", 9, np.array([center_x + lower_arm_offset, arm_y, center_z])),
        ("leftHand", 10, np.array([center_x + hand_offset, arm_y, center_z])),
        
        # 오른쪽 팔: -X is model-right.
        ("rightShoulder", 3, np.array([center_x - shoulder_offset, arm_y, center_z])),
        ("rightUpperArm", 12, np.array([center_x - upper_arm_offset, arm_y, center_z])),
        ("rightLowerArm", 13, np.array([center_x - lower_arm_offset, arm_y, center_z])),
        ("rightHand", 14, np.array([center_x - hand_offset, arm_y, center_z])),
        
        # 왼쪽 다리
        ("leftUpperLeg", 0, np.array([center_x + height * 0.08, base_y + height * 0.48, center_z])),
        ("leftLowerLeg", 16, np.array([center_x + height * 0.08, base_y + height * 0.28, center_z])),
        ("leftFoot", 17, np.array([center_x + height * 0.08, base_y + height * 0.08, center_z])),
        ("leftToes", 18, np.array([center_x + height * 0.08, base_y + height * 0.02, center_z + height * 0.03])),
        
        # 오른쪽 다리
        ("rightUpperLeg", 0, np.array([center_x - height * 0.08, base_y + height * 0.48, center_z])),
        ("rightLowerLeg", 20, np.array([center_x - height * 0.08, base_y + height * 0.28, center_z])),
        ("rightFoot", 21, np.array([center_x - height * 0.08, base_y + height * 0.08, center_z])),
        ("rightToes", 22, np.array([center_x - height * 0.08, base_y + height * 0.02, center_z + height * 0.03])),
        
        # Secondary chain used by VRMC_springBone.  The chain sits behind the
        # upper head so only back/top vertices can be weighted to it.
        ("hairRoot", 5, np.array([center_x, base_y + height * 0.91, center_z - height * 0.03])),
        ("hairMid", 24, np.array([center_x, base_y + height * 0.84, center_z - height * 0.07])),
        ("hairTip", 25, np.array([center_x, base_y + height * 0.76, center_z - height * 0.09])),
    ]
    
    names = [b[0] for b in bones]
    parents = np.array([b[1] for b in bones], dtype=np.int32)
    positions = np.array([b[2] for b in bones], dtype=np.float32)
    
    # inverseBindMatrices 계산 (각 뼈의 역변환 행렬)
    # 월드 변환 행렬에서 역행렬을 구함
    num_bones = len(bones)
    inverse_bind_matrices = np.zeros((num_bones, 4, 4), dtype=np.float32)
    
    # 각 뼈의 월드 변환 행렬 계산
    world_matrices = np.zeros((num_bones, 4, 4), dtype=np.float32)
    
    for i, (name, parent_idx, world_pos) in enumerate(bones):
        # 단위 행렬로 시작
        world_matrices[i] = np.eye(4, dtype=np.float32)
        
        # 위치 설정
        if parent_idx >= 0:
            # 로컬 위치 = 월드 위치 - 부모 월드 위치
            local_pos = world_pos - bones[parent_idx][2]
            world_matrices[i, :3, 3] = world_pos
        else:
            # 루트 뼈
            world_matrices[i, :3, 3] = world_pos
        
        # inverseBindMatrix = inverse(worldMatrix)
        inverse_bind_matrices[i] = np.linalg.inv(world_matrices[i])
    
    return {
        "names": names,
        "parents": parents,
        "positions": positions,
        "world_matrices": world_matrices,
        "inverse_bind_matrices": inverse_bind_matrices,
        "num_joints": num_bones
    }


def compute_skin_weights(
    vertices: np.ndarray,
    skeleton: Dict[str, Any],
    max_influences: int = 4
) -> Tuple[np.ndarray, np.ndarray]:
    """Compute normalized skin weights with a localized secondary hair chain.

    Humanoid bones are available everywhere. Secondary hair bones are only
    eligible for upper/back-head vertices so facial/torso vertices cannot
    accidentally inherit SpringBone motion.
    """
    num_vertices = len(vertices)
    positions = skeleton["positions"]
    names = skeleton["names"]
    num_joints = skeleton["num_joints"]

    diff = vertices[:, None, :] - positions[None, :, :]
    distances = np.linalg.norm(diff, axis=2)
    weights = 1.0 / (distances + 1e-6)

    hair_indices = np.array([i for i, name in enumerate(names) if name.lower().startswith("hair")], dtype=int)
    if len(hair_indices):
        vmin = vertices.min(axis=0)
        vmax = vertices.max(axis=0)
        height = max(float(vmax[1] - vmin[1]), 1e-6)
        center_z = float((vmin[2] + vmax[2]) / 2.0)
        hair_region = (vertices[:, 1] >= vmin[1] + 0.72 * height) & (vertices[:, 2] <= center_z)
        weights[~hair_region[:, None] & np.isin(np.arange(num_joints)[None, :], hair_indices)] = 0.0

    joint_indices = np.zeros((num_vertices, max_influences), dtype=np.uint16)
    joint_weights = np.zeros((num_vertices, max_influences), dtype=np.float32)

    for i in range(num_vertices):
        order = np.argsort(weights[i])[::-1]
        order = order[weights[i, order] > 0][:max_influences]
        if len(order) == 0:
            order = np.array([0], dtype=int)
        selected = weights[i, order].astype(np.float32)
        total = float(selected.sum())
        selected = selected / total if total > 0 else np.ones(len(order), dtype=np.float32) / len(order)
        joint_indices[i, :len(order)] = order.astype(np.uint16)
        joint_weights[i, :len(order)] = selected

    return joint_indices, joint_weights

def create_gltf_with_skin(
    mesh: Any,
    skeleton: Dict[str, Any],
    joint_indices: np.ndarray,
    joint_weights: np.ndarray,
    output_path: str,
    texture_path: str | None = None,
) -> str:
    """Create a binary glTF with skinning and an optional embedded PNG texture."""
    if not PYGLTFLIB_AVAILABLE:
        raise ImportError("pygltflib이 설치되지 않았습니다. pip install pygltflib")

    from pygltflib import (
        Mesh, Primitive, Scene, Image, Texture, Sampler, Material,
        PbrMetallicRoughness, TextureInfo
    )

    gltf = GLTF2()
    buffer_data = bytearray()

    def append_aligned(payload: bytes) -> tuple[int, int]:
        while len(buffer_data) % 4:
            buffer_data.append(0)
        offset = len(buffer_data)
        buffer_data.extend(payload)
        return offset, len(payload)

    vertices = np.asarray(mesh.vertices, dtype=np.float32)
    normals = np.asarray(mesh.vertex_normals, dtype=np.float32)
    faces = np.asarray(mesh.faces, dtype=np.uint32).reshape(-1)
    joints = np.asarray(joint_indices, dtype=np.uint16)
    weights = np.asarray(joint_weights, dtype=np.float32)
    # glTF MAT4 payloads are column-major. NumPy matrices are stored
    # row-major by default, so transpose each matrix before serialization.
    ibm = np.asarray(
        skeleton["inverse_bind_matrices"],
        dtype=np.float32,
    ).transpose(0, 2, 1).copy()

    pos_off, pos_len = append_aligned(vertices.tobytes())
    norm_off, norm_len = append_aligned(normals.tobytes())
    idx_off, idx_len = append_aligned(faces.tobytes())
    joint_off, joint_len = append_aligned(joints.tobytes())
    weight_off, weight_len = append_aligned(weights.tobytes())
    ibm_off, ibm_len = append_aligned(ibm.tobytes())

    uv = None
    uv_off = uv_len = image_off = image_len = None
    texture_file = pathlib.Path(texture_path) if texture_path else None
    if texture_file and texture_file.is_file():
        visual_uv = getattr(getattr(mesh, "visual", None), "uv", None)
        if visual_uv is not None and len(visual_uv) == len(vertices):
            uv = np.asarray(visual_uv, dtype=np.float32)
        else:
            center = vertices.mean(axis=0)
            centered = vertices - center
            x, y, z = centered[:, 0], centered[:, 1], centered[:, 2]
            radius = np.linalg.norm(centered, axis=1)
            radius = np.where(radius < 1e-8, 1e-8, radius)
            u = 0.5 + np.arctan2(x, z) / (2.0 * np.pi)
            v = 0.5 - np.arcsin(np.clip(y / radius, -1.0, 1.0)) / np.pi
            uv = np.stack([u, v], axis=1).astype(np.float32)
        uv_off, uv_len = append_aligned(uv.tobytes())
        image_off, image_len = append_aligned(texture_file.read_bytes())

    def add_view(offset: int, length: int, target=None) -> int:
        idx = len(gltf.bufferViews)
        gltf.bufferViews.append(BufferView(buffer=0, byteOffset=offset, byteLength=length, target=target))
        return idx

    bv_pos = add_view(pos_off, pos_len, ARRAY_BUFFER)
    bv_norm = add_view(norm_off, norm_len, ARRAY_BUFFER)
    bv_idx = add_view(idx_off, idx_len, ELEMENT_ARRAY_BUFFER)
    bv_joint = add_view(joint_off, joint_len, ARRAY_BUFFER)
    bv_weight = add_view(weight_off, weight_len, ARRAY_BUFFER)
    bv_ibm = add_view(ibm_off, ibm_len, None)
    bv_uv = add_view(uv_off, uv_len, ARRAY_BUFFER) if uv is not None else None
    bv_image = add_view(image_off, image_len, None) if image_off is not None else None

    gltf.accessors.append(Accessor(
        bufferView=bv_pos, componentType=FLOAT, count=len(vertices), type="VEC3",
        max=vertices.max(axis=0).tolist(), min=vertices.min(axis=0).tolist(),
    ))
    gltf.accessors.append(Accessor(bufferView=bv_norm, componentType=FLOAT, count=len(vertices), type="VEC3"))
    gltf.accessors.append(Accessor(bufferView=bv_idx, componentType=UNSIGNED_INT, count=len(faces), type="SCALAR"))
    gltf.accessors.append(Accessor(bufferView=bv_joint, componentType=UNSIGNED_SHORT, count=len(vertices), type="VEC4"))
    gltf.accessors.append(Accessor(bufferView=bv_weight, componentType=FLOAT, count=len(vertices), type="VEC4"))
    gltf.accessors.append(Accessor(bufferView=bv_ibm, componentType=FLOAT, count=skeleton["num_joints"], type="MAT4"))
    uv_accessor = None
    if bv_uv is not None:
        uv_accessor = len(gltf.accessors)
        gltf.accessors.append(Accessor(bufferView=bv_uv, componentType=FLOAT, count=len(vertices), type="VEC2"))

    gltf.skins.append(Skin(
        name="humanoid_skin",
        joints=list(range(skeleton["num_joints"])),
        inverseBindMatrices=5,
    ))

    names = skeleton["names"]
    parents = skeleton["parents"]
    positions = skeleton["positions"]
    for i in range(skeleton["num_joints"]):
        parent_idx = int(parents[i])
        local_pos = positions[i] - positions[parent_idx] if parent_idx >= 0 else positions[i]
        gltf.nodes.append(Node(name=names[i], translation=local_pos.tolist(), children=[]))
    for i in range(skeleton["num_joints"]):
        parent_idx = int(parents[i])
        if parent_idx >= 0:
            gltf.nodes[parent_idx].children.append(i)

    attrs = {"POSITION": 0, "NORMAL": 1, "JOINTS_0": 3, "WEIGHTS_0": 4}
    if uv_accessor is not None:
        attrs["TEXCOORD_0"] = uv_accessor

    material_index = None
    if bv_image is not None:
        gltf.images.append(Image(bufferView=bv_image, mimeType="image/png", name="avatar_texture"))
        gltf.samplers.append(Sampler())
        gltf.textures.append(Texture(source=0, sampler=0, name="avatar_texture"))
        gltf.materials.append(Material(
            name="avatar_material",
            pbrMetallicRoughness=PbrMetallicRoughness(
                baseColorTexture=TextureInfo(index=0),
                metallicFactor=0.0,
                roughnessFactor=1.0,
            ),
        ))
        material_index = 0

    primitive = Primitive(attributes=attrs, indices=2, mode=4, material=material_index)
    gltf.meshes.append(Mesh(name="avatar", primitives=[primitive]))

    mesh_node_idx = len(gltf.nodes)
    gltf.nodes.append(Node(name="avatar_mesh", mesh=0, skin=0, translation=[0.0, 0.0, 0.0]))
    root_idx = len(gltf.nodes)
    gltf.nodes.append(Node(name="root", children=[0, mesh_node_idx]))
    gltf.scenes.append(Scene(name="main_scene", nodes=[root_idx]))
    gltf.scene = 0

    gltf.buffers.append(Buffer(byteLength=len(buffer_data)))
    gltf.set_binary_blob(bytes(buffer_data))
    gltf.save_binary(output_path)

    output = pathlib.Path(output_path)
    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError("Rigged GLB export produced no artifact")

    # Re-import the exact binary that later stages will consume.
    check = GLTF2().load(str(output))
    if len(check.skins or []) != 1:
        raise RuntimeError("Rigged GLB re-import lost its skin")
    if not check.meshes or not check.meshes[0].primitives:
        raise RuntimeError("Rigged GLB re-import lost its mesh")
    attrs = check.meshes[0].primitives[0].attributes
    joints_accessor = getattr(attrs, "JOINTS_0", None)
    weights_accessor = getattr(attrs, "WEIGHTS_0", None)
    if joints_accessor is None or weights_accessor is None:
        raise RuntimeError("Rigged GLB re-import lost JOINTS_0/WEIGHTS_0")
    if check.accessors[joints_accessor].componentType != UNSIGNED_SHORT:
        raise RuntimeError("JOINTS_0 must use UNSIGNED_SHORT")
    if check.accessors[weights_accessor].componentType != FLOAT:
        raise RuntimeError("WEIGHTS_0 must use FLOAT")
    return str(output)

def rig_avatar(mesh_path: str, output_path: str, texture_path: str | None = None) -> str:
    """
    메시에 기본 휴머노이드 리그를 추가합니다.
    
    Args:
        mesh_path: 입력 메시 파일 경로 (GLB/GLTF)
        output_path: 출력 파일 경로
    
    Returns:
        출력 파일 경로
    """
    if not TRIMESH_AVAILABLE:
        raise ImportError(
            "trimesh가 설치되지 않았습니다. pip install trimesh"
        )
    if not PYGLTFLIB_AVAILABLE:
        raise ImportError(
            "pygltflib이 설치되지 않았습니다. pip install pygltflib"
        )
    
    # 메시 로드
    mesh = trimesh.load(mesh_path)
    
    # Scene인 경우 첫 번째 메시 추출
    if isinstance(mesh, trimesh.Scene):
        geometries = list(mesh.geometry.values())
        if len(geometries) > 0:
            mesh = geometries[0]
        else:
            raise ValueError("Scene에 메시가 없습니다.")
    
    # 메시 바운드 계산
    bounds = mesh.bounds  # (2, 3) - [min, max]
    
    # 휴머노이드 뼈대 생성
    skeleton = create_humanoid_skeleton(bounds)
    
    # 스킨 가중치 계산
    joint_indices, joint_weights = compute_skin_weights(
        mesh.vertices, skeleton, max_influences=4
    )
    
    # 스킨이 포함된 GLB 생성
    result = create_gltf_with_skin(
        mesh, skeleton, joint_indices, joint_weights, output_path,
        texture_path=texture_path,
    )
    
    return result
