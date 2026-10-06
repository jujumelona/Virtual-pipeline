"""Avatar rigging module for VTuber Pipeline."""

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
    from pygltflib import ARRAY_BUFFER, ELEMENT_ARRAY_BUFFER, FLOAT, UNSIGNED_INT
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
        ("leftEye", 5, np.array([center_x - height * 0.03, base_y + height * 0.88, center_z + height * 0.05])),
        ("rightEye", 5, np.array([center_x + height * 0.03, base_y + height * 0.88, center_z + height * 0.05])),
        
        # 왼쪽 팔
        ("leftShoulder", 3, np.array([center_x - height * 0.08, base_y + height * 0.72, center_z])),
        ("leftUpperArm", 8, np.array([center_x - height * 0.12, base_y + height * 0.70, center_z])),
        ("leftLowerArm", 9, np.array([center_x - height * 0.16, base_y + height * 0.60, center_z])),
        ("leftHand", 10, np.array([center_x - height * 0.18, base_y + height * 0.50, center_z])),
        
        # 오른쪽 팔
        ("rightShoulder", 3, np.array([center_x + height * 0.08, base_y + height * 0.72, center_z])),
        ("rightUpperArm", 12, np.array([center_x + height * 0.12, base_y + height * 0.70, center_z])),
        ("rightLowerArm", 13, np.array([center_x + height * 0.16, base_y + height * 0.60, center_z])),
        ("rightHand", 14, np.array([center_x + height * 0.18, base_y + height * 0.50, center_z])),
        
        # 왼쪽 다리
        ("leftUpperLeg", 0, np.array([center_x - height * 0.08, base_y + height * 0.48, center_z])),
        ("leftLowerLeg", 16, np.array([center_x - height * 0.08, base_y + height * 0.28, center_z])),
        ("leftFoot", 17, np.array([center_x - height * 0.08, base_y + height * 0.08, center_z])),
        ("leftToes", 18, np.array([center_x - height * 0.08, base_y + height * 0.02, center_z + height * 0.03])),
        
        # 오른쪽 다리
        ("rightUpperLeg", 0, np.array([center_x + height * 0.08, base_y + height * 0.48, center_z])),
        ("rightLowerLeg", 20, np.array([center_x + height * 0.08, base_y + height * 0.28, center_z])),
        ("rightFoot", 21, np.array([center_x + height * 0.08, base_y + height * 0.08, center_z])),
        ("rightToes", 22, np.array([center_x + height * 0.08, base_y + height * 0.02, center_z + height * 0.03])),
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
    """
    거리 기반 스키닝 가중치를 계산합니다.
    
    Args:
        vertices: (N, 3) 정점 위치 배열
        skeleton: create_humanoid_skeleton() 결과
        max_influences: 최대 영향 뼈 수 (기본 4)
    
    Returns:
        (joint_indices, joint_weights) - 각각 (N, max_influences) 형태
    """
    num_vertices = len(vertices)
    num_joints = skeleton["num_joints"]
    positions = skeleton["positions"]
    
    # 각 정점에서 각 뼈까지의 거리 계산
    distances = np.zeros((num_vertices, num_joints), dtype=np.float32)
    
    for j in range(num_joints):
        bone_pos = positions[j]
        # 정점과 뼈 위치 간 유클리드 거리
        diff = vertices - bone_pos
        distances[:, j] = np.sqrt(np.sum(diff ** 2, axis=1))
    
    # 거리 역수로 가중치 계산 (가까울수록 큰 가중치)
    # 0으로 나누기 방지를 위해 작은 값 추가
    epsilon = 1e-6
    weights = 1.0 / (distances + epsilon)
    
    # 가장 큰 max_influences 개의 가중치만 선택
    joint_indices = np.zeros((num_vertices, max_influences), dtype=np.uint16)
    joint_weights = np.zeros((num_vertices, max_influences), dtype=np.float32)
    
    for i in range(num_vertices):
        # 가중치가 큰 순서대로 인덱스 정렬
        sorted_indices = np.argsort(weights[i])[::-1][:max_influences]
        
        # 상위 가중치 추출
        top_weights = weights[i, sorted_indices]
        
        # 정규화 (합이 1이 되도록)
        weight_sum = np.sum(top_weights)
        if weight_sum > 0:
            top_weights = top_weights / weight_sum
        else:
            # 모든 거리가 같으면 균등 분배
            top_weights = np.ones(max_influences, dtype=np.float32) / max_influences
        
        joint_indices[i] = sorted_indices
        joint_weights[i] = top_weights
    
    return joint_indices, joint_weights


