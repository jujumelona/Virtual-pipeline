"""Avatar reconstruction module for VTuber Pipeline."""

import functools
import hashlib
import subprocess
import pathlib
import logging
import os
import sys

logger = logging.getLogger(__name__)

TRIPOSR_PINNED_COMMIT = "107cefdc244c39106fa830359024f6a2f1c78871"
TRIPOSR_MODEL_ID = "stabilityai/TripoSR"
TRIPOSR_MODEL_REVISION = "c1cf7716aed5aa6c1c5e174657791ef0e1327bde"
TRIPOSR_MODEL_WEIGHT_SHA256 = "429e2c6b22a0923967459de24d67f05962b235f79cde6b032aa7ed2ffcd970ee"
TRIPOSR_DEFAULT_TIMEOUT_SECONDS = 1200


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
        result = subprocess.run(
            ["which", "triposr"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    
    # Not found - raise error with installation instructions
    raise RuntimeError(
        "TripoSR installation not found. Please install TripoSR:\n"
        "  git clone https://github.com/VAST-AI-Research/TripoSR.git\n"
        "  cd TripoSR && pip install -e .\n"
        "Or set TRIPOSR_DIR environment variable to the TripoSR directory."
    )


def verify_triposr_revision(run_script: str, profile: str) -> None:
    """Require the pinned TripoSR source revision for commercial/production use."""
    if profile not in {"commercial", "production"}:
        return
    repo_dir = pathlib.Path(run_script).resolve().parent
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_dir), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(
            "Commercial profile requires a git checkout of the pinned TripoSR source"
        ) from exc
    if proc.returncode != 0:
        raise RuntimeError(
            "Commercial profile could not verify TripoSR source revision: "
            + proc.stderr.strip()
        )
    actual = proc.stdout.strip()
    if actual != TRIPOSR_PINNED_COMMIT:
        raise RuntimeError(
            f"TripoSR revision mismatch: expected {TRIPOSR_PINNED_COMMIT}, got {actual}"
        )


def _sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@functools.lru_cache(maxsize=1)
def resolve_triposr_model() -> str:
    """Resolve the exact pinned TripoSR model snapshot and verify its weights."""
    explicit = os.environ.get("TRIPOSR_MODEL_DIR")
    if explicit:
        model_dir = pathlib.Path(explicit).expanduser().resolve()
        config_path = model_dir / "config.yaml"
        weight_path = model_dir / "model.ckpt"
    else:
        try:
            from huggingface_hub import hf_hub_download
        except ImportError as exc:
            raise RuntimeError(
                "huggingface-hub is required to resolve the pinned TripoSR model"
            ) from exc

        config_path = pathlib.Path(hf_hub_download(
            repo_id=TRIPOSR_MODEL_ID,
            filename="config.yaml",
            revision=TRIPOSR_MODEL_REVISION,
        )).resolve()
        weight_path = pathlib.Path(hf_hub_download(
            repo_id=TRIPOSR_MODEL_ID,
            filename="model.ckpt",
            revision=TRIPOSR_MODEL_REVISION,
        )).resolve()
        if config_path.parent != weight_path.parent:
            raise RuntimeError(
                "Pinned TripoSR config and weights resolved to different snapshots"
            )
        model_dir = config_path.parent

    if not config_path.is_file() or config_path.stat().st_size == 0:
        raise RuntimeError(f"Pinned TripoSR config is missing: {config_path}")
    if not weight_path.is_file() or weight_path.stat().st_size == 0:
        raise RuntimeError(f"Pinned TripoSR weights are missing: {weight_path}")

    actual_sha256 = _sha256(weight_path)
    if actual_sha256 != TRIPOSR_MODEL_WEIGHT_SHA256:
        raise RuntimeError(
            "TripoSR model weight SHA256 mismatch: "
            f"expected {TRIPOSR_MODEL_WEIGHT_SHA256}, got {actual_sha256}"
        )

    return str(model_dir)


def reconstruct_avatar(
    image_path: str,
    output_dir: str,
    profile: str = "commercial",
    *,
    model_save_format: str = "obj",
    remove_background: bool = True,
) -> str:
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
    
    input_path = pathlib.Path(image_path)
    if not input_path.is_file() or input_path.stat().st_size <= 0:
        raise FileNotFoundError(
            f"TripoSR input image is missing or empty: {image_path}"
        )
    if profile not in {"commercial", "production", "development"}:
        raise ValueError(f"Unsupported reconstruction profile: {profile!r}")
    if model_save_format not in {"obj", "glb"}:
        raise ValueError(
            f"Unsupported TripoSR model_save_format: {model_save_format}"
        )
    if not isinstance(remove_background, bool):
        raise ValueError("remove_background must be boolean")

    pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Resolve code/model only after cheap caller validation so malformed API
    # requests cannot trigger heavyweight downloads or GPU setup.
    run_script = find_triposr_installation()
    verify_triposr_revision(run_script, profile)
    logger.info(f"Using TripoSR at: {run_script}")
    model_dir = resolve_triposr_model()
    logger.info(
        "Using pinned TripoSR model %s@%s from %s",
        TRIPOSR_MODEL_ID,
        TRIPOSR_MODEL_REVISION,
        model_dir,
    )

    # User uploads are ordinary images, so use TripoSR's normal background
    # removal/foreground resize path by default. --no-remove-bg is only valid
    # for preprocessed gray-background images.
    cmd = [
        sys.executable,
        str(run_script),
        image_path,
        "--output-dir", output_dir,
        "--model-save-format", model_save_format,
        "--pretrained-model-name-or-path", model_dir,
    ]
    if not remove_background:
        # Upstream does not create output_dir/0 in this branch, so make it
        # explicitly before invoking run.py.
        pathlib.Path(output_dir, "0").mkdir(parents=True, exist_ok=True)
        cmd.append("--no-remove-bg")
    
    raw_timeout = os.environ.get(
        "TRIPOSR_TIMEOUT_SECONDS",
        str(TRIPOSR_DEFAULT_TIMEOUT_SECONDS),
    )
    try:
        timeout_seconds = int(raw_timeout)
    except ValueError as exc:
        raise ValueError(
            f"Invalid TRIPOSR_TIMEOUT_SECONDS: {raw_timeout!r}"
        ) from exc
    timeout_seconds = min(max(timeout_seconds, 60), 3600)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=str(pathlib.Path(run_script).resolve().parent),
        )
    except FileNotFoundError as e:
        raise RuntimeError(f"TripoSR CLI not found at {run_script}. Please clone TripoSR repository: git clone https://github.com/VAST-AI-Research/TripoSR.git") from e
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(
            f"TripoSR execution timed out after {timeout_seconds} seconds"
        ) from e
    
    if result.returncode != 0:
        stderr = result.stderr.lower()
        # Check for CUDA/GPU errors
        if 'cuda' in stderr or 'gpu' in stderr or 'out of memory' in stderr:
            raise RuntimeError(f"TripoSR failed due to GPU unavailability: {result.stderr}")
        raise RuntimeError(f"TripoSR failed:\n{result.stderr}")
    
    mesh_path = str(pathlib.Path(output_dir) / "0" / f"mesh.{model_save_format}")
    
    mesh_file = pathlib.Path(mesh_path)
    if not mesh_file.is_file() or mesh_file.stat().st_size == 0:
        raise RuntimeError(
            f"TripoSR output mesh not found or empty at expected path: {mesh_path}"
        )

    # Fail before fitting if TripoSR produced a structurally unreadable mesh.
    try:
        import trimesh

        loaded = trimesh.load(mesh_path, process=False)
        if isinstance(loaded, trimesh.Scene):
            geometries = list(loaded.geometry.values())
            if not geometries:
                raise ValueError("mesh scene contains no geometry")
            vertex_count = sum(len(g.vertices) for g in geometries)
            face_count = sum(len(g.faces) for g in geometries)
        else:
            vertex_count = len(loaded.vertices)
            face_count = len(loaded.faces)
        if vertex_count < 16 or face_count < 8:
            raise ValueError(
                f"mesh is too small: vertices={vertex_count}, faces={face_count}"
            )
    except Exception as exc:
        raise RuntimeError(
            f"TripoSR output mesh failed re-import validation: {exc}"
        ) from exc

    return str(mesh_file)
