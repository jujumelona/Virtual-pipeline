"""Procedural canonical VTuber template mesh generation.

This module creates a canonical VTuber template mesh with:
- Head: UV sphere
- Neck: Cylinder
- Upper body: Box
- Humanoid bone hierarchy with distance-based vertex groups
"""

from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Tuple
import pathlib
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
    """Canonical VTuber 템플릿 메시를 생성합니다.
    
    절차적 메시 생성:
    - Head: UV sphere (r=0.08)
    - Neck: Cylinder (r=0.02, h=0.05)
    - Body: Box (0.15 x 0.12 x 0.08)
    
    뼈 계층 구조:
    - hips -> spine -> chest -> neck -> head
    - leftEye, rightEye (head의 자식)
    
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
        
        # 6. 결과 저장
        result["vertex_count"] = len(merged_mesh.vertices)
        result["face_count"] = len(merged_mesh.faces)
        result["bones"] = list(adjusted_bones.keys())
        result["vertex_groups"] = {k: v.tolist() for k, v in vertex_groups.items()}
        
        # 7. GLB로 내보내기
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


def create_canonical_template_from_makehuman(base_obj_path: str, output_path: str) -> Dict[str, Any]:
    """
    MakeHuman CC0 base mesh에서 VTuber canonical template을 생성합니다.
    
    Steps:
    1. trimesh으로 base.obj 로드
    2. 애니메이션 비율 스케일링 (머리 1.2x 확대)
    3. template.glb로 저장
    
    Args:
        base_obj_path: MakeHuman base.obj 파일 경로
        output_path: 출력 GLB 파일 경로
        
    Returns:
        생성 결과 딕셔너리
    """
    if not TRIMESH_AVAILABLE:
        return {"status": "error", "error": "trimesh not available"}
    
    try:
        mesh = trimesh.load(base_obj_path)
        if isinstance(mesh, trimesh.Scene):
            mesh = trimesh.util.concatenate(list(mesh.geometry.values()))
        
        # 애니메 비율: 머리 부분 1.2배 확대
        vertices = np.array(mesh.vertices)
        bounds_min = vertices.min(axis=0)
        bounds_max = vertices.max(axis=0)
        height = bounds_max[1] - bounds_min[1]
        
        # 머리는 상위 25% 영역으로 정의
        head_y_threshold = bounds_max[1] - 0.25 * height
        head_mask = vertices[:, 1] > head_y_threshold
        head_center = np.array([0.0, bounds_max[1], 0.0])
        
        # 머리 버텍스를 머리 중심 기준으로 1.2배 스케일
        for i in range(len(vertices)):
            if head_mask[i]:
                offset = vertices[i] - head_center
                vertices[i] = head_center + offset * 1.2
        
        mesh.vertices = vertices
        
        output_path_obj = pathlib.Path(output_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)
        mesh.export(str(output_path_obj))
        
        return {
            "status": "complete",
            "output_path": str(output_path_obj),
            "source": "makehuman_cc0",
            "vertex_count": len(mesh.vertices),
            "face_count": len(mesh.faces)
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


if __name__ == "__main__":
    # 테스트 실행
    result = create_canonical_template("assets/canonical_vtuber/template.glb")
    print(f"Status: {result['status']}")
    if result['status'] == 'complete':
        print(f"Vertices: {result['vertex_count']}")
        print(f"Faces: {result['face_count']}")
        print(f"Bones: {result['bones']}")