def create_gltf_with_skin(
    mesh: Any,
    skeleton: Dict[str, Any],
    joint_indices: np.ndarray,
    joint_weights: np.ndarray,
    output_path: str
) -> str:
    """
    스킨이 포함된 glTF 파일을 생성합니다.
    
    Args:
        mesh: trimesh.Trimesh 객체
        skeleton: 뼈대 정보
        joint_indices: 정점별 뼈 인덱스
        joint_weights: 정점별 가중치
        output_path: 출력 파일 경로
    
    Returns:
        출력 파일 경로
    """
    if not PYGLTFLIB_AVAILABLE:
        raise ImportError("pygltflib이 설치되지 않았습니다. pip install pygltflib")
    
    # glTF 객체 생성
    gltf = GLTF2()
    
    # 버퍼 생성
    buffer_data = bytearray()
    
    # 1. 정점 위치
    vertices = mesh.vertices.astype(np.float32)
    vertices_bytes = vertices.tobytes()
    vertices_byte_offset = len(buffer_data)
    vertices_byte_length = len(vertices_bytes)
    buffer_data.extend(vertices_bytes)
    
    # 2. 법선
    normals = mesh.vertex_normals.astype(np.float32)
    normals_bytes = normals.tobytes()
    normals_byte_offset = len(buffer_data)
    normals_byte_length = len(normals_bytes)
    buffer_data.extend(normals_bytes)
    
    # 3. 인덱스
    faces = mesh.faces.astype(np.uint32)
    indices_bytes = faces.flatten().tobytes()
    indices_byte_offset = len(buffer_data)
    indices_byte_length = len(indices_bytes)
    buffer_data.extend(indices_bytes)
    
    # 4. 조인트 인덱스 (VEC4)
    joints_bytes = joint_indices.tobytes()
    joints_byte_offset = len(buffer_data)
    joints_byte_length = len(joints_bytes)
    buffer_data.extend(joints_bytes)
    
    # 5. 조인트 가중치 (VEC4)
    weights_bytes = joint_weights.tobytes()
    weights_byte_offset = len(buffer_data)
    weights_byte_length = len(weights_bytes)
    buffer_data.extend(weights_bytes)
    
    # 6. inverseBindMatrices
    ibm = skeleton["inverse_bind_matrices"].astype(np.float32)
    ibm_bytes = ibm.tobytes()
    ibm_byte_offset = len(buffer_data)
    ibm_byte_length = len(ibm_bytes)
    buffer_data.extend(ibm_bytes)
    
    # BufferViews 생성
    # 정점 위치
    bv_vertices = BufferView(
        buffer=0,
        byteOffset=vertices_byte_offset,
        byteLength=vertices_byte_length,
        target=ARRAY_BUFFER
    )
    gltf.bufferViews.append(bv_vertices)
    
    # 법선
    bv_normals = BufferView(
        buffer=0,
        byteOffset=normals_byte_offset,
        byteLength=normals_byte_length,
        target=ARRAY_BUFFER
    )
    gltf.bufferViews.append(bv_normals)
    
    # 인덱스
    bv_indices = BufferView(
        buffer=0,
        byteOffset=indices_byte_offset,
        byteLength=indices_byte_length,
        target=ELEMENT_ARRAY_BUFFER
    )
    gltf.bufferViews.append(bv_indices)
    
    # 조인트 인덱스
    bv_joints = BufferView(
        buffer=0,
        byteOffset=joints_byte_offset,
        byteLength=joints_byte_length,
        target=ARRAY_BUFFER
    )
    gltf.bufferViews.append(bv_joints)
    
    # 조인트 가중치
    bv_weights = BufferView(
        buffer=0,
        byteOffset=weights_byte_offset,
        byteLength=weights_byte_length,
        target=ARRAY_BUFFER
    )
    gltf.bufferViews.append(bv_weights)
    
    # inverseBindMatrices
    bv_ibm = BufferView(
        buffer=0,
        byteOffset=ibm_byte_offset,
        byteLength=ibm_byte_length,
        target=None  # 버퍼 뷰 타겟 없음
    )
    gltf.bufferViews.append(bv_ibm)
    
    # Accessors 생성
    num_vertices = len(vertices)
    num_indices = len(faces.flatten())
    num_joints = skeleton["num_joints"]
    
    # 정점 위치 accessor
    acc_positions = Accessor(
        bufferView=0,
        componentType=FLOAT,
        count=num_vertices,
        type="VEC3",
        max=vertices.max(axis=0).tolist(),
        min=vertices.min(axis=0).tolist()
    )
    gltf.accessors.append(acc_positions)
    
    # 법선 accessor
    acc_normals = Accessor(
        bufferView=1,
        componentType=FLOAT,
        count=num_vertices,
        type="VEC3"
    )
    gltf.accessors.append(acc_normals)
    
    # 인덱스 accessor
    acc_indices = Accessor(
        bufferView=2,
        componentType=UNSIGNED_INT,
        count=num_indices,
        type="SCALAR"
    )
    gltf.accessors.append(acc_indices)
    
    # 조인트 인덱스 accessor (VEC4)
    acc_joints = Accessor(
        bufferView=3,
        componentType=UNSIGNED_INT,  # uint16을 unsigned int로
        count=num_vertices,
        type="VEC4"
    )
    gltf.accessors.append(acc_joints)
    
    # 조인트 가중치 accessor (VEC4)
    acc_weights = Accessor(
        bufferView=4,
        componentType=FLOAT,
        count=num_vertices,
        type="VEC4"
    )
    gltf.accessors.append(acc_weights)
    
    # inverseBindMatrices accessor
    acc_ibm = Accessor(
        bufferView=5,
        componentType=FLOAT,
        count=num_joints,
        type="MAT4"
    )
    gltf.accessors.append(acc_ibm)
    
    # Skin 생성
    skin = Skin(
        name="humanoid_skin",
        joints=list(range(num_joints)),  # 조인트 노드 인덱스
        inverseBindMatrices=5  # accessor 인덱스
    )
    gltf.skins.append(skin)
    
    # Nodes 생성 (뼈대)
    names = skeleton["names"]
    parents = skeleton["parents"]
    positions = skeleton["positions"]
    
    # 루트 노드부터 추가
    for i in range(num_joints):
        parent_idx = parents[i]
        local_pos = positions[i].copy()
        
        if parent_idx >= 0:
            # 로컬 위치 계산
            local_pos = positions[i] - positions[parent_idx]
        
        node = Node(
            name=names[i],
            translation=local_pos.tolist(),
            children=[]
        )
        gltf.nodes.append(node)
    
    # 부모-자식 관계 설정
    for i in range(num_joints):
        parent_idx = parents[i]
        if parent_idx >= 0:
            if gltf.nodes[parent_idx].children is None:
                gltf.nodes[parent_idx].children = []
            gltf.nodes[parent_idx].children.append(i)
    
    # Mesh 노드 생성
    mesh_node = Node(
        name="avatar_mesh",
        mesh=0,
        skin=0,
        translation=[0.0, 0.0, 0.0]
    )
    gltf.nodes.append(mesh_node)
    
    # Mesh 생성
    from pygltflib import Mesh, Primitive
    primitive = Primitive(
        attributes={"POSITION": 0, "NORMAL": 1, "JOINTS_0": 3, "WEIGHTS_0": 4},
        indices=2,
        mode=4  # TRIANGLES
    )
    mesh_obj = Mesh(
        name="avatar",
        primitives=[primitive]
    )
    gltf.meshes.append(mesh_obj)
    
    # Scene 설정
    # 루트 노드들 (hips와 mesh_node)
    root_children = [0, num_joints]  # hips 노드와 mesh 노드
    root_node = Node(
        name="root",
        children=root_children
    )
    gltf.nodes.append(root_node)
    
    # Scene
    from pygltflib import Scene
    scene = Scene(
        name="main_scene",
        nodes=[num_joints + 1]  # root 노드
    )
    gltf.scenes.append(scene)
    gltf.scene = 0
    
    # Buffer 설정
    buffer = Buffer(
        byteLength=len(buffer_data)
    )
    gltf.buffers.append(buffer)
    
    # GLB로 저장
    gltf.set_binary_blob(bytes(buffer_data))
    gltf.save(output_path)
    
    return output_path


def rig_avatar(mesh_path: str, output_path: str) -> str:
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
        mesh, skeleton, joint_indices, joint_weights, output_path
    )
    
    return result
