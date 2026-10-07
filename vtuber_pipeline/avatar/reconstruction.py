"""Avatar reconstruction module for VTuber Pipeline."""

import subprocess
import pathlib
import logging

logger = logging.getLogger(__name__)


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
        
    Raises:
        RuntimeError: TripoSR 실행 실패 (GPU 없음, 설치되지 않음 등)
        FileNotFoundError: TripoSR CLI를 찾을 수 없음
        subprocess.CalledProcessError: TripoSR subprocess 오류
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
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except FileNotFoundError as e:
        raise RuntimeError(f"TripoSR CLI not found. Please clone TripoSR repository: git clone https://github.com/VAST-AI-Research/TripoSR.git") from e
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"TripoSR execution timed out after 300 seconds") from e
    
    if result.returncode != 0:
        stderr = result.stderr.lower()
        # Check for CUDA/GPU errors
        if 'cuda' in stderr or 'gpu' in stderr or 'out of memory' in stderr:
            raise RuntimeError(f"TripoSR failed due to GPU unavailability: {result.stderr}")
        raise RuntimeError(f"TripoSR failed:\n{result.stderr}")
    
    # TripoSR은 output_dir/0/mesh.obj를 생성합니다
    mesh_path = str(pathlib.Path(output_dir) / '0' / 'mesh.obj')
    
    if not pathlib.Path(mesh_path).exists():
        raise RuntimeError(f"TripoSR output mesh not found at expected path: {mesh_path}")
    
    return mesh_path
