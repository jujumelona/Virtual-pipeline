"""Avatar reconstruction module for VTuber Pipeline."""

import subprocess
import pathlib
import logging
import os
import sys

logger = logging.getLogger(__name__)


def find_triposr_installation() -> str:
    """Find TripoSR installation directory.
    
    Searches in the following order:
    1. TRIPOSR_DIR environment variable
    2. /content/third_party/TripoSR (Colab default)
    3. /content/TripoSR (Colab alternative)
    4. ~/TripoSR (home directory)
    5. ./TripoSR (current directory)
    6. Site-packages (pip install)
    7. PATH
    
    Returns:
        Absolute path to TripoSR run.py
        
    Raises:
        RuntimeError: If TripoSR installation not found
    """
    search_paths = []
    
    # 1. TRIPOSR_DIR environment variable
    triposr_dir = os.environ.get('TRIPOSR_DIR')
    if triposr_dir:
        search_paths.append(pathlib.Path(triposr_dir))
    
    # 2. /content/third_party/TripoSR (Colab default)
    search_paths.append(pathlib.Path('/content/third_party/TripoSR'))
    
    # 3. /content/TripoSR (Colab alternative)
    search_paths.append(pathlib.Path('/content/TripoSR'))
    
    # 4. ~/TripoSR (home directory)
    search_paths.append(pathlib.Path.home() / 'TripoSR')
    
    # 5. ./TripoSR (current directory)
    search_paths.append(pathlib.Path.cwd() / 'TripoSR')
    
    # 6. Check relative to this module (for pip install)
    module_dir = pathlib.Path(__file__).parent
    search_paths.append(module_dir.parent.parent / 'TripoSR')
    
    # Check each path for run.py
    for path in search_paths:
        run_py = path / 'run.py'
        if run_py.exists():
            return str(run_py.resolve())
    
    # 7. Check if triposr is in PATH
    try:
        result = subprocess.run(['which', 'triposr'], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    
    # Not found - raise error with installation instructions
    raise RuntimeError(
        "TripoSR installation not found. Please install TripoSR:\n"
        "  git clone https://github.com/VAST-AI-Research/TripoSR.git\n"
        "  cd TripoSR && pip install -e .\n"
        "Or set TRIPOSR_DIR environment variable to the TripoSR directory."
    )


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
    
    # Find TripoSR installation
    run_script = find_triposr_installation()
    logger.info(f"Using TripoSR at: {run_script}")
    
    # TripoSR CLI 호출 with absolute path
    cmd = [
        sys.executable,  # Use current Python interpreter
        str(run_script),  # Absolute path to run.py
        image_path,
        '--output-dir', output_dir,
        '--no-remove-bg',
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except FileNotFoundError as e:
        raise RuntimeError(f"TripoSR CLI not found at {run_script}. Please clone TripoSR repository: git clone https://github.com/VAST-AI-Research/TripoSR.git") from e
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
