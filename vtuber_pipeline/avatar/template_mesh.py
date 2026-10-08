"""Canonical VTuber template mesh support.

Production uses the pinned CC0 MakeHuman base mesh as the topology seed.
The procedural sphere/cylinder/box generator is retained only as a small
test fixture helper and is never selected by the production resolver.
"""

from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Tuple
import hashlib
import json
import os
import pathlib
import urllib.request
import numpy as np

try:
    import trimesh
    from trimesh import creation
    TRIMESH_AVAILABLE = True
except ImportError:
    trimesh = None
    TRIMESH_AVAILABLE = False

try:
    from scipy import sparse
    SCIPY_AVAILABLE = True
except ImportError:
    sparse = None
    SCIPY_AVAILABLE = False


@dataclass
class BoneInfo:
    """Bone 정보를 담는 데이터클래스."""
    name: str
    parent: Optional[str]
    head: np.ndarray  # bone head position (tail of parent)
    tail: np.ndarray  # bone tail position
    children: List[str] = None
    
    def __post_init__(self):
        if self.children is None:
            self.children = []


# Canonical VTuber bone hierarchy
CANONICAL_BONE_HIERARCHY: Dict[str, BoneInfo] = {
    "hips": BoneInfo("hips", None, np.array([0.0, 0.0, 0.0]), np.array([0.0, 0.05, 0.0])),
    "spine": BoneInfo("spine", "hips", np.array([0.0, 0.05, 0.0]), np.array([0.0, 0.10, 0.0])),
    "chest": BoneInfo("chest", "spine", np.array([0.0, 0.10, 0.0]), np.array([0.0, 0.15, 0.0])),
    "neck": BoneInfo("neck", "chest", np.array([0.0, 0.15, 0.0]), np.array([0.0, 0.18, 0.0])),
    "head": BoneInfo("head", "neck", np.array([0.0, 0.18, 0.0]), np.array([0.0, 0.26, 0.0])),
    "leftEye": BoneInfo("leftEye", "head", np.array([0.03, 0.22, 0.06]), np.array([0.03, 0.22, 0.08])),
    "rightEye": BoneInfo("rightEye", "head", np.array([-0.03, 0.22, 0.06]), np.array([-0.03, 0.22, 0.08])),
}


def create_uv_sphere(radius: float, subdivisions: int = 2) -> trimesh.Trimesh:
    """UV sphere 메시를 생성합니다.
    
    Args:
        radius: 구의 반지름
        subdivisions: 세분화 수준
        
    Returns:
        trimesh.Trimesh 객체
    """
    if not TRIMESH_AVAILABLE:
        raise ImportError("trimesh가 설치되지 않았습니다. pip install trimesh")
    
    # trimesh.creation.uv_sphere 사용
    mesh = creation.uv_sphere(radius=radius, count=[16 * (subdivisions + 1), 8 * (subdivisions + 1)])
    return mesh


def create_cylinder(radius: float, height: float, sections: int = 16) -> trimesh.Trimesh:
    """원기둥 메시를 생성합니다.
    
    Args:
        radius: 원기둥 반지름
        height: 원기둥 높이
        sections: 단면 분할 수
        
    Returns:
        trimesh.Trimesh 객체
    """
    if not TRIMESH_AVAILABLE:
        raise ImportError("trimesh가 설치되지 않았습니다. pip install trimesh")
    
    mesh = creation.cylinder(radius=radius, height=height, sections=sections)
    return mesh


def create_box(extents: Tuple[float, float, float]) -> trimesh.Trimesh:
    """박스 메시를 생성합니다.
    
    Args:
        extents: (width, height, depth) 크기
        
    Returns:
        trimesh.Trimesh 객체
    """
    if not TRIMESH_AVAILABLE:
        raise ImportError("trimesh가 설치되지 않았습니다. pip install trimesh")
    
    mesh = creation.box(extents=extents)
    return mesh


def merge_meshes(meshes: List[trimesh.Trimesh]) -> trimesh.Trimesh:
    """여러 메시를 하나로 병합합니다.
    
    Args:
        meshes: 병합할 메시 리스트
        
    Returns:
        병합된 trimesh.Trimesh 객체
    """
    if not TRIMESH_AVAILABLE:
        raise ImportError("trimesh가 설치되지 않았습니다. pip install trimesh")
    
    # trimesh.util.concatenate로 메시 병합
    merged = trimesh.util.concatenate(meshes)
    return merged


