"""Avatar reconstruction module for VTuber Pipeline."""

import subprocess
import pathlib
from vtuber_pipeline.core.config import check_commercial_profile


def reconstruct_avatar(image_path: str, output_dir: str, profile: str = 'commercial') -> str:
    """
    TripoSR로 이미지에서 3D 메시를 생성합니다.
    commercial 프로파일: --no-remove-bg 사용 (rembg 의존 없음).
    Returns: 출력 메시 파일 경로
    """
    if profile == 'commercial':
        check_commercial_profile('nvdiffrast')  # 차단된 패키지 확인 예시
        # TripoSR은 상업용 프로파일에서 안전합니다
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
