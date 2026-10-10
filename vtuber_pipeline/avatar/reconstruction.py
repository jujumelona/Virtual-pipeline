"""Avatar reconstruction module for VTuber Pipeline."""

import functools
import hashlib
import subprocess
import pathlib
import logging
import os
import sys
import threading

from vtuber_pipeline.core.stage_progress import current_reporter, report_stage

from vtuber_pipeline.avatar.triposr_runner import REMBG_U2NET_MD5

logger = logging.getLogger(__name__)

TRIPOSR_PINNED_COMMIT = "107cefdc244c39106fa830359024f6a2f1c78871"
TRIPOSR_MODEL_ID = "stabilityai/TripoSR"
TRIPOSR_MODEL_REVISION = "c1cf7716aed5aa6c1c5e174657791ef0e1327bde"
TRIPOSR_MODEL_WEIGHT_SHA256 = "429e2c6b22a0923967459de24d67f05962b235f79cde6b032aa7ed2ffcd970ee"
TRIPOSR_MODEL_CONFIG = {
    "cond_image_size": 512,
    "image_tokenizer_cls": "tsr.models.tokenizers.image.DINOSingleImageTokenizer",
    "image_tokenizer": {
        "pretrained_model_name_or_path": "facebook/dino-vitb16",
    },
    "tokenizer_cls": "tsr.models.tokenizers.triplane.Triplane1DTokenizer",
    "tokenizer": {
        "plane_size": 32,
        "num_channels": 1024,
    },
    "backbone_cls": "tsr.models.transformer.transformer_1d.Transformer1D",
    "backbone": {
        "in_channels": "${tokenizer.num_channels}",
        "num_attention_heads": 16,
        "attention_head_dim": 64,
        "num_layers": 16,
        "cross_attention_dim": 768,
    },
    "post_processor_cls": "tsr.models.network_utils.TriplaneUpsampleNetwork",
    "post_processor": {
        "in_channels": 1024,
        "out_channels": 40,
    },
    "decoder_cls": "tsr.models.network_utils.NeRFMLP",
    "decoder": {
        "in_channels": 120,
        "n_neurons": 64,
        "n_hidden_layers": 9,
        "activation": "silu",
    },
    "renderer_cls": "tsr.models.nerf_renderer.TriplaneNeRFRenderer",
    "renderer": {
        "radius": 0.87,
        "feature_reduction": "concat",
        "density_activation": "exp",
        "density_bias": -1.0,
        "num_samples_per_ray": 128,
    },
}
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

    try:
        status = subprocess.run(
            [
                "git",
                "-C",
                str(repo_dir),
                "status",
                "--porcelain",
                "--untracked-files=all",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(
            "Commercial profile could not verify TripoSR working tree"
        ) from exc
    if status.returncode != 0:
        raise RuntimeError(
            "Commercial profile could not inspect TripoSR working tree: "
            + status.stderr.strip()
        )
    dirty_lines = []
    for raw in status.stdout.splitlines():
        line = raw.strip()
        if not line:
            continue
        path_text = line[3:] if len(line) > 3 else line
        normalized = path_text.replace("\\", "/")
        if (
            "/__pycache__/" in f"/{normalized}"
            or normalized.endswith(".pyc")
        ):
            continue
        dirty_lines.append(line)
    if dirty_lines:
        raise RuntimeError(
            "Commercial profile requires an exact pinned TripoSR checkout; "
            "tracked or executable untracked changes detected: "
            + "; ".join(dirty_lines)
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

        # Keep the snapshot paths and their original filenames. Calling
        # .resolve() dereferences HF snapshot symlinks to /blobs/<sha>,
        # so returning their common /blobs directory breaks upstream
        # TSR.from_pretrained(), which opens model_dir/config.yaml and
        # model_dir/model.ckpt by name.
        config_path = pathlib.Path(hf_hub_download(
            repo_id=TRIPOSR_MODEL_ID,
            filename="config.yaml",
            revision=TRIPOSR_MODEL_REVISION,
        )).expanduser().absolute()
        weight_path = pathlib.Path(hf_hub_download(
            repo_id=TRIPOSR_MODEL_ID,
            filename="model.ckpt",
            revision=TRIPOSR_MODEL_REVISION,
        )).expanduser().absolute()
        if config_path.parent != weight_path.parent:
            raise RuntimeError(
                "Pinned TripoSR config and weights resolved to different snapshots"
            )
        model_dir = config_path.parent

    if not config_path.is_file() or config_path.stat().st_size == 0:
        raise RuntimeError(f"Pinned TripoSR config is missing: {config_path}")
    if not weight_path.is_file() or weight_path.stat().st_size == 0:
        raise RuntimeError(f"Pinned TripoSR weights are missing: {weight_path}")

    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError(
            "PyYAML is required to verify the pinned TripoSR config"
        ) from exc

    try:
        actual_config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(
            f"Pinned TripoSR config cannot be parsed: {config_path}"
        ) from exc
    if actual_config != TRIPOSR_MODEL_CONFIG:
        raise RuntimeError(
            "TripoSR model config mismatch: the resolved config.yaml "
            "does not match the pinned semantic contract"
        )

    actual_sha256 = _sha256(weight_path)
    if actual_sha256 != TRIPOSR_MODEL_WEIGHT_SHA256:
        raise RuntimeError(
            "TripoSR model weight SHA256 mismatch: "
            f"expected {TRIPOSR_MODEL_WEIGHT_SHA256}, got {actual_sha256}"
        )

    return str(model_dir)


def _run_triposr_with_diagnostics(
    cmd: list[str], *, timeout: int, cwd: str, env: dict,
) -> subprocess.CompletedProcess:
    """Stream actual model subprocess output when a live UI reporter exists.

    CLI/API calls without a reporter retain their normal subprocess.run path.
    Timeout and nonzero exit behavior remains fail-closed.
    """
    sink = current_reporter()
    if sink is None:
        return subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=timeout, cwd=cwd, env=env,
        )
    env = {**env, "PYTHONUNBUFFERED": "1", "VTUBER_REQUIRE_CUDA": "1"}
    report_stage("gpu_inference", "running", "TripoSR CUDA 프로세스 시작")
    sink("triposr_output", "log", "TripoSR 시작: CUDA 필수, CPU 폴백 금지")
    process = subprocess.Popen(
        cmd, cwd=cwd, env=env, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, bufsize=1,
    )
    output: list[str] = []

    def forward() -> None:
        assert process.stdout is not None
        pending: list[str] = []

        def emit() -> None:
            if pending:
                detail = "".join(pending).strip()
                pending.clear()
                if detail:
                    sink("triposr_output", "log", detail[-1200:])

        # Progress bars use carriage returns without newline. Iterating over
        # text lines would otherwise hide these messages until subprocess exit.
        while True:
            char = process.stdout.read(1)
            if not char:
                emit()
                break
            output.append(char)
            if char in "\r\n":
                emit()
            else:
                pending.append(char)
                if len(pending) >= 1000:
                    emit()

    reader = threading.Thread(target=forward, daemon=True)
    reader.start()
    try:
        code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)
        reader.join(timeout=10)
        raise subprocess.TimeoutExpired(cmd, timeout)
    reader.join(timeout=10)
    combined = "".join(output)
    report_stage("gpu_inference", "complete" if code == 0 else "error",
                 f"TripoSR 종료 코드 {code}")
    return subprocess.CompletedProcess(
        cmd, code, stdout=combined, stderr=combined,
    )


def _describe_triposr_process_failure(result: subprocess.CompletedProcess) -> str:
    """Classify the final exception, never informational [GPU] startup lines."""
    detail = result.stderr or result.stdout or "(no process output)"
    lines = [line.strip() for line in detail.splitlines() if line.strip()]
    exception_line = next(
        (line for line in reversed(lines) if line.startswith((
            "ModuleNotFoundError:", "ImportError:", "RuntimeError:",
            "OSError:", "ValueError:", "torch.OutOfMemoryError:",
            "torch.cuda.OutOfMemoryError:",
        ))),
        lines[-1] if lines else "(unknown failure)",
    )
    lowered = exception_line.lower()
    if exception_line.startswith(("ModuleNotFoundError:", "ImportError:")):
        category = "Python dependency/import error"
    elif ("out of memory" in lowered or "cuda error" in lowered
          or "cuda driver" in lowered or "cuda unavailable" in lowered
          or "no cuda" in lowered or "cuda gpu 없음" in lowered):
        category = "CUDA inference error"
    else:
        category = "model execution error"
    return (
        f"TripoSR {category} (exit={result.returncode}): "
        f"{exception_line}\\n{detail}"
    )


def canonicalize_triposr_mesh(source_path, output_path):
    """Rotate native TripoSR geometry into the pipeline's Y-up/+Z-front frame.

    Pinned 107cefd tsr/utils.py defines X-back, Y-right, Z-up. The avatar
    frame is X-left, Y-up, Z-forward, hence (X,Y,Z) = (-y,z,-x).
    This proper rotation preserves scale, winding and vertex appearance;
    inferred TripoSR coordinates do not become calibrated metres.
    """
    import numpy as np
    import trimesh

    source_path, output_path = pathlib.Path(source_path), pathlib.Path(output_path)
    if source_path.resolve() == output_path.resolve():
        raise ValueError("Keep the original native TripoSR mesh separate")
    mesh = trimesh.load(source_path, process=False)
    rotation = np.array([
        [0., -1., 0., 0.], [0., 0., 1., 0.],
        [-1., 0., 0., 0.], [0., 0., 0., 1.],
    ])
    mesh.apply_transform(rotation)
    mesh.export(output_path)
    return str(output_path)


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
    
    # TripoSR runs with cwd set to its own checkout. Normalize caller paths
    # before crossing that subprocess boundary (CLI accepts relative paths).
    input_path = pathlib.Path(image_path).expanduser().resolve()
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

    output_path = pathlib.Path(output_dir).expanduser().resolve()
    output_path.mkdir(parents=True, exist_ok=True)

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
    runner_script = pathlib.Path(__file__).with_name(
        "triposr_runner.py"
    ).resolve()
    if not runner_script.is_file():
        raise RuntimeError(
            f"Pinned TripoSR runner is missing: {runner_script}"
        )

    cmd = [
        sys.executable,
        str(runner_script),
        str(run_script),
        str(input_path),
        "--output-dir", str(output_path),
        "--model-save-format", model_save_format,
        "--pretrained-model-name-or-path", model_dir,
    ]
    if not remove_background:
        # Upstream does not create output_dir/0 in this branch, so make it
        # explicitly before invoking run.py.
        (output_path / "0").mkdir(parents=True, exist_ok=True)
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
        child_env = os.environ.copy()
        # rembg 2.0.85 normally verifies its pinned u2net model with MD5.
        # Never allow a parent environment to silently disable that check.
        child_env.pop("MODEL_CHECKSUM_DISABLED", None)

        result = _run_triposr_with_diagnostics(
            cmd, timeout=timeout_seconds,
            cwd=str(pathlib.Path(run_script).resolve().parent),
            env=child_env,
        )
    except FileNotFoundError as e:
        raise RuntimeError(f"TripoSR CLI not found at {run_script}. Please clone TripoSR repository: git clone https://github.com/VAST-AI-Research/TripoSR.git") from e
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(
            f"TripoSR execution timed out after {timeout_seconds} seconds"
        ) from e
    
    if result.returncode != 0:
        raise RuntimeError(_describe_triposr_process_failure(result))
    
    mesh_path = str(output_path / "0" / f"mesh.{model_save_format}")
    
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

    canonical_path = mesh_file.with_name(f"mesh_canonical.{model_save_format}")
    return canonicalize_triposr_mesh(mesh_file, canonical_path)