def compute_vertex_groups(
    vertices: np.ndarray,
    bones: Dict[str, BoneInfo],
    max_influence: int = 4,
    falloff_distance: float = 0.1
) -> Dict[str, np.ndarray]:
    """거리 기반 버텍스 그룹 가중치를 계산합니다.
    
    각 버텍스에 대해 가장 가까운 뼈들로부터 거리 기반 가중치를 할당합니다.
    
    Args:
        vertices: (N, 3) 버텍스 위치 배열
        bones: 뼈 이름 -> BoneInfo 딕셔너리
        max_influence: 각 버텍스에 영향을 주는 최대 뼈 수
        falloff_distance: 가중치 감소 거리
        
    Returns:
        뼈 이름 -> 가중치 배열 딕셔너리
    """
    n_vertices = len(vertices)
    vertex_groups = {}
    
    # 각 뼈에 대한 거리 계산
    bone_distances = {}
    for bone_name, bone_info in bones.items():
        # 뼈의 head와 tail 사이의 선분에 대한 거리 계산
        head = bone_info.head
        tail = bone_info.tail
        
        # 각 버텍스에서 뼈 선분까지의 거리 계산
        distances = _point_to_segment_distances(vertices, head, tail)
        bone_distances[bone_name] = distances
    
    # 각 버텍스에 대해 가중치 계산
    for bone_name in bones.keys():
        vertex_groups[bone_name] = np.zeros(n_vertices, dtype=np.float32)
    
    for i in range(n_vertices):
        # 이 버텍스에 대한 모든 뼈까지의 거리
        distances = np.array([bone_distances[bn][i] for bn in bones.keys()])
        
        # 가장 가까운 max_influence 개의 뼈 선택
        closest_indices = np.argsort(distances)[:max_influence]
        closest_distances = distances[closest_indices]
        
        # 거리 기반 가중치 계산 (역거리 가중치)
        weights = np.exp(-closest_distances / falloff_distance)
        
        # 정규화
        weights = weights / np.sum(weights)
        
        # 가중치 할당
        bone_names = list(bones.keys())
        for j, idx in enumerate(closest_indices):
            bone_name = bone_names[idx]
            vertex_groups[bone_name][i] = weights[j]
    
    return vertex_groups


def _point_to_segment_distances(points: np.ndarray, seg_start: np.ndarray, seg_end: np.ndarray) -> np.ndarray:
    """점들에서 선분까지의 거리를 계산합니다.
    
    Args:
        points: (N, 3) 점 위치 배열
        seg_start: 선분 시작점
        seg_end: 선분 끝점
        
    Returns:
        (N,) 거리 배열
    """
    # 선분 벡터
    seg_vec = seg_end - seg_start
    seg_len = np.linalg.norm(seg_vec)
    
    if seg_len < 1e-10:
        # 뼈가 점인 경우
        return np.linalg.norm(points - seg_start, axis=1)
    
    seg_unit = seg_vec / seg_len
    
    # 각 점에서 선분 시작점까지의 벡터
    point_vecs = points - seg_start
    
    # 선분 방향으로의 투영
    projections = np.dot(point_vecs, seg_unit)
    
    # 선분 내부로 클램핑
    projections = np.clip(projections, 0, seg_len)
    
    # 선분 위의 가장 가까운 점
    closest_points = seg_start + np.outer(projections, seg_unit)
    
    # 거리 계산
    distances = np.linalg.norm(points - closest_points, axis=1)
    
    return distances


