"""Avatar reconstruction module for VTuber Pipeline."""

import subprocess
import pathlib


def reconstruct_avatar(image_path: str, output_dir: str, profile: str = 'commercial') -> str:
    """
    TripoSR로 이미지에서 3D 메시를 생성합니다.
    
    TripoSR은 MIT 라이선스로 상업적 사용이 가능합니다.
    nvdiffrast를 사용하지 않으므로 라이선스 제한이 없습니다.
    
    Args:
        image_path: 입력 이미지 경로
        output_dir: 출력 디렉터리
        profile: 라이선스 프로파일 (TripoSR은 모든 프로파일에서 사용 가능)
        
    Returns: 출력 메시 파일 경로
    """
    # TripoSR은 MIT 라이선스 - 모든 프로파일에서 안전하게 사용 가능
    # nvdiffrast 의존성 없음
    
    pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # TripoSR CLI 호출 (Colab에서 git clone으로 설치됨)
    cmd = [
        'python', 'TripoSR/run.py',
        image_path,
        '--output-dir', output_dir,
        '--no-remove-bg',
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"TripoSR 실패:\n{result.stderr}")
    # TripoSR은 output_dir/0/mesh.obj를 생성합니다
    mesh_path = str(pathlib.Path(output_dir) / '0' / 'mesh.obj')
    return mesh_path