def create_canonical_template(
    output_path: Optional[str] = None,
    head_radius: float = 0.08,
    neck_radius: float = 0.02,
    neck_height: float = 0.05,
    body_extents: Tuple[float, float, float] = (0.15, 0.12, 0.08)
) -> Dict[str, Any]:
    """Create a minimal procedural test template.
    
    This helper is for unit tests and geometry smoke tests only. Production
    code must use get_template_path(), which resolves the pinned CC0
    MakeHuman-derived canonical template.
    
    절차적 메시 생성:
    - Head: UV sphere (r=0.08)
    - Neck: Cylinder (r=0.02, h=0.05)
    - Body: Box (0.15 x 0.12 x 0.08)
    
    뼈 계층 구조:
    - hips -> spine -> chest -> neck -> head
    - leftEye, rightEye (head의 자식)
    
    Expression vertex groups:
    - upper_eyelid_L/R, lower_eyelid_L/R
    - upper_lip, lower_lip, mouth_corners
    
    Args:
        output_path: 출력 GLB 파일 경로 (선택)
        head_radius: 머리 구 반지름
        neck_radius: 목 원기둥 반지름
        neck_height: 목 원기둥 높이
        body_extents: (width, height, depth) 몸통 박스 크기
        
    Returns:
        생성 결과 딕셔너리
    """
    if not TRIMESH_AVAILABLE:
        return {
            "status": "error",
            "error": "trimesh가 설치되지 않았습니다. pip install trimesh"
        }
    
    result = {
        "status": "pending",
        "components": {}
    }
    
    try:
        # 1. 머리 (UV Sphere) - Y축으로 위치 조정 (목 위에)
        head = create_uv_sphere(radius=head_radius, subdivisions=2)
        # 머리 중심을 Y=0.18 + head_radius = 0.26 (머리 상단이 약 0.34)
        head_center_y = 0.18 + neck_height + head_radius  # 목 끝 + 머리 반지름
        head.apply_translation([0, head_center_y, 0])
        result["components"]["head"] = {
            "type": "uv_sphere",
            "radius": head_radius,
            "center": [0, head_center_y, 0],
            "vertices": len(head.vertices),
            "faces": len(head.faces)
        }
        
        # 2. 목 (Cylinder) - 몸통 위에서 머리 아래까지
        neck = create_cylinder(radius=neck_radius, height=neck_height, sections=12)
        # 목 중심 위치: 몸통 상단(0.12) + neck_height/2
        neck_center_y = 0.12 + neck_height / 2
        neck.apply_translation([0, neck_center_y, 0])
        result["components"]["neck"] = {
            "type": "cylinder",
            "radius": neck_radius,
            "height": neck_height,
            "center": [0, neck_center_y, 0],
            "vertices": len(neck.vertices),
            "faces": len(neck.faces)
        }
        
        # 3. 몸통 (Box) - 중심이 Y=0.06 (하단이 0)
        body = create_box(extents=body_extents)
        # 몸통 중심: 상단이 목 시작점(0.12)이 되도록
        body_center_y = body_extents[1] / 2  # 0.06
        body.apply_translation([0, body_center_y, 0])
        result["components"]["body"] = {
            "type": "box",
            "extents": list(body_extents),
            "center": [0, body_center_y, 0],
            "vertices": len(body.vertices),
            "faces": len(body.faces)
        }
        
        # 4. 메시 병합
        merged_mesh = merge_meshes([body, neck, head])
        
        # 5. 버텍스 그룹 계산
        # 뼈 위치를 메시에 맞게 조정
        adjusted_bones = _adjust_bone_positions(CANONICAL_BONE_HIERARCHY, head_center_y, neck_center_y, body_center_y)
        vertex_groups = compute_vertex_groups(merged_mesh.vertices, adjusted_bones)
        
        # 6. Expression vertex groups 계산 (메시 영역 기반 휴리스틱)
        expression_groups = compute_expression_vertex_groups(
            merged_mesh.vertices, 
            head_center_y, 
            head_radius
        )
        
        # 7. 결과 저장
        result["vertex_count"] = len(merged_mesh.vertices)
        result["face_count"] = len(merged_mesh.faces)
        result["bones"] = list(adjusted_bones.keys())
        result["vertex_groups"] = {k: v.tolist() for k, v in vertex_groups.items()}
        result["expression_groups"] = {k: v.tolist() for k, v in expression_groups.items()}
        
        # 8. GLB로 내보내기
        if output_path:
            output_dir = pathlib.Path(output_path).parent
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # 메시에 버텍스 그룹 정보를 메타데이터로 저장
            # (GLB는 직접 스킨 가중치를 저장하지 않으므로 별도 파일로 저장)
            merged_mesh.export(output_path)
            result["output_path"] = str(output_path)
            
            # 버텍스 그룹을 별도 JSON으로 저장
            weights_path = output_dir / "vertex_weights.json"
            import json
            with open(weights_path, 'w') as f:
                json.dump(result["vertex_groups"], f)
            result["weights_path"] = str(weights_path)
        
        result["status"] = "complete"
        
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
    
    return result


def compute_expression_vertex_groups(
    vertices: np.ndarray,
    head_center_y: float,
    head_radius: float
) -> Dict[str, np.ndarray]:
    """Compute expression vertex groups based on mesh region heuristics.
    
    Identifies vertices for facial expression regions:
    - upper_eyelid_L/R, lower_eyelid_L/R
    - upper_lip, lower_lip, mouth_corners
    
    Uses spatial heuristics based on head position and radius.
    
    Args:
        vertices: (N, 3) vertex position array
        head_center_y: Y coordinate of head center
        head_radius: Radius of head sphere
        
    Returns:
        Dictionary mapping expression group names to vertex index arrays
    """
    n_vertices = len(vertices)
    expression_groups = {
        "upper_eyelid_L": [],
        "lower_eyelid_L": [],
        "upper_eyelid_R": [],
        "lower_eyelid_R": [],
        "upper_lip": [],
        "lower_lip": [],
        "mouth_corners": []
    }
    
    # Define facial region boundaries relative to head center
    # Eye region: Y at ~0.6 * head_radius above center, Z at front
    eye_y = head_center_y + 0.02  # Slightly above head center
    eye_z = head_radius * 0.7  # Front of head
    eye_y_range = head_radius * 0.15
    
    # Left eye (positive X)
    left_eye_x = head_radius * 0.35
    # Right eye (negative X)  
    right_eye_x = -head_radius * 0.35
    
    # Mouth region: Y at ~0.1 * head_radius below center, Z at front
    mouth_y = head_center_y - 0.03
    mouth_z = head_radius * 0.75
    mouth_y_range = head_radius * 0.1
    
    for i, v in enumerate(vertices):
        x, y, z = v
        
        # Skip vertices not in head region
        if y < head_center_y - head_radius * 0.3:
            continue
        if z < head_radius * 0.3:  # Must be on front of face
            continue
            
        # Check eye regions
        # Left eye
        if (abs(x - left_eye_x) < head_radius * 0.15 and
            abs(y - eye_y) < eye_y_range and
            abs(z - eye_z) < head_radius * 0.2):
            if y >= eye_y:
                expression_groups["upper_eyelid_L"].append(i)
            else:
                expression_groups["lower_eyelid_L"].append(i)
                
        # Right eye
        if (abs(x - right_eye_x) < head_radius * 0.15 and
            abs(y - eye_y) < eye_y_range and
            abs(z - eye_z) < head_radius * 0.2):
            if y >= eye_y:
                expression_groups["upper_eyelid_R"].append(i)
            else:
                expression_groups["lower_eyelid_R"].append(i)
                
        # Check mouth region
        if (abs(x) < head_radius * 0.25 and
            abs(y - mouth_y) < mouth_y_range and
            abs(z - mouth_z) < head_radius * 0.15):
            if y >= mouth_y:
                expression_groups["upper_lip"].append(i)
            else:
                expression_groups["lower_lip"].append(i)
                
        # Mouth corners (wider X range)
        if (abs(y - mouth_y) < mouth_y_range and
            abs(z - mouth_z) < head_radius * 0.15):
            if abs(x) > head_radius * 0.15 and abs(x) < head_radius * 0.3:
                expression_groups["mouth_corners"].append(i)
    
    # Convert to numpy arrays
    return {k: np.array(v, dtype=np.int32) for k, v in expression_groups.items()}


def _adjust_bone_positions(
    bones: Dict[str, BoneInfo],
    head_center_y: float,
    neck_center_y: float,
    body_center_y: float
) -> Dict[str, BoneInfo]:
    """메시 위치에 맞게 뼈 위치를 조정합니다.
    
    Args:
        bones: 원본 뼈 딕셔너리
        head_center_y: 머리 중심 Y 위치
        neck_center_y: 목 중심 Y 위치
        body_center_y: 몸통 중심 Y 위치
        
    Returns:
        조정된 뼈 딕셔너리
    """
    adjusted = {}
    
    # hips: 몸통 하단 (Y=0)
    adjusted["hips"] = BoneInfo(
        "hips", None,
        np.array([0.0, 0.0, 0.0]),
        np.array([0.0, 0.03, 0.0]),
        ["spine"]
    )
    
    # spine: 몸통 하중앙
    adjusted["spine"] = BoneInfo(
        "spine", "hips",
        np.array([0.0, 0.03, 0.0]),
        np.array([0.0, 0.06, 0.0]),
        ["chest"]
    )
    
    # chest: 몸통 상중앙
    adjusted["chest"] = BoneInfo(
        "chest", "spine",
        np.array([0.0, 0.06, 0.0]),
        np.array([0.0, 0.12, 0.0]),
        ["neck"]
    )
    
    # neck: 목 위치
    adjusted["neck"] = BoneInfo(
        "neck", "chest",
        np.array([0.0, 0.12, 0.0]),
        np.array([0.0, neck_center_y + 0.025, 0.0]),  # 목 상단
        ["head"]
    )
    
    # head: 머리 위치 (목 상단에서 머리 중심까지)
    adjusted["head"] = BoneInfo(
        "head", "neck",
        np.array([0.0, neck_center_y + 0.025, 0.0]),
        np.array([0.0, head_center_y, 0.0]),
        ["leftEye", "rightEye"]
    )
    
    # eyes: 머리 앞쪽에 위치 (눈은 머리 중심에서 앞쪽/Z+)
    head_top = head_center_y + 0.08  # 머리 상단
    eye_y = head_center_y  # 눈은 머리 중심 높이
    eye_z = 0.06  # 앞쪽으로
    
    adjusted["leftEye"] = BoneInfo(
        "leftEye", "head",
        np.array([0.03, eye_y, eye_z]),
        np.array([0.03, eye_y, eye_z + 0.02]),
        []
    )
    
    adjusted["rightEye"] = BoneInfo(
        "rightEye", "head",
        np.array([-0.03, eye_y, eye_z]),
        np.array([-0.03, eye_y, eye_z + 0.02]),
        []
    )
    
    return adjusted


def get_bone_hierarchy() -> Dict[str, Any]:
    """뼈 계층 구조를 반환합니다.
    
    Returns:
        뼈 계층 구조 딕셔너리
    """
    hierarchy = {}
    for bone_name, bone_info in CANONICAL_BONE_HIERARCHY.items():
        hierarchy[bone_name] = {
            "parent": bone_info.parent,
            "children": bone_info.children if bone_info.children else []
        }
    return hierarchy



def _parse_makehuman_obj(base_obj_path: str):
    """Parse MakeHuman base.obj and return body-only geometry plus joint centroids."""
    path = pathlib.Path(base_obj_path)
    raw_vertices: List[List[float]] = []
    body_faces: List[List[int]] = []
    joint_refs: Dict[str, set] = {}
    current_group: Optional[str] = None

    with path.open("r", encoding="utf-8", errors="strict") as handle:
        for line in handle:
            if line.startswith("v "):
                parts = line.strip().split()
                if len(parts) < 4:
                    raise ValueError("Malformed vertex line in MakeHuman base.obj")
                raw_vertices.append([float(parts[1]), float(parts[2]), float(parts[3])])
                continue

            if line.startswith("g "):
                current_group = line[2:].strip()
                continue

            if not line.startswith("f "):
                continue

            face: List[int] = []
            for token in line.strip().split()[1:]:
                raw = token.split("/", 1)[0]
                if not raw:
                    raise ValueError("Malformed face index in MakeHuman base.obj")
                parsed = int(raw)
                index = parsed - 1 if parsed > 0 else len(raw_vertices) + parsed
                if index < 0 or index >= len(raw_vertices):
                    raise ValueError("OBJ face index is out of range")
                face.append(index)

            if current_group == "body":
                if len(face) < 3:
                    continue
                for i in range(1, len(face) - 1):
                    body_faces.append([face[0], face[i], face[i + 1]])
            elif current_group and current_group.startswith("joint-"):
                joint_refs.setdefault(current_group, set()).update(face)

    if not raw_vertices or not body_faces:
        raise ValueError("MakeHuman base.obj does not contain usable body geometry")

    raw = np.asarray(raw_vertices, dtype=np.float64)
    used = sorted({index for face in body_faces for index in face})
    remap = {old: new for new, old in enumerate(used)}
    body_vertices = raw[np.asarray(used, dtype=int)]
    compact_faces = np.asarray(
        [[remap[index] for index in face] for face in body_faces],
        dtype=np.int64,
    )

    joint_centroids: Dict[str, np.ndarray] = {}
    for name, refs in joint_refs.items():
        indices = sorted(refs)
        if indices:
            joint_centroids[name] = raw[np.asarray(indices, dtype=int)].mean(axis=0)

    return body_vertices, compact_faces, joint_centroids


def _rotation_from_to(source: np.ndarray, target: np.ndarray) -> np.ndarray:
    """Return a stable 3x3 rotation matrix mapping source direction to target."""
    source = np.asarray(source, dtype=float)
    target = np.asarray(target, dtype=float)
    source_norm = np.linalg.norm(source)
    target_norm = np.linalg.norm(target)
    if source_norm <= 1e-10 or target_norm <= 1e-10:
        raise ValueError("Cannot align a zero-length limb segment")

    a = source / source_norm
    b = target / target_norm
    cross = np.cross(a, b)
    dot = float(np.clip(np.dot(a, b), -1.0, 1.0))
    cross_norm = float(np.linalg.norm(cross))

    if cross_norm <= 1e-10:
        if dot > 0.0:
            return np.eye(3)
        axis = np.array([1.0, 0.0, 0.0])
        if abs(a[0]) > 0.9:
            axis = np.array([0.0, 1.0, 0.0])
        axis = axis - a * np.dot(axis, a)
        axis /= np.linalg.norm(axis)
        return 2.0 * np.outer(axis, axis) - np.eye(3)

    k = cross / cross_norm
    K = np.array([
        [0.0, -k[2], k[1]],
        [k[2], 0.0, -k[0]],
        [-k[1], k[0], 0.0],
    ])
    angle = np.arctan2(cross_norm, dot)
    return np.eye(3) + np.sin(angle) * K + (1.0 - np.cos(angle)) * (K @ K)


def _point_segment_projection(points: np.ndarray, start: np.ndarray, end: np.ndarray):
    """Return clipped segment parameter and distance for each point."""
    points = np.asarray(points, dtype=float)
    start = np.asarray(start, dtype=float)
    end = np.asarray(end, dtype=float)
    vec = end - start
    length_sq = float(np.dot(vec, vec))
    if length_sq <= 1e-12:
        t = np.zeros(len(points), dtype=float)
        return t, np.linalg.norm(points - start, axis=1)
    t = ((points - start) @ vec) / length_sq
    clipped = np.clip(t, 0.0, 1.0)
    nearest = start + clipped[:, None] * vec
    return clipped, np.linalg.norm(points - nearest, axis=1)


def _smoothstep01(values: np.ndarray) -> np.ndarray:
    values = np.clip(values, 0.0, 1.0)
    return values * values * (3.0 - 2.0 * values)


def _normalize_makehuman_arms_to_t_pose(
    vertices: np.ndarray,
    joint_centroids: Dict[str, np.ndarray],
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Straighten MakeHuman lowered arms into a VRM-compatible T-pose."""
    out = np.asarray(vertices, dtype=float).copy()
    report: Dict[str, Any] = {"sides": {}}

    for side, sign in (("l", 1.0), ("r", -1.0)):
        shoulder = joint_centroids.get(f"joint-{side}-shoulder")
        elbow = joint_centroids.get(f"joint-{side}-elbow")
        hand = joint_centroids.get(f"joint-{side}-hand")
        if shoulder is None or elbow is None or hand is None:
            raise ValueError(f"Missing MakeHuman arm joint helpers for side {side}")

        upper = elbow - shoulder
        lower = hand - elbow
        upper_len = float(np.linalg.norm(upper))
        lower_len = float(np.linalg.norm(lower))
        target_elbow = shoulder + np.array([sign * upper_len, 0.0, 0.0])
        target_hand = target_elbow + np.array([sign * lower_len, 0.0, 0.0])

        r_upper = _rotation_from_to(upper, target_elbow - shoulder)
        r_lower = _rotation_from_to(lower, target_hand - target_elbow)

        current = out.copy()
        t_upper, d_upper = _point_segment_projection(current, shoulder, elbow)
        t_lower, d_lower = _point_segment_projection(current, elbow, hand)

        side_coord = sign * current[:, 0]
        shoulder_coord = sign * float(shoulder[0])
        elbow_coord = sign * float(elbow[0])

        upper_radius = max(0.34 * upper_len, 0.35)
        lower_radius = max(0.40 * lower_len, 0.40)

        upper_mask = (
            (side_coord >= shoulder_coord * 0.78)
            & (d_upper <= upper_radius)
            & (side_coord <= elbow_coord + upper_radius)
        )
        lower_mask = (
            (side_coord >= elbow_coord - lower_radius * 0.55)
            & (
                (d_lower <= lower_radius)
                | (side_coord >= elbow_coord + lower_radius * 0.25)
            )
        )

        upper_transformed = shoulder + ((current - shoulder) @ r_upper.T)
        lower_transformed = target_elbow + ((current - elbow) @ r_lower.T)

        shoulder_blend = _smoothstep01(t_upper / 0.28)
        out[upper_mask] = (
            current[upper_mask] * (1.0 - shoulder_blend[upper_mask, None])
            + upper_transformed[upper_mask] * shoulder_blend[upper_mask, None]
        )

        elbow_blend = _smoothstep01(t_lower / 0.24)
        if np.any(lower_mask):
            upper_for_lower = upper_transformed[lower_mask]
            lower_for_lower = lower_transformed[lower_mask]
            blend = elbow_blend[lower_mask, None]
            out[lower_mask] = upper_for_lower * (1.0 - blend) + lower_for_lower * blend

        report["sides"][side] = {
            "shoulder": shoulder.tolist(),
            "elbow_before": elbow.tolist(),
            "hand_before": hand.tolist(),
            "elbow_after": target_elbow.tolist(),
            "hand_after": target_hand.tolist(),
            "upper_vertices": int(np.count_nonzero(upper_mask)),
            "lower_vertices": int(np.count_nonzero(lower_mask)),
        }

    return out, report



def create_canonical_template_from_makehuman(base_obj_path: str, output_path: str) -> Dict[str, Any]:
    """Create the production canonical VTuber mesh from pinned MakeHuman CC0 body.

    Only the upstream body group is exported. Joint/helper groups are used
    solely as anatomical landmarks. Arms are normalized into a VRM-compatible
    T-pose while topology and vertex ordering remain fixed.
    """
    if not TRIMESH_AVAILABLE:
        return {"status": "error", "error": "trimesh not available"}

    try:
        body_vertices, body_faces, joints = _parse_makehuman_obj(base_obj_path)
        tpose_vertices, tpose_report = _normalize_makehuman_arms_to_t_pose(
            body_vertices,
            joints,
        )

        bounds_min = tpose_vertices.min(axis=0)
        bounds_max = tpose_vertices.max(axis=0)
        height = float(bounds_max[1] - bounds_min[1])
        if height <= 1e-8:
            raise ValueError("MakeHuman body has zero height")

        # Enlarge only the cranial region; preserve neck/shoulder rest pose.
        head_threshold = bounds_min[1] + 0.84 * height
        head_mask = tpose_vertices[:, 1] >= head_threshold
        if np.count_nonzero(head_mask) < 32:
            raise ValueError("Unable to isolate MakeHuman cranial region")

        head_center = tpose_vertices[head_mask].mean(axis=0)
        adjusted = tpose_vertices.copy()
        head_scale = np.array([1.12, 1.08, 1.10], dtype=float)
        adjusted[head_mask] = (
            head_center
            + (adjusted[head_mask] - head_center) * head_scale
        )

        pmin = adjusted.min(axis=0)
        pmax = adjusted.max(axis=0)
        source_height = float(pmax[1] - pmin[1])
        target_height_m = 1.65
        scale_to_m = target_height_m / source_height
        adjusted *= scale_to_m

        pmin = adjusted.min(axis=0)
        pmax = adjusted.max(axis=0)
        adjusted[:, 0] -= float((pmin[0] + pmax[0]) * 0.5)
        adjusted[:, 1] -= float(pmin[1])
        adjusted[:, 2] -= float((pmin[2] + pmax[2]) * 0.5)

        mesh = trimesh.Trimesh(
            vertices=adjusted,
            faces=body_faces,
            process=False,
            validate=False,
        )
        if len(mesh.vertices) == 0 or len(mesh.faces) == 0:
            raise ValueError("Canonical body mesh is empty")

        output = pathlib.Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        mesh.export(str(output))
        if not output.is_file() or output.stat().st_size == 0:
            raise RuntimeError("Canonical template export produced no file")

        check = trimesh.load(str(output), process=False)
        if isinstance(check, trimesh.Scene):
            geometries = list(check.geometry.values())
            if not geometries:
                raise RuntimeError("Canonical template GLB contains no geometry")
        elif len(check.vertices) == 0:
            raise RuntimeError("Canonical template GLB contains no vertices")

        return {
            "status": "complete",
            "output_path": str(output),
            "source": "makehuman_cc0_body_only",
            "vertex_count": int(len(mesh.vertices)),
            "face_count": int(len(mesh.faces)),
            "target_height_m": target_height_m,
            "t_pose": tpose_report,
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


MAKEHUMAN_CC0_COMMIT = "a8bc2d54ff0ac92e78ff71431b1023eda42bf482"
MAKEHUMAN_BASE_GIT_BLOB_SHA1 = "d26635e9326e3cca30778fd7b9c00062b03cce09"
CANONICAL_TEMPLATE_VERSION = "makehuman-a8bc2d54-body-tpose-v3"
MAKEHUMAN_BASE_URL = (
    "https://raw.githubusercontent.com/makehumancommunity/makehuman/"
    f"{MAKEHUMAN_CC0_COMMIT}/makehuman/data/3dobjs/base.obj"
)


def _git_blob_sha1(path: pathlib.Path) -> str:
    size = path.stat().st_size
    digest = hashlib.sha1()
    digest.update(f"blob {size}\0".encode("ascii"))
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_pinned_makehuman_base(path: pathlib.Path) -> pathlib.Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_file() or resolved.stat().st_size <= 0:
        raise FileNotFoundError(f"MakeHuman base.obj is missing or empty: {resolved}")
    actual = _git_blob_sha1(resolved)
    if actual != MAKEHUMAN_BASE_GIT_BLOB_SHA1:
        raise RuntimeError(
            "MakeHuman base.obj blob mismatch: "
            f"expected {MAKEHUMAN_BASE_GIT_BLOB_SHA1}, got {actual}"
        )
    return resolved


def _template_metadata_path(template_path: pathlib.Path) -> pathlib.Path:
    return template_path.with_name("template.meta.json")


def _cached_template_valid(template_path: pathlib.Path) -> bool:
    if not template_path.is_file() or template_path.stat().st_size <= 0:
        return False
    metadata_path = _template_metadata_path(template_path)
    if not metadata_path.is_file():
        return False
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except Exception:
        return False
    expected = {
        "canonical_template_version": CANONICAL_TEMPLATE_VERSION,
        "makehuman_commit": MAKEHUMAN_CC0_COMMIT,
        "makehuman_blob_sha1": MAKEHUMAN_BASE_GIT_BLOB_SHA1,
    }
    if any(metadata.get(key) != value for key, value in expected.items()):
        return False
    recorded = metadata.get("template_sha256")
    return (
        isinstance(recorded, str)
        and bool(recorded)
        and _file_sha256(template_path) == recorded
    )


def _write_template_metadata(template_path: pathlib.Path) -> None:
    metadata = {
        "canonical_template_version": CANONICAL_TEMPLATE_VERSION,
        "makehuman_commit": MAKEHUMAN_CC0_COMMIT,
        "makehuman_blob_sha1": MAKEHUMAN_BASE_GIT_BLOB_SHA1,
        "template_sha256": _file_sha256(template_path),
    }
    _template_metadata_path(template_path).write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _cache_root() -> pathlib.Path:
    """Return a writable cache root for generated canonical assets."""
    override = os.environ.get("VTUBER_PIPELINE_CACHE")
    if override:
        return pathlib.Path(override).expanduser().resolve()
    return pathlib.Path.home() / ".cache" / "vtuber-pipeline"


def _find_local_makehuman_base() -> Optional[pathlib.Path]:
    """Find a byte-identical copy of the pinned MakeHuman CC0 base mesh."""
    repo_root = pathlib.Path(__file__).resolve().parents[2]
    env_path = os.environ.get("MAKEHUMAN_BASE_OBJ")
    if env_path:
        return _require_pinned_makehuman_base(
            pathlib.Path(env_path).expanduser()
        )

    candidates = [
        repo_root / "assets" / "makehuman_cc0" / "base.obj",
        _cache_root() / "makehuman_cc0" / "base.obj",
    ]
    for candidate in candidates:
        if not candidate.is_file():
            continue
        try:
            return _require_pinned_makehuman_base(candidate)
        except (FileNotFoundError, RuntimeError):
            # A stale/corrupt implicit cache is not trusted; fetch the pinned
            # upstream bytes again instead.
            continue
    return None


def _download_pinned_makehuman_base() -> pathlib.Path:
    """Download only the pinned CC0 base.obj into the writable cache."""
    target = _cache_root() / "makehuman_cc0" / "base.obj"
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".obj.tmp")
    try:
        with urllib.request.urlopen(MAKEHUMAN_BASE_URL, timeout=60) as response:
            with tmp.open("wb") as handle:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
        if not tmp.is_file() or tmp.stat().st_size == 0:
            raise RuntimeError("Downloaded MakeHuman base.obj is empty")
        _require_pinned_makehuman_base(tmp)
        tmp.replace(target)
    finally:
        if tmp.exists():
            tmp.unlink()
    return target.resolve()


def ensure_template_exists() -> pathlib.Path:
    """Return a production canonical template, creating it when necessary.

    Resolution order:
    1. VTUBER_TEMPLATE_PATH, when explicitly supplied and existing.
    2. Versioned writable cache generated from pinned MakeHuman CC0 base.obj.

    The cache path contains CANONICAL_TEMPLATE_VERSION so topology/rest-pose
    changes cannot silently reuse an artifact generated by older code.

    Production never falls back to the procedural sphere/cylinder/box test
    template because that would silently degrade the avatar topology.
    """
    explicit = os.environ.get("VTUBER_TEMPLATE_PATH")
    if explicit:
        explicit_path = pathlib.Path(explicit).expanduser().resolve()
        if not explicit_path.is_file():
            raise FileNotFoundError(
                f"VTUBER_TEMPLATE_PATH does not exist: {explicit_path}"
            )
        return explicit_path

    cached_template = (
        _cache_root()
        / "canonical_vtuber"
        / CANONICAL_TEMPLATE_VERSION
        / "template.glb"
    )
    if _cached_template_valid(cached_template):
        return cached_template.resolve()

    base_obj = _find_local_makehuman_base()
    if base_obj is None:
        try:
            base_obj = _download_pinned_makehuman_base()
        except Exception as exc:
            raise RuntimeError(
                "Canonical VTuber template is missing and the pinned MakeHuman "
                "CC0 base.obj could not be fetched. Set MAKEHUMAN_BASE_OBJ or "
                "VTUBER_TEMPLATE_PATH explicitly."
            ) from exc

    cached_template.parent.mkdir(parents=True, exist_ok=True)
    result = create_canonical_template_from_makehuman(
        str(base_obj), str(cached_template)
    )
    if result.get("status") != "complete" or not cached_template.is_file():
        raise RuntimeError(
            "Failed to generate MakeHuman-CC0 canonical template: "
            f"{result.get('error', 'unknown error')}"
        )
    _write_template_metadata(cached_template)
    if not _cached_template_valid(cached_template):
        raise RuntimeError("Canonical template cache integrity check failed")
    return cached_template.resolve()


_template_path: Optional[pathlib.Path] = None


def get_template_path() -> pathlib.Path:
    """Get the single production canonical template path."""
    global _template_path
    if _template_path is None or not _template_path.is_file():
        _template_path = ensure_template_exists()
    return _template_path
