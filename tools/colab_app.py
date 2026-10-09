"""Colab Gradio UI for the VTuber pipeline.

This file is intentionally loaded from the freshly synchronized main branch by
the notebook bootstrap. The notebook itself stays tiny so stale Colab copies
still execute the current UI and pipeline code.
"""

from __future__ import annotations

import hashlib
import logging
import time
import queue
import shlex
import threading
from datetime import datetime, timezone
import inspect
import os
import pathlib
import shutil
import subprocess
import sys
import traceback
import uuid
from typing import Any, Dict, List, Optional, Tuple

# runpy.run_path() does not add the script directory to sys.path. Colab
# installs in a separate Python process, so an editable .pth may not be loaded
# in the already-running notebook kernel. Import from this checkout explicitly.
_SOURCE_REPO_DIR = pathlib.Path(__file__).resolve().parent.parent
if str(_SOURCE_REPO_DIR) not in sys.path:
    sys.path.insert(0, str(_SOURCE_REPO_DIR))

# The package installer runs before the final Gradio dependency graph is
# resolved. It must not import Gradio merely to reach ensure_runtime().
# Normal UI execution still imports the real Gradio package.
# Legacy Colab tabs call runpy.run_path(..., run_name='vtuber_prepare')
# without setting VTUBER_SETUP_ONLY. Honor both forms so old tabs can still
# prepare the freshly cloned main without importing an unstable Gradio install.
_PREPARATION_MODE = (
    os.environ.get("VTUBER_SETUP_ONLY") == "1"
    or __name__ in {"vtuber_prepare", "prepare"}
)
if _PREPARATION_MODE:
    from types import SimpleNamespace
    gr = SimpleNamespace(Progress=lambda: None)
    print("[setup] Python preparation entrypoint loaded", flush=True)
else:
    import gradio as gr


REPO_URL = "https://github.com/jujumelona/Virtual-pipeline.git"
REPO_DIR = pathlib.Path("/content/Virtual-pipeline")
TRIPOSR_DIR = pathlib.Path("/content/third_party/TripoSR")
TRIPOSR_COMMIT = "107cefdc244c39106fa830359024f6a2f1c78871"
TRIPOSR_MODEL_REVISION = "c1cf7716aed5aa6c1c5e174657791ef0e1327bde"
TRIPOSR_MODEL_WEIGHT_SHA256 = "429e2c6b22a0923967459de24d67f05962b235f79cde6b032aa7ed2ffcd970ee"
GRADIO_VERSION = "6.3.0"
RUNTIME_CONTRACT = "colab-runtime-v10"
WORK_ROOT = pathlib.Path("/content/vtuber_builder")
OUTPUT_ROOT = WORK_ROOT / "output"

ANCHORS = [
    "HEAD_TOP",
    "FACE",
    "LEFT_EAR",
    "RIGHT_EAR",
    "NECK",
    "CHEST",
    "BACK",
    "LEFT_SHOULDER",
    "RIGHT_SHOULDER",
    "LEFT_HAND",
    "RIGHT_HAND",
    "LEFT_FOOT",
    "RIGHT_FOOT",
    "HIPS",
    "CUSTOM",
]

_RUNTIME_READY_HEAD: Optional[str] = None


def _run(
    cmd: List[str],
    *,
    timeout: int,
    cwd: Optional[pathlib.Path] = None,
) -> subprocess.CompletedProcess:
    # Stream stdout/stderr as they arrive: Colab users must see pip downloads,
    # model verification and failures, not a silent 20-minute capture_output.
    log_path = WORK_ROOT / "logs" / "runtime_setup.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    command = shlex.join(cmd)
    print(f"[setup] $ {command}", flush=True)
    output: List[str] = []
    process = subprocess.Popen(
        cmd,
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    def forward() -> None:
        assert process.stdout is not None
        with log_path.open("a", encoding="utf-8") as log:
            log.write(f"\n[setup] $ {command}\n")
            for line in process.stdout:
                output.append(line)
                log.write(line)
                log.flush()
                print(line, end="", flush=True)

    reader = threading.Thread(target=forward, daemon=True)
    reader.start()
    try:
        code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        process.kill()
        process.wait(timeout=10)
        reader.join(timeout=10)
        raise RuntimeError(
            f"Command timeout ({timeout}s): {command}\n"
            f"Full log: {log_path}"
        ) from exc
    reader.join(timeout=10)
    combined = "".join(output)
    if code:
        raise RuntimeError(
            f"Command failed ({code}): {command}\n"
            f"{combined[-6000:]}\nFull log: {log_path}"
        )
    return subprocess.CompletedProcess(cmd, code, stdout=combined, stderr="")


def _sync_repo() -> str:
    if (REPO_DIR / ".git").is_dir():
        _run(
            ["git", "-C", str(REPO_DIR), "remote", "set-url", "origin", REPO_URL],
            timeout=60,
        )
        _run(
            ["git", "-C", str(REPO_DIR), "fetch", "--prune", "origin", "main"],
            timeout=180,
        )
    else:
        if REPO_DIR.exists():
            shutil.rmtree(REPO_DIR)
        _run(
            [
                "git",
                "clone",
                "--branch",
                "main",
                "--single-branch",
                REPO_URL,
                str(REPO_DIR),
            ],
            timeout=300,
        )

    _run(
        ["git", "-C", str(REPO_DIR), "checkout", "-B", "main", "origin/main"],
        timeout=60,
    )
    _run(
        ["git", "-C", str(REPO_DIR), "reset", "--hard", "origin/main"],
        timeout=60,
    )

    head = _run(
        ["git", "-C", str(REPO_DIR), "rev-parse", "HEAD"],
        timeout=30,
    ).stdout.strip()
    origin_head = _run(
        ["git", "-C", str(REPO_DIR), "rev-parse", "origin/main"],
        timeout=30,
    ).stdout.strip()
    if head != origin_head:
        raise RuntimeError(
            f"Latest-main synchronization failed: local={head}, origin/main={origin_head}"
        )
    return head


def _sync_triposr() -> None:
    TRIPOSR_DIR.parent.mkdir(parents=True, exist_ok=True)
    if (TRIPOSR_DIR / ".git").is_dir():
        _run(
            ["git", "-C", str(TRIPOSR_DIR), "fetch", "--prune", "origin"],
            timeout=180,
        )
    else:
        if TRIPOSR_DIR.exists():
            shutil.rmtree(TRIPOSR_DIR)
        _run(
            [
                "git",
                "clone",
                "https://github.com/VAST-AI-Research/TripoSR.git",
                str(TRIPOSR_DIR),
            ],
            timeout=300,
        )

    _run(
        ["git", "-C", str(TRIPOSR_DIR), "checkout", "--detach", TRIPOSR_COMMIT],
        timeout=60,
    )
    # A checkout can preserve tracked local edits when they do not conflict.
    # Production must execute the exact pinned source bytes.
    _run(
        ["git", "-C", str(TRIPOSR_DIR), "reset", "--hard", TRIPOSR_COMMIT],
        timeout=60,
    )
    _run(
        ["git", "-C", str(TRIPOSR_DIR), "clean", "-ffd"],
        timeout=60,
    )
    actual = _run(
        ["git", "-C", str(TRIPOSR_DIR), "rev-parse", "HEAD"],
        timeout=30,
    ).stdout.strip()
    if actual != TRIPOSR_COMMIT:
        raise RuntimeError(
            f"TripoSR pin mismatch: expected={TRIPOSR_COMMIT}, actual={actual}"
        )


def _runtime_contract_fingerprint() -> str:
    """Hash every input that can change the installed Colab runtime."""
    digest = hashlib.sha256()
    for value in (
        RUNTIME_CONTRACT,
        TRIPOSR_COMMIT,
        TRIPOSR_MODEL_REVISION,
        TRIPOSR_MODEL_WEIGHT_SHA256,
        GRADIO_VERSION,
        f"python-{sys.version_info.major}.{sys.version_info.minor}",
    ):
        digest.update(str(value).encode("utf-8"))
        digest.update(b"\0")

    for path in (
        REPO_DIR / "pyproject.toml",
        REPO_DIR / "requirements.txt",
        REPO_DIR / "third_party.lock.json",
    ):
        if not path.is_file():
            raise RuntimeError(
                f"Runtime contract input is missing: {path}"
            )
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")

    # Package installation commands live in this function. Hashing its source
    # means changing a pin/flag here invalidates the marker even when a human
    # forgets to bump RUNTIME_CONTRACT.
    digest.update(inspect.getsource(_install_runtime).encode("utf-8"))
    return digest.hexdigest()


def _install_runtime(head: str) -> None:
    python_tag = f"py{sys.version_info.major}{sys.version_info.minor}"
    runtime_fingerprint = _runtime_contract_fingerprint()
    marker = WORK_ROOT / (
        f".environment-{RUNTIME_CONTRACT}-{python_tag}-"
        f"{runtime_fingerprint[:16]}.ready"
    )
    if marker.is_file():
        print(f"[setup] 설치된 환경 사용: {marker.name}", flush=True)
        # The dependency fingerprint is identical, but Python/UI source may
        # have changed. Record the synchronized head without reinstalling.
        lines = marker.read_text(encoding="utf-8").splitlines()
        lines = [line for line in lines if not line.startswith("installed_from_main=")]
        lines.append(f"installed_from_main={head}")
        marker.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.environ["TRIPOSR_DIR"] = str(TRIPOSR_DIR)
        if str(REPO_DIR) not in sys.path:
            sys.path.insert(0, str(REPO_DIR))
        # Editable installation points at the stable /content/Virtual-pipeline
        # path, so a git reset to a newer main immediately exposes new source.
        return

    if not ((3, 12) <= sys.version_info[:2] <= (3, 13)):
        raise RuntimeError(
            "Supported Colab Python versions are 3.12 and 3.13; "
            f"current={sys.version.split()[0]}"
        )

    WORK_ROOT.mkdir(parents=True, exist_ok=True)

    print("[환경 1/7] pip/setuptools/wheel 준비 (GPU 사용 전)", flush=True)
    _run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "-U",
            "pip",
            "setuptools",
            "wheel",
        ],
        timeout=600,
    )

    print("[환경 2/7] PyTorch/CUDA 환경 점검 (GPU 추론 아님)", flush=True)
    # Colab already provides CUDA-enabled torch/torchvision. Never let the
    # resolver replace them with a different build.
    _run(
        [
            sys.executable,
            "-c",
            (
                "import torch, torchvision; "
                "print('python', __import__('sys').version); "
                "print('torch', torch.__version__); "
                "print('torchvision', torchvision.__version__); "
                "print('cuda', torch.version.cuda, torch.cuda.is_available()); "
                "assert torch.cuda.is_available(), "
                "'GPU 연결 안 됨: Colab 런타임 > 런타임 유형 변경 > T4 GPU 선택'"
            ),
        ],
        timeout=60,
    )

    print("[환경 3/7] 사전 빌드된 이미지/메시 라이브러리 설치", flush=True)
    # Native packages: wheel-only. This deliberately prevents silent source
    # builds such as Pillow==10.1.0 on newer Colab Python runtimes.
    _run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--only-binary=:all:",
            "Pillow==12.3.0",
            "xatlas==0.0.11",
            "scikit-image==0.26.0",
            "moderngl==5.12.0",
            "onnxruntime==1.30.0",
            "opencv-python-headless>=4.10.0.84",
            "safetensors>=0.5.3",
        ],
        timeout=1200,
    )

    # TripoSR + local pipeline runtime. These versions retain TripoSR's used
    # APIs while supporting the current 3.12/3.13 Colab runtime.
    print("[환경 4/7] TripoSR 의존성 설치 (GPU 추론 아님)", flush=True)
    runtime_packages = [
        "omegaconf==2.3.0",
        "einops==0.7.0",
        "transformers==4.57.6",
        "trimesh==4.12.2",
        "rembg==2.0.85",
        "huggingface-hub>=0.34.0,<1.0",
        "imageio[ffmpeg]>=2.34.0",
        "PyYAML>=6.0",
        "scipy>=1.13",
        "click>=8.0",
        "pygltflib==1.16.5",
        "psd-tools==1.11.0",
        "packaging>=24.0",
    ]
    _run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--prefer-binary",
            *runtime_packages,
        ],
        timeout=1800,
    )

    print("[환경 5/7] 얼굴 검출 라이브러리 설치", flush=True)
    # anime-face-detector depends on the existing torch/torchvision pair.
    # Install its package without dependency resolution so pip cannot replace
    # Colab's CUDA-enabled PyTorch.
    _run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-deps",
            "anime-face-detector==0.1.0",
        ],
        timeout=600,
    )

    # Pinned TripoSR only needs marching_cubes, supplied by our scikit-image
    # bridge in the isolated TripoSR subprocess. No native CUDA extension
    # is built at Colab startup.
    print("[환경 6/7] VTuber Pipeline 설치", flush=True)
    # Install the freshly synchronized repository without re-running the
    # dependency resolver and undoing the compatibility set above.
    _run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-deps",
            "-e",
            str(REPO_DIR),
        ],
        timeout=600,
    )

    print("[환경 7/7] 메시 추출 테스트 · 의존성 라이선스 감사", flush=True)
    # End-to-end import smoke test for every external runtime edge used before
    # the first model inference.
    _run(
        [
            sys.executable,
            "-c",
            (
                "import PIL, xatlas, moderngl, onnxruntime, cv2, safetensors; "
                "import omegaconf, einops, trimesh, rembg, imageio, scipy; "
                "import huggingface_hub, pygltflib, torch, torchvision, gradio; "
                "from transformers.models.vit.modeling_vit import ViTModel; "
                "from anime_face_detector import create_detector; from skimage import measure; "
                "from vtuber_pipeline.avatar.marching_cubes_backend import install_triposr_marching_cubes; "
                "install_triposr_marching_cubes(); "
                "from torchmcubes import marching_cubes; "
                "grid = torch.linspace(-1, 1, 12); "
                "z, y, x = torch.meshgrid(grid, grid, grid, indexing='ij'); "
                "vertices, faces = marching_cubes(x*x + y*y + z*z, 0.5); "
                "assert vertices.shape[1] == 3 and faces.shape[1] == 3; "
                "assert vertices.numel() > 0 and faces.numel() > 0; "
                "print('runtime-smoke-ok'); "
                "print('Pillow', PIL.__version__); "
                "print('trimesh', trimesh.__version__); "
                "print('onnxruntime', onnxruntime.__version__); "
                "print('gradio', gradio.__version__)"
            ),
        ],
        timeout=120,
    )

    # Audit the actually resolved dependency graph before caching this runtime.
    _run(
        [
            sys.executable,
            str(REPO_DIR / "tools" / "audit_runtime_environment.py"),
        ],
        timeout=180,
    )

    os.environ["TRIPOSR_DIR"] = str(TRIPOSR_DIR)
    if str(REPO_DIR) not in sys.path:
        sys.path.insert(0, str(REPO_DIR))

    marker.write_text(
        "\n".join(
            [
                f"runtime_contract={RUNTIME_CONTRACT}",
                f"runtime_fingerprint={runtime_fingerprint}",
                f"installed_from_main={head}",
                f"python={sys.version.split()[0]}",
                f"triposr={TRIPOSR_COMMIT}",
                f"triposr_model_revision={TRIPOSR_MODEL_REVISION}",
                f"triposr_model_sha256={TRIPOSR_MODEL_WEIGHT_SHA256}",
                "marching_cubes=scikit-image-0.26.0",
                f"gradio={GRADIO_VERSION}",
                "pillow=12.3.0",
                "xatlas=0.0.11",
                "scikit-image=0.26.0",
                "moderngl=5.12.0",
                "onnxruntime=1.30.0",
                "transformers=4.57.6",
                "trimesh=4.12.2",
                "rembg=2.0.85",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _model_fingerprint() -> str:
    """Model cache stamp changes with dependency contract and model code."""
    digest = hashlib.sha256(_runtime_contract_fingerprint().encode("utf-8"))
    for relative in (
        "tools/prefetch_model_assets.py",
        "vtuber_pipeline/avatar/reconstruction.py",
        "vtuber_pipeline/avatar/face_detector.py",
        "vtuber_pipeline/avatar/triposr_runner.py",
        "vtuber_pipeline/avatar/template_mesh.py",
    ):
        path = REPO_DIR / relative
        if not path.is_file():
            raise RuntimeError(f"Model contract file missing: {relative}")
        digest.update(relative.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _model_scope(mode: str) -> str:
    if mode in ("inochi2d", "live2d", "common_2d"):
        return "common_2d"
    if mode == "3d":
        return "3d"
    raise ValueError(f"unsupported model prefetch mode: {mode!r}")


def _model_marker(mode: str = "3d") -> pathlib.Path:
    scope = _model_scope(mode)
    tag = f"py{sys.version_info.major}{sys.version_info.minor}"
    return WORK_ROOT / (
        f".models-{scope}-{RUNTIME_CONTRACT}-{tag}-{_model_fingerprint()[:16]}.ready"
    )


def _prepare_models_checked(mode: str = "3d") -> None:
    """Prepare only selected-model checkpoints; record a per-mode ready marker."""
    scope = _model_scope(mode)
    revision = subprocess.run(
        ["git", "-C", str(REPO_DIR), "rev-parse", "HEAD"],
        text=True, capture_output=True, timeout=15,
    )
    if revision.returncode:
        raise RuntimeError("① 환경 설치를 먼저 실행하세요.")
    head = revision.stdout.strip()
    fingerprint = _runtime_contract_fingerprint()
    tag = f"py{sys.version_info.major}{sys.version_info.minor}"
    environment = WORK_ROOT / (
        f".environment-{RUNTIME_CONTRACT}-{tag}-{fingerprint[:16]}.ready"
    )
    if not environment.is_file() or (
        f"installed_from_main={head}" not in environment.read_text(encoding="utf-8").splitlines()
    ):
        raise RuntimeError("① 환경 설치를 먼저 완료하세요.")
    marker = _model_marker(scope)
    if marker.is_file():
        lines = marker.read_text(encoding="utf-8").splitlines()
        if (f"model_fingerprint={_model_fingerprint()}" in lines
                and f"model_scope={scope}" in lines
                and "face_detector_initialized=true" in lines):
            if f"installed_from_main={head}" not in lines:
                lines = [line for line in lines if not line.startswith("installed_from_main=")]
                lines.append(f"installed_from_main={head}")
                marker.write_text("\n".join(lines) + "\n", encoding="utf-8")
            print("[models] 검증된 모델 캐시 사용", flush=True)
            return
    print(f"[models] 선택 모드만 준비: {scope}", flush=True)
    _run(
        [sys.executable, "-u", str(REPO_DIR / "tools" / "prefetch_model_assets.py"),
         "--mode", scope],
        timeout=3000,
    )
    # Downloaded weights do not prove that the detector can be instantiated.
    # Validate actual YOLOv3 + HRNetV2 initialization on Colab CUDA before
    # writing the ready marker, not during the user's first generation.
    print("[models] 얼굴 검출기 YOLOv3/HRNetV2 CUDA 초기화 검증", flush=True)
    _run(
        [
            sys.executable, "-u", "-c",
            "from vtuber_pipeline.avatar.face_detector import AnimeFaceDetector; "
            "detector = AnimeFaceDetector(); "
            "assert detector._detector is not None; "
            "print('[models] face-detector-init-ok', flush=True)",
        ],
        timeout=600,
    )
    # A success marker must only exist after all parallel workers finish.
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(
        f"model_fingerprint={_model_fingerprint()}\n"
        f"installed_from_main={head}\n"
        f"model_scope={scope}\n"
        "face_detector_initialized=true\n",
        encoding="utf-8",
    )


def prepare_models(mode: str = "3d") -> None:
    """Explicitly prepare only the models for the selected workflow."""
    scope = _model_scope(mode)
    log_file = WORK_ROOT / "logs" / "model_setup.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    print(f"[models] 모델 준비 시작 · 전체 오류 로그: {log_file}", flush=True)
    try:
        _prepare_models_checked(scope)
    except Exception:
        detail = "[models] 준비 실패\n" + traceback.format_exc()
        with log_file.open("a", encoding="utf-8") as output:
            output.write(detail + "\n")
        print(detail, flush=True)
        raise
    print("[models] 준비·초기화 검증 완료", flush=True)


def prepare_skintokens_ui():
    """Explicit opt-in installer; never invoked by avatar inference itself."""
    try:
        require_runtime_ready("3d")
        from vtuber_pipeline.avatar.skintokens_bridge import (
            runtime_identity, check_gpu_compatibility,
        )
        directory = pathlib.Path("/content/third_party/SkinTokens")
        _run(
            [sys.executable, "-u", str(REPO_DIR / "tools" / "setup_skintokens_runtime.py"),
             "--directory", str(directory)],
            timeout=10800,
        )
        # A child process cannot export into the already-running Gradio server.
        # Bind the isolated interpreter only after native setup has succeeded.
        os.environ["VTUBER_SKINTOKENS_DIR"] = str(directory)
        os.environ["VTUBER_SKINTOKENS_PYTHON"] = str(directory / ".venv/bin/python")
        identity = runtime_identity()
        check_gpu_compatibility(identity)
        return ("SkinTokens 설치/검증 완료 · 이제 3D 자동 스키닝 엔진에서 "
                "SkinTokens를 선택해 생성할 수 있습니다.")
    except Exception as exc:
        return "SkinTokens 준비 실패: " + str(exc) + " · 기본 리깅을 선택하세요."


def _reload_pipeline_modules() -> None:
    for name in list(sys.modules):
        if name == "vtuber_pipeline" or name.startswith("vtuber_pipeline."):
            del sys.modules[name]


def _setup_stage(label: str, callback):
    """Expose failures even to legacy notebook wrappers with bare check=True."""
    print(f"[setup] {label}: start", flush=True)
    try:
        outcome = callback()
    except Exception:
        detail = f"[setup] {label}: FAILED\n{traceback.format_exc()}"
        log_path = WORK_ROOT / "logs" / "runtime_setup.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as log:
            log.write(detail + "\n")
        print(detail, flush=True)
        raise
    print(f"[setup] {label}: complete", flush=True)
    return outcome


def ensure_runtime(
    progress: Optional[gr.Progress] = None,
) -> Tuple[str, List[str]]:
    global _RUNTIME_READY_HEAD

    logs: List[str] = []

    if progress:
        progress(0.04, desc="최신 main 확인")
    head = _setup_stage("main 동기화", _sync_repo)
    logs.append(f"최신 main: {head[:12]}")

    if _RUNTIME_READY_HEAD == head:
        os.environ["TRIPOSR_DIR"] = str(TRIPOSR_DIR)
        return head, logs

    # The user has not selected a mode yet. Avoid cloning TripoSR on
    # Inochi2D / Live2D-only sessions; checkout belongs in 3D setup.
    if progress:
        progress(0.20, desc="공통 패키지 준비")
    _setup_stage("Python dependency installation", lambda: _install_runtime(head))
    logs.append("Python 환경 준비 완료")

    _reload_pipeline_modules()
    _RUNTIME_READY_HEAD = head
    return head, logs



def require_runtime_ready(mode: str = "3d") -> Tuple[str, List[str]]:
    """Generation must not install packages or download checkpoints."""
    scope = _model_scope(mode)
    revision = subprocess.run(
        ["git", "-C", str(REPO_DIR), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    if revision.returncode != 0:
        raise RuntimeError("저장소가 준비되지 않았습니다. 노트북 ① 환경 준비 셀부터 실행하세요.")
    head = revision.stdout.strip()
    fingerprint = _runtime_contract_fingerprint()
    tag = f"py{sys.version_info.major}{sys.version_info.minor}"
    marker = WORK_ROOT / (
        f".environment-{RUNTIME_CONTRACT}-{tag}-{fingerprint[:16]}.ready"
    )
    if not marker.is_file():
        raise RuntimeError(
            "① 환경 설치를 먼저 완료하세요."
        )
    details = marker.read_text(encoding="utf-8")
    if f"installed_from_main={head}" not in details.splitlines():
        raise RuntimeError("① 환경 설치를 다시 실행하세요.")
    model_marker = _model_marker(scope)
    if not model_marker.is_file() or (
        f"installed_from_main={head}" not in model_marker.read_text(encoding="utf-8").splitlines()
        or f"model_scope={scope}" not in model_marker.read_text(encoding="utf-8").splitlines()
    ):
        raise RuntimeError("② 모델 다운로드·검증을 먼저 완료하세요.")
    os.environ["TRIPOSR_DIR"] = str(TRIPOSR_DIR)
    if str(REPO_DIR) not in sys.path:
        sys.path.insert(0, str(REPO_DIR))
    return head, [f"환경 준비 확인: main {head[:12]} (패키지 재설치 없음)"]


def _gpu_snapshot() -> str:
    """Measure actual GPU utilization, including separate TripoSR subprocesses."""
    try:
        check = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.used,memory.total,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=4,
        )
        if check.returncode != 0:
            return "GPU 계측 불가 (nvidia-smi 오류)"
        line = next((x.strip() for x in check.stdout.splitlines() if x.strip()), "")
        used, total, util = (item.strip() for item in line.split(",")[:3])
        return f"GPU VRAM {used}/{total} MiB, 사용률 {util}%"
    except (ValueError, OSError, subprocess.TimeoutExpired, StopIteration):
        return "GPU 계측 불가 (GPU 런타임 연결 확인)"


def _stream_ui_task(handler, args, count, progress, *, preserve_avatar=None):
    """Bridge synchronous pipeline stages to live Gradio progress and log outputs."""
    # Import inside worker's try block. If any native package import fails,
    # report the traceback in Gradio instead of crashing its queue handler.
    events: queue.Queue = queue.Queue()
    run_id = uuid.uuid4().hex[:10]
    log_file = WORK_ROOT / "logs" / f"generation-{run_id}.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    transcript: List[str] = []
    stage_names = [
        "reference_quality", "input_gate", "reference_reconstruction", "template_fitting",
        "texture_transfer", "rig", "expressions", "gaze", "springbone",
        "vrm_export", "validator",
    ]
    current_stage = "대기 중"

    def worker() -> None:
        pipeline_logger = logging.getLogger("vtuber_pipeline")
        old_level = pipeline_logger.level
        worker_id = threading.get_ident()

        class PipelineLogHandler(logging.Handler):
            def emit(self, record):
                if record.thread == worker_id:
                    events.put(("python_log", record.name, self.format(record)))

        logging_sink = PipelineLogHandler()
        logging_sink.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
        pipeline_logger.addHandler(logging_sink)
        pipeline_logger.setLevel(logging.INFO)
        try:
            from vtuber_pipeline.core.stage_progress import stage_reporter
            events.put(("stage", "pipeline", "running", "입력 검사"))
            with stage_reporter(lambda name, status, detail: events.put(
                ("stage", name, status, detail)
            )):
                result = handler(
                    *args,
                    progress=lambda fraction, desc="": events.put(
                        ("progress", float(fraction), str(desc))
                    ),
                )
            events.put(("done", result))
        except Exception:
            events.put(("crash", traceback.format_exc()))
        finally:
            pipeline_logger.removeHandler(logging_sink)
            pipeline_logger.setLevel(old_level)

    def append(message: str) -> str:
        timestamp = datetime.now(timezone.utc).astimezone().strftime("%H:%M:%S")
        entry = f"[{timestamp}] {message}"
        transcript.append(entry)
        with log_file.open("a", encoding="utf-8") as out:
            out.write(entry + "\n")
        print(entry, flush=True)
        return "\n".join(transcript[-250:])

    def show(message, logs, download=None, avatar_state=None):
        if count == 5:
            return (message, logs, download, avatar_state, str(log_file))
        return (message, logs, download, str(log_file))

    append(f"작업 시작 · {_gpu_snapshot()}")
    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    yield show("⏳ 생성 실행 중 · " + current_stage, "\n".join(transcript), avatar_state=preserve_avatar)
    last_gpu_sample = time.monotonic()
    while True:
        try:
            event = events.get(timeout=2)
        except queue.Empty:
            event = None
        if time.monotonic() - last_gpu_sample >= 2:
            logs = append(f"[GPU] {current_stage} · {_gpu_snapshot()}")
            last_gpu_sample = time.monotonic()
            yield show("⏳ " + current_stage, logs, avatar_state=preserve_avatar)
        if event is None:
            continue

        kind = event[0]
        if kind == "python_log":
            _, name, detail = event
            logs = append(f"[{name}] {detail}")
            yield show("⏳ " + current_stage, logs, avatar_state=preserve_avatar)
        elif kind == "stage":
            _, name, status, detail = event
            current_stage = f"{name} / {status}"
            info = f" [{detail}]" if detail else ""
            gpu = f" · {_gpu_snapshot()}" if status == "running" and (
                name == "reference_reconstruction" or name.startswith("accessory")
            ) else ""
            logs = append(f"[{name}] {status}{info}{gpu}")
            if name in stage_names and status == "running":
                progress((stage_names.index(name) + 1) / (len(stage_names) + 1),
                         desc=f"{name} 실행 중")
            yield show("⏳ 생성 실행 중 · " + current_stage, logs, avatar_state=preserve_avatar)
        elif kind == "progress":
            _, fraction, desc = event
            current_stage = desc or current_stage
            progress(max(0.0, min(1.0, fraction)), desc=current_stage)
            logs = append(f"[단계] {current_stage}")
            yield show("⏳ 생성 실행 중 · " + current_stage, logs, avatar_state=preserve_avatar)
        elif kind == "done":
            result = event[1]
            append(f"종료: {result[0]} · {_gpu_snapshot()}")
            if count == 5:
                status, existing_log, output, new_avatar = result
                if existing_log:
                    append(existing_log[-4000:])
                yield show(status, "\n".join(transcript[-250:]), output, new_avatar)
            else:
                status, existing_log, output = result
                if existing_log:
                    append(existing_log[-4000:])
                yield show(status, "\n".join(transcript[-250:]), output)
            break
        else:
            append("실행 예외: " + event[1])
            yield show("❌ 생성 중 예외 발생", "\n".join(transcript[-250:]), avatar_state=preserve_avatar)
            break


def stream_avatar_ui(
    image_path, commercial_usage, latest_avatar,
    face_image=None, back_image=None, full_body=True, texture_size=2048,
    left_image=None, right_image=None, rigging_provider="canonical",
    progress: gr.Progress = gr.Progress(),
):
    previous = latest_avatar if latest_avatar and pathlib.Path(latest_avatar).is_file() else None
    yield from _stream_ui_task(
        build_avatar_ui, (image_path, commercial_usage, latest_avatar, face_image, back_image,
                          full_body, texture_size, left_image, right_image, rigging_provider),
        5, progress, preserve_avatar=previous,
    )


def stream_accessories_ui(
    use_latest_avatar, base_vrm, latest_avatar, *slot_values,
    progress: gr.Progress = gr.Progress(),
):
    yield from _stream_ui_task(
        build_accessories_ui,
        (use_latest_avatar, base_vrm, latest_avatar, *slot_values),
        4, progress,
    )


def _pipeline_imports():
    from vtuber_pipeline.avatar import build_avatar
    from vtuber_pipeline.accessory import reconstruct_accessories, AccessoryPipeline

    return build_avatar, reconstruct_accessories, AccessoryPipeline


def _stage_log(stages: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    for name, result in stages.items():
        if not isinstance(result, dict):
            continue
        status = result.get("status", "unknown")
        detail = result.get("error") or result.get("warning")
        mark = "✓" if status == "complete" else "·" if status in {"cached", "skipped"} else "✗"
        line = f"{mark} {name}: {status}"
        if detail:
            line += f" — {detail}"
        lines.append(line)
    return lines


def build_avatar_ui(
    image_path: Optional[str],
    commercial_usage: str,
    latest_avatar: Optional[str],
    face_image: Optional[str] = None,
    back_image: Optional[str] = None,
    full_body: bool = False,
    texture_size: int = 2048,
    left_image: Optional[str] = None,
    right_image: Optional[str] = None,
    rigging_provider: str = "canonical",
    progress: gr.Progress = gr.Progress(),
):
    previous_avatar = (
        str(latest_avatar)
        if latest_avatar and pathlib.Path(latest_avatar).is_file()
        else None
    )

    logs: List[str] = []
    try:
        if not image_path:
            return "❌ 캐릭터 이미지를 선택하세요.", "", None, previous_avatar

        head, setup_logs = require_runtime_ready()
        logs.extend(setup_logs)

        # Generation is a read-only inference boundary: Blender must have
        # passed an actual VRM operator probe during the 3D setup transition.
        from tools.setup_blender_runtime import require_blender_runtime_ready
        blender_bin = require_blender_runtime_ready()
        logs.append(f"Blender VRM extension verified: {blender_bin}")
        progress(0.30, desc="Avatar 생성 시작")
        build_avatar, _, _ = _pipeline_imports()

        run_id = uuid.uuid4().hex[:10]
        output_dir = OUTPUT_ROOT / run_id / "3d"
        output_dir.mkdir(parents=True, exist_ok=True)

        result = build_avatar(
            image_path=str(image_path),
            output_dir=str(output_dir),
            config={
                "profile": "commercial",
                "commercial_usage": commercial_usage,
                "rigging": {"provider": rigging_provider},
                "references": {
                    "full_body": bool(full_body),
                    "face_image": str(face_image) if face_image else None,
                    "back_image": str(back_image) if back_image else None,
                    "left_image": str(left_image) if left_image else None,
                    "right_image": str(right_image) if right_image else None,
                    "texture_size": int(texture_size),
                },
            },
        )
        logs.extend(_stage_log(result.get("stages", {})))

        if result.get("status") != "complete":
            reason = (
                result.get("failed_reason")
                or result.get("failed_stages")
                or result.get("status")
            )
            return (
                f"❌ Avatar 생성 실패: {reason}",
                "\n".join(logs),
                None,
                previous_avatar,
            )

        vrm_path = pathlib.Path(result["vrm_path"])
        if not vrm_path.is_file():
            raise RuntimeError(f"VRM output missing: {vrm_path}")

        auto_download_dir = os.environ.get("VTUBER_COLAB_AUTODOWNLOAD_DIR")
        delivery = ""
        if auto_download_dir:
            from tools.colab_download_contract import publish_avatar_download
            # The separate notebook process owns google.colab.files.download;
            # Gradio can only publish a verified, atomic delivery request.
            # Never say "download completed" from the server process.
            try:
                delivery_event = publish_avatar_download(
                    vrm_path, OUTPUT_ROOT, auto_download_dir
                )
                delivery = " · avatar.vrm 직접 다운로드 링크 생성 중 (브라우저 차단 시 다운로드 버튼 사용)"
                logs.append(f"Colab 자동 다운로드 전달 요청: {delivery_event.name}")
            except Exception as exc:
                delivery = " · ⚠️ 다운로드 링크 생성 실패; 아래 직접 다운로드 버튼 사용"
                logs.append(
                    f"자동 다운로드 전달 실패: {type(exc).__name__}: {exc}"
                )

        progress(1.0, desc="완료")
        logs.append(f"완료: {vrm_path.name}")
        logs.append(f"완성 VRM 경로: {vrm_path.resolve()}")
        return (
            f"✅ 캐릭터 VRM 생성 완료 · main {head[:12]}{delivery}",
            "\n".join(logs),
            str(vrm_path),
            str(vrm_path),
        )
    except Exception as exc:
        logs.append(traceback.format_exc())
        return (
            f"❌ 실패: {exc}",
            "\n".join(logs),
            None,
            previous_avatar,
        )


def _normalize_file_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    name = getattr(value, "name", None)
    return str(name) if name else None


def build_accessories_ui(
    use_latest_avatar: bool,
    base_vrm: Any,
    latest_avatar: Optional[str],
    *slot_values: Any,
    progress: gr.Progress = gr.Progress(),
):
    logs: List[str] = []

    try:
        head, setup_logs = require_runtime_ready()
        logs.extend(setup_logs)
        _, reconstruct_accessories, AccessoryPipeline = _pipeline_imports()

        base_path: Optional[str] = None
        if use_latest_avatar and latest_avatar and pathlib.Path(latest_avatar).is_file():
            base_path = latest_avatar
        else:
            base_path = _normalize_file_value(base_vrm)

        if not base_path or not pathlib.Path(base_path).is_file():
            return (
                "❌ 기준 캐릭터 VRM을 선택하세요.",
                "\n".join(logs),
                None,
            )

        slot_width = 7
        if len(slot_values) % slot_width != 0:
            raise RuntimeError("Accessory slot contract mismatch")

        slots: List[Dict[str, Any]] = []
        for i in range(0, len(slot_values), slot_width):
            image_value = slot_values[i]
            anchor = str(slot_values[i + 1] or "HEAD_TOP")
            image_path = _normalize_file_value(image_value)
            if not image_path:
                continue

            slot: Dict[str, Any] = {
                "image": image_path,
                "anchor": anchor,
            }
            if anchor == "CUSTOM":
                parent_bone = str(slot_values[i + 2] or "").strip()
                if not parent_bone:
                    raise RuntimeError(
                        "CUSTOM 부착 위치는 parent bone/node 이름이 필요합니다."
                    )
                try:
                    offset = [
                        float(slot_values[i + 3]),
                        float(slot_values[i + 4]),
                        float(slot_values[i + 5]),
                    ]
                    target_size = float(slot_values[i + 6])
                except (TypeError, ValueError) as exc:
                    raise RuntimeError(
                        "CUSTOM offset/size는 숫자여야 합니다."
                    ) from exc
                if target_size <= 0.0:
                    raise RuntimeError("CUSTOM target size는 0보다 커야 합니다.")
                slot["custom_anchor"] = {
                    "parent_bone": parent_bone,
                    "offset": offset,
                    "target_size": target_size,
                }
            slots.append(slot)

        if not slots:
            return (
                "❌ 악세사리 이미지를 1개 이상 선택하세요.",
                "\n".join(logs),
                None,
            )

        from vtuber_pipeline.core.stage_progress import report_stage
        progress(0.30, desc="악세사리 3D 재구성")
        report_stage("accessory_reconstruction", "running", f"{len(slots)}개")
        source_paths = [slot["image"] for slot in slots]
        recon_dir = OUTPUT_ROOT / f"accessory-recon-{uuid.uuid4().hex[:10]}"
        reconstructed = reconstruct_accessories(
            source_paths,
            str(recon_dir),
            profile="commercial",
        )
        report_stage("accessory_reconstruction", "complete" if all(
            item.get("status") == "complete" for item in reconstructed
        ) else "error", f"{len(reconstructed)}개")
        if len(reconstructed) != len(slots):
            raise RuntimeError(
                f"Accessory reconstruction count mismatch: {len(reconstructed)} != {len(slots)}"
            )

        current_vrm = base_path
        total = len(slots)

        for index, (slot, item) in enumerate(
            zip(slots, reconstructed),
            start=1,
        ):
            source_path = slot["image"]
            anchor = slot["anchor"]
            if item.get("status") != "complete" or not item.get("mesh"):
                raise RuntimeError(
                    f"{pathlib.Path(source_path).name} 3D 재구성 실패: "
                    f"{item.get('error') or item}"
                )

            progress(
                0.35 + 0.55 * (index - 1) / max(total, 1),
                desc=f"악세사리 {index}/{total} 적용",
            )
            report_stage(f"accessory_{index}_bake", "running", f"{anchor}")
            logs.append(
                f"[{index}/{total}] {pathlib.Path(source_path).name} → {anchor}"
            )

            item_dir = OUTPUT_ROOT / f"accessory-{uuid.uuid4().hex[:10]}"
            result = AccessoryPipeline(str(item_dir)).build(
                base_vrm=current_vrm,
                accessory_glb=item["mesh"],
                config={
                    "anchor_name": anchor,
                    "custom_anchor": slot.get("custom_anchor"),
                    "bake": True,
                },
            )
            logs.extend(
                _stage_log(
                    {
                        f"{pathlib.Path(source_path).name}/{name}": stage
                        for name, stage in result.get("stages", {}).items()
                    }
                )
            )

            if result.get("status") != "complete":
                raise RuntimeError(
                    f"{pathlib.Path(source_path).name} 적용 실패: "
                    f"{result.get('failed_stages') or result.get('failed_reason') or result.get('status')}"
                )
            current_vrm = result["output_vrm"]
            report_stage(f"accessory_{index}_bake", "complete", str(current_vrm))

        final_path = pathlib.Path(current_vrm)
        if not final_path.is_file():
            raise RuntimeError(f"Combined VRM output missing: {final_path}")

        progress(1.0, desc="완료")
        logs.append(f"완료: {final_path.name}")
        return (
            f"✅ 악세사리 적용 완료 · {total}개 · main {head[:12]}",
            "\n".join(logs),
            str(final_path),
        )
    except Exception as exc:
        logs.append(traceback.format_exc())
        return (
            f"❌ 실패: {exc}",
            "\n".join(logs),
            None,
        )


CSS = """
.gradio-container {max-width: 1280px !important; margin: 0 auto !important;}
#workflow-start {max-width: 690px; margin: 32px auto; padding: 22px !important;}
#workflow-start .gr-radio {font-size: 16px;}
#generation-panel {position: sticky; top: 12px; align-self: flex-start;}
#generation-panel textarea {font-family: ui-monospace, SFMono-Regular, Menlo, monospace;}
@media (max-width: 850px) {#generation-panel {position: static;}}
"""


def build_2d_ui(image_path, layers_zip, commercial_usage, target="live2d"):
    """Run actual 2D production graph, with strict editor/native status."""
    if target not in {"inochi2d", "live2d"}:
        return "지원하지 않는 2D 모드", "", None
    if not image_path:
        return "원본 캐릭터 이미지를 업로드하세요.", "", None
    try:
        require_runtime_ready(target)
        from vtuber_pipeline.common.schemas import SourceSet
        from vtuber_pipeline.two_d.build import build_inochi2d, build_live2d
        output = OUTPUT_ROOT / uuid.uuid4().hex[:10] / target
        source = SourceSet(mode=target, front_image=str(image_path),
                           user_layers_zip=str(layers_zip) if layers_zip else None,
                           commercial_usage=commercial_usage, output_dir=str(output))
        result = build_inochi2d(source) if target == "inochi2d" else build_live2d(source)
        details = (f"mode: {target}\nstatus: {result.status}\n"
                   f"primary_file: {result.primary_file}\neditable_file: {result.editable_file}\n"
                   f"error: {result.error or 'none'}")
        if result.status == "complete":
            message = f"{target}: 실제 방송용 모델 생성 완료"
        elif result.status == "needs_editor_export":
            message = "Live2D: Cubism 편집·정식 MOC3 출력이 필요합니다"
        elif result.status == "prepared":
            message = "Inochi2D: PSD/ORA/리깅 자료 준비 완료. 공식 SDK INP 내보내기 미완료"
        else:
            message = f"{target}: 제작 실패 (임시 그림 파일을 모델 완성으로 표시하지 않음)"
        return message, details, result.primary_file if result.primary_file and pathlib.Path(result.primary_file).is_file() else None
    except Exception as exc:
        return f"{target} 제작 실패: {exc}", traceback.format_exc(), None


def collect_cubism_zip_ui(official_zip):
    """Securely extract the official Cubism ZIP and validate its runtime files."""
    if not official_zip:
        return "공식 Cubism 출력 ZIP을 업로드하세요", "", None
    try:
        import zipfile
        from pathlib import Path, PurePosixPath
        from vtuber_pipeline.two_d.cubism_handoff import collect_official_export
        output = OUTPUT_ROOT / f"live2d-official-{uuid.uuid4().hex[:10]}"
        unpack = output / "source"
        unpack.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(official_zip) as source:
            files=[f for f in source.infolist() if not f.is_dir()]
            if not files or len(files)>256 or sum(f.file_size for f in files)>1024*1024*1024:
                raise ValueError("invalid Cubism ZIP archive size/count")
            for member in files:
                rel=PurePosixPath(member.filename)
                if member.filename.startswith("/") or ".." in rel.parts or not rel.parts or (member.external_attr >> 16)&0o170000==0o120000:
                    raise ValueError("unsafe Cubism ZIP member")
                dest=unpack.joinpath(*rel.parts)
                dest.parent.mkdir(parents=True,exist_ok=True)
                with source.open(member) as inp, dest.open("wb") as out:
                    import shutil
                    shutil.copyfileobj(inp,out)
        result=collect_official_export(str(unpack),str(output))
        package=output/"live2d_official_export.zip"
        return "공식 MOC3 수집 완료", str(result.primary_file), str(package)
    except Exception as exc:
        return "공식 MOC3 검증/수집 실패: "+str(exc), traceback.format_exc(), None


def build_inochi2d_ui(image_path, layers_zip, commercial_usage):
    return build_2d_ui(image_path, layers_zip, commercial_usage, target="inochi2d")


def build_live2d_ui(image_path, layers_zip, commercial_usage):
    return build_2d_ui(image_path, layers_zip, commercial_usage, target="live2d")


def choose_workflow(mode: str, usage: str):
    """Route independently to named Inochi2D, Live2D, or 3D VRM workflows."""
    if mode not in {"inochi2d", "live2d", "3d"}:
        raise ValueError(f"Unsupported workflow mode: {mode!r}")
    if usage not in {"corporation", "personalProfit", "personalNonProfit"}:
        raise ValueError(f"Unsupported use scope: {usage!r}")
    # Each 2D worker runs in an isolated site-packages environment sharing
    # only the existing Colab PyTorch/CUDA installation. This must happen
    # before checkpoint fetch and before the generation button is enabled.
    if mode in {"inochi2d", "live2d"}:
        from tools.install_2d_workers import activate_2d_environment
        _setup_stage("2D alpha/SAM/FLUX worker environment", activate_2d_environment)
        if mode == "inochi2d":
            # Build the official SDK puppet exporter only for users who
            # selected Inochi; never burden Live2D/3D with DUB/SDL2.
            from tools.setup_inochi_runtime import ensure_inochi_native_runtime
            _setup_stage("Inochi SDK native rig exporter", ensure_inochi_native_runtime)
    else:
        # 3D workers actually require this exact source revision; neither
        # the 2D models nor shared Colab startup require the checkout.
        _setup_stage("3D TripoSR checkout", _sync_triposr)
        os.environ["TRIPOSR_DIR"] = str(TRIPOSR_DIR)
        # Full-body 3D references use exactly the same official alpha
        # segmentation worker as 2D, but not Florence/SAM/FLUX. Previously
        # selecting 3D never provisioned the required ANIME_SEGMENTATION_REPO.
        from tools.install_2d_workers import activate_alpha_environment
        _setup_stage("3D alpha-only worker environment", activate_alpha_environment)
        from tools.setup_blender_runtime import ensure_blender_runtime
        _setup_stage("3D Blender VRM operator verification", lambda: ensure_blender_runtime(
            str(WORK_ROOT / "third_party" / "blender")
        ))
    # Mode selection is the first checkpoint download boundary. Do not fetch
    # TripoSR/InstantMesh for 2D; do not fetch FLUX for 3D.
    prepare_models(mode)
    return (
        gr.update(visible=False),
        gr.update(visible=(mode == "inochi2d")),
        gr.update(visible=(mode == "live2d")),
        gr.update(visible=(mode == "3d")),
        gr.update(visible=False),
        usage,
    )


def select_workflow_view(mode: str, usage: str):
    """Show image uploads immediately; do not block navigation on pip/HF."""
    if mode not in {"inochi2d", "live2d", "3d"}:
        raise ValueError(f"Unsupported workflow mode: {mode!r}")
    if usage not in {"corporation", "personalProfit", "personalNonProfit"}:
        raise ValueError(f"Unsupported use scope: {usage!r}")
    label = {"inochi2d": "Inochi2D", "live2d": "Live2D", "3d": "3D VRM"}[mode]
    return (
        gr.update(visible=False),
        gr.update(visible=(mode == "inochi2d")),
        gr.update(visible=(mode == "live2d")),
        gr.update(visible=(mode == "3d")),
        gr.update(visible=False),
        usage,
        mode,
        f"{label} 이미지 업로드 화면입니다. 모델 및 환경 준비 중입니다. "
        "준비 완료 전에는 제작을 시작하지 마세요.",
        None,
    )


def prepare_selected_workflow_ui(mode: str, usage: str):
    """Retain the selected upload screen when an on-demand setup fails."""
    label = {"inochi2d": "Inochi2D", "live2d": "Live2D", "3d": "3D VRM"}.get(mode, mode)
    try:
        choose_workflow(mode, usage)
    except Exception as exc:
        path = WORK_ROOT / "logs" / f"workflow_setup_{mode}.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as output:
            output.write(f"\n[{datetime.now(timezone.utc).isoformat()}] {label} setup failure\n")
            output.write(traceback.format_exc() + "\n")
        # The failed command's stdout/stderr is also persisted in
        # worker_envs/two_d/logs/dependency_setup.log or runtime_setup.log.
        print(f"[workflow] {label} FAILED: {exc} (traceback: {path})", flush=True)
        return (
            f"{label} 환경/모델 준비 실패: {exc}\n"
            f"전체 호출 오류: {path}\n"
            f"pip 설치 상세: {WORK_ROOT / 'worker_envs' / 'two_d' / 'logs' / 'dependency_setup.log'}\n"
            "이미지는 계속 올릴 수 있습니다. 원인 수정 후 '환경·모델 준비 재시도'를 누르세요.",
            str(path),
        )
    return f"{label} 환경·모델 준비 및 검증 완료. 이미지 업로드 후 제작할 수 있습니다.", None


def return_to_workflow_choice():
    return (
        gr.update(visible=True), gr.update(visible=False),
        gr.update(visible=False), gr.update(visible=False),
        gr.update(visible=False),
    )


def show_3d_accessory():
    return gr.update(visible=False), gr.update(visible=True)


def show_3d_avatar():
    return gr.update(visible=True), gr.update(visible=False)


def build_app() -> gr.Blocks:
    with gr.Blocks(title="VTuber Builder") as demo:
        latest_avatar = gr.State(value=None)
        selected_usage = gr.State(value="corporation")
        selected_mode = gr.State(value="3d")
        gr.Markdown("# VTuber Builder")

        with gr.Group(visible=True, elem_id="workflow-start") as workflow_start:
            mode = gr.Radio(
                label="작업 선택",
                choices=[("Inochi2D", "inochi2d"), ("Live2D", "live2d"), ("3D VRM", "3d")],
                value="3d",
            )
            usage = gr.Radio(
                label="사용 범위",
                choices=[
                    ("기업 / 수익", "corporation"),
                    ("개인 수익", "personalProfit"),
                    ("개인 비영리", "personalNonProfit"),
                ],
                value="corporation",
            )
            enter_workflow = gr.Button("다음", variant="primary")

        workflow_setup_status = gr.Textbox(
            label="선택한 모드의 환경·모델 준비 상태", lines=4,
            interactive=False, value="작업 모드를 선택하고 다음을 누르세요.",
        )
        workflow_setup_log = gr.File(
            label="실패 시 전체 호출 오류 로그", interactive=False,
        )

        with gr.Column(visible=False) as inochi2d_view:
            gr.Markdown(
                "## Inochi2D\n"
                "외부에서 제작한 캐릭터 원본/투명 파츠를 업로드합니다. "
                "**오픈소스 Inochi Creator / Inochi Session**을 목표로 합니다. "
                "네이티브 SDK가 실제 .inp를 출력해야만 complete입니다."
            )
            inochi_back = gr.Button("← 모드 선택", size="sm", variant="secondary")
            inochi_retry = gr.Button("Inochi2D 환경·모델 준비 재시도", size="sm")
            inochi_image = gr.Image(
                label="Inochi2D 캐릭터 그림", sources=["upload"],
                type="filepath", height=390,
            )
            inochi_layers = gr.File(
                label="투명 PNG 파츠 ZIP (선택)", file_types=[".zip"], type="filepath",
            )
            with gr.Accordion("외부 이미지 AI용 Inochi2D 프롬프트", open=False):
                gr.Textbox(
                    label="Inochi2D 기본 캐릭터",
                    value="[TASK] Generate ONE high-resolution original anime VTuber character image, not a collage or model sheet. [FRAMING] 3:4 portrait, symmetrical straight FRONT orthographic view, head through mid-torso, neutral relaxed pose, shoulders and neck fully visible, both eyes open, mouth gently closed, ample margin around hair and shoulders. [DESIGN] Clear bangs, separate left/right side locks and rear hair, eyebrows, eyelids, irises and lips with sharply legible outlines; distinctive yet riggable costume details; coherent lighting, clean silhouette, consistent anatomy and color. [FOR 2D RIGGING] Nothing crosses eyes, cheeks, mouth or neck; allow space for head tilt and hair sway. [AVOID] angled camera, multiple characters, cropped hair, speech bubbles, accessories covering facial parts, lettering, watermark, cluttered background.", lines=5,
                )
                gr.Textbox(
                    label="Inochi2D 투명 파츠 보완",
                    value="[REFERENCE LOCK] Use the uploaded original FRONT character image as a strict identity, costume, palette, stroke-weight, head-shape and framing reference. [DELIVERABLE] Supply independent transparent RGBA PNG art for each requested Inochi2D layer, one layer per file, all EXACTLY the original image width and height and with identical pixel coordinates; preserve natural antialiased edges and unmodified visible pixels. [PARTS] Front/back hair segments, side locks, face/ears, separate eyes including closed-eye variants, eyebrows, mouth closed/open/interior, neck, torso and deformable costume details. [HIDDEN ART] Extend scalp behind bangs, cheeks under hair and skin/clothing behind movable boundaries so deformation does not expose holes. [AVOID] redrawing the design, shifting the character, flattening the background into layers, montage sheets or opaque rectangles. If separate aligned PNG files cannot be produced, supply only an explicit reference, not falsely labeled rig-ready layers.", lines=5,
                )
            inochi_run = gr.Button("Inochi2D 네이티브 퍼펫 제작", variant="primary")
            inochi_status = gr.Markdown("대기 중")
            inochi_report = gr.Textbox(
                label="Inochi2D 입력·파츠 검사", interactive=False, lines=5,
            )
            inochi_result = gr.File(
                label="Inochi2D 결과 (.inp 성공 시)",
                interactive=False,
            )
            inochi_run.click(
                fn=build_inochi2d_ui,
                inputs=[inochi_image, inochi_layers, selected_usage],
                outputs=[inochi_status, inochi_report, inochi_result],
                show_progress="full",
                concurrency_id="vtuber_gpu_pipeline",
                concurrency_limit=1,
            )

        with gr.Column(visible=False) as live2d_view:
            gr.Markdown(
                "## Live2D\n"
                "외부 AI/일러스트 프로그램으로 제작한 이미지를 올리세요. "
                "레이어 패키지를 생성하며, Cubism 리깅과 .moc3 출력은 별도로 필요합니다. "
                "공식 Cubism Editor 내보내기 전에는 needs_editor_export입니다."
            )
            live2d_back = gr.Button("← 모드 선택", size="sm", variant="secondary")
            live2d_retry = gr.Button("Live2D 환경·모델 준비 재시도", size="sm")
            two_d_image = gr.Image(
                label="2D 캐릭터 원본 일러스트 (필수)",
                sources=["upload"], type="filepath", height=390,
            )
            two_d_layers = gr.File(
                label="분리된 투명 PNG 파츠 ZIP (선택; 모든 PNG는 원본과 동일한 캔버스)",
                file_types=[".zip"], type="filepath",
            )
            with gr.Accordion("외부 대형 AI에 넣을 2D 제작 프롬프트", open=False):
                gr.Textbox(
                    label="2D 전면 캐릭터 일러스트",
                    value="[TASK] Draw ONE original anime VTuber bust-up FRONT master image optimized for Live2D Cubism layer separation, not a character sheet. [GEOMETRY] Symmetric orthographic viewpoint, straight head, relaxed neck and shoulders, calm neutral expression, eyes fully open and mouth closed, head and hair fully inside 3:4 portrait canvas. [SEPARATION] Clearly defined independent bangs, side/back hair, ears, brows, upper/lower lids, eye whites, irises, pupils, highlights, nose, lips, mouth opening, neck, clothing and accessories. [QUALITY] High resolution, sharp antialiased outlines, simple uniform backdrop, consistent lighting and visible skin boundaries for yaw/pitch and blinking deformers. [AVOID] three-quarter pose, face obstruction, exaggerated perspective, merged hair/face borders, multi-panel layout, lettering or watermark.", lines=5,
                )
                gr.Textbox(
                    label="파츠 분리 보완 프롬프트",
                    value="[REFERENCE LOCK] Match the uploaded Live2D FRONT master image pixel-for-pixel in appearance, color, line style, proportions and original canvas coordinates. [OUTPUT] Each separable part must be an individual full-canvas RGBA PNG with transparent pixels everywhere outside the painted part; use unchanged width, height, registration and scale for every file, suitable for assembling into a layered PSD. [LAYERS] Face/base scalp/ears; individual front, side and rear hair groups; left and right eyebrows, sclera, iris/pupil, upper and lower eyelids and lashes; upper/lower lips, internal mouth, tongue and teeth; torso, neck and costume ornaments. [DEFORMATION COVERAGE] Paint plausible hidden skin, hair roots and mouth interiors underneath moving layers, with closed-eye, smile and phoneme reference shapes exported separately and precisely aligned. [AVOID] sprite sheets, perspective changes, mismatched expressions between base layers, cropped parts, baked background, shifted canvas and fictional alpha. If the tool cannot deliver actual layered PNG files, request art references only and do not claim Cubism-ready layers.", lines=6,
                )
            two_d_run = gr.Button("Live2D Cubism 제작 자료 생성", variant="primary")
            two_d_status = gr.Markdown("대기 중")
            two_d_report = gr.Textbox(
                label="2D 준비 검사 결과", interactive=False, lines=5,
            )
            two_d_result = gr.File(
                label="Cubism 편집 자료 ZIP",
                interactive=False,
            )
            two_d_run.click(
                fn=build_live2d_ui,
                inputs=[two_d_image, two_d_layers, selected_usage],
                outputs=[two_d_status, two_d_report, two_d_result],
                show_progress="full",
                concurrency_id="vtuber_gpu_pipeline",
                concurrency_limit=1,
            )

            gr.Markdown("### 공식 Cubism Editor에서 출력한 모델 수집")
            cubism_official_zip = gr.File(label="공식 Cubism 출력 폴더 ZIP (.model3.json, .moc3, textures 포함)", file_types=[".zip"], type="filepath")
            cubism_import_button = gr.Button("공식 MOC3 수집 및 검증")
            cubism_import_button.click(
                fn=collect_cubism_zip_ui,
                inputs=[cubism_official_zip],
                outputs=[two_d_status, two_d_report, two_d_result],
                show_progress="full",
                concurrency_id="vtuber_gpu_pipeline",
                concurrency_limit=1,
            )

        with gr.Column(visible=False) as avatar_view:
            gr.Markdown("## 사용자 이미지 → 전신 VRM\n외부 AI에서 직접 만든 이미지를 업로드합니다. 이 프로그램은 이미지를 생성하지 않습니다.")
            avatar_back = gr.Button("← 2D / 3D 선택", size="sm", variant="secondary")
            avatar_retry = gr.Button("3D 환경·모델 준비 재시도", size="sm")
            avatar_to_accessory = gr.Button("3D 액세서리 제작 →", size="sm", variant="secondary")
            with gr.Row():
                with gr.Column(scale=2, min_width=360):
                    avatar_image = gr.Image(
                        label="전신 정면 이미지 (필수)",
                        sources=["upload"],
                        type="filepath",
                        height=430,
                    )
                    avatar_face_image = gr.Image(
                        label="얼굴 확대 이미지 (전신 고품질 모드 필수)",
                        sources=["upload"],
                        type="filepath",
                        height=260,
                    )
                    avatar_back_image = gr.Image(
                        label="전신 후면 이미지 (선택: 후면 텍스처에 사용)",
                        sources=["upload"],
                        type="filepath",
                        height=320,
                    )
                    avatar_left_image = gr.Image(
                        label="왼쪽 측면 참조 (선택)", sources=["upload"],
                        type="filepath", height=220,
                    )
                    avatar_right_image = gr.Image(
                        label="오른쪽 측면 참조 (선택)", sources=["upload"],
                        type="filepath", height=220,
                    )
                    avatar_full_body = gr.Checkbox(
                        label="전신 고품질 모드 (얼굴 확대 입력 필요)",
                        value=True,
                    )
                    avatar_texture_size = gr.Dropdown(
                        label="텍스처 아틀라스 해상도",
                        choices=[("2048×2048 (권장)", 2048), ("1024×1024 (빠름)", 1024)],
                        value=2048,
                    )
                    avatar_rigging_provider = gr.Dropdown(
                        label="3D 자동 스키닝 엔진",
                        choices=[("기본 휴머노이드 + 머리카락 리깅 (검증 경로)", "canonical"),
                                 ("Blender 자동 본 히트 스키닝 (T4 지원·실험적)", "blender_heat"),
                                 ("SkinTokens 실험적 스키닝 (Ampere+ CUDA만 가능)", "skintokens")],
                        value="canonical",
                    )
                    avatar_skintokens_setup = gr.Button(
                        "SkinTokens 별도 설치·검증 (T4 불가 · Ampere 이상 GPU)",
                        size="sm", variant="secondary",
                    )
                    with gr.Accordion("외부 이미지 생성 AI에 넣을 제작 프롬프트", open=False):
                        gr.Markdown("이 프롬프트를 외부 대형 이미지 AI에 복사해 이미지를 만든 다음 위에 업로드하세요. **AI 이미지 생성 기능은 이 프로그램에 포함되지 않습니다.**")
                        gr.Textbox(
                            label="전신 정면 원본",
                            value="[OUTPUT] Create exactly ONE full-body front-view anime VTuber reference image (not a turnaround collage); 2:3 or 3:4 portrait, high resolution. [CAMERA] Strict FRONT orthographic, eye-level, no foreshortening, full body centered head-to-soles and completely inside canvas. [POSE] Symmetrical relaxed A-pose with arms slightly away from torso; separated hands and visible fingers, legs and shoes not overlapping, neutral straight gaze. [GEOMETRY] Clear silhouettes for front/back hair, sleeves, hips and footwear; preserve anatomical proportions and garment seams suitable for reconstructing a rigged 3D character. [CONSISTENCY] Uniform neutral light, plain contrasting background without cast shadow, one distinctive costume and palette to be held identical in all additional views. [AVOID] props hiding body, dramatic lighting, floating/cropped hands or feet, multiple people, words, watermarks or perspective lens.", lines=5,
                        )
                        gr.Textbox(
                            label="같은 캐릭터 얼굴 확대 (필수 권장)",
                            value="[REFERENCE] Use the already-generated FULL-BODY FRONT image as a mandatory visual identity reference; do not redesign anything. [OUTPUT] ONE detailed face-and-hairline close-up only, same character, FRONT orthographic, centered, both ears/eyebrows/eyelids/eyes/nose/lips and full facial outline readable, eyes open, mouth softly closed, neutral expression. [FIDELITY] Exactly preserve iris hue, pupil structure, bangs, hair roots, skin tone, face proportions, accessories, line width and illumination from the full-body reference. Crisp eye and mouth details for expression reconstruction. [AVOID] perspective yaw/tilt, selfies, portrait lens distortion, new hairstyle, open mouth, hair over eyes, extra faces, text or collage.", lines=5,
                        )
                        gr.Textbox(
                            label="같은 캐릭터 전신 후면 (선택)",
                            value="[REFERENCE LOCK] Use the same character FRONT image as an immutable design sheet; match the precise height, limb proportions, A-pose arm angle, clothing fit, materials, hair length, color and shoe geometry. [OUTPUT] ONE complete full-body REAR orthographic view, same centered frame and scale as front reference, visible back of head/hair, seams, costume closures, calves and soles. Neutral lighting, plain background, all hands and feet uncropped. [AVOID] mirror-flipped front texture, new garment details inconsistent with front, three-quarter camera, body turn, extra subjects, labels or multi-panel layout.", lines=5,
                        )
                        gr.Textbox(
                            label="같은 캐릭터 측면 (선택)",
                            value="[REFERENCE LOCK] Keep exactly the same character design, standing height, proportions, A-pose, hair volume, costume colors and shoe geometry as the FRONT image. [OUTPUT] ONE complete full-body LEFT SIDE orthographic image if creating the left-reference file, or ONE RIGHT SIDE orthographic image for the right-reference file; generate each direction in a separate image. Camera level and scale must match the front and rear images. Render clear facial profile, true head depth, chest/back contour, hairstyle thickness, wrists, legs and shoes; plain background, flat consistent lighting. [AVOID] three-quarter angles, perspective, cropped extremities, inconsistent costume/hair, collage, text and watermark.", lines=21, max_lines=30,
                        interactive=False, autoscroll=True,
                    )
                    avatar_log_file = gr.File(
                        label="전체 로그", interactive=False,
                    )

            avatar_skintokens_setup.click(
                fn=prepare_skintokens_ui,
                inputs=[], outputs=[avatar_status],
                show_progress="full",
                concurrency_id="vtuber_gpu_pipeline", concurrency_limit=1,
            )

            avatar_generation_event = avatar_run.click(
                fn=stream_avatar_ui,
                inputs=[avatar_image, selected_usage, latest_avatar, avatar_face_image, avatar_back_image,
                        avatar_full_body, avatar_texture_size, avatar_left_image, avatar_right_image,
                        avatar_rigging_provider],
                outputs=[
                    avatar_status, avatar_log, avatar_result,
                    latest_avatar, avatar_log_file,
                ],
                show_progress="full",
                concurrency_id="vtuber_gpu_pipeline",
                concurrency_limit=1,
            )
            # A direct anchor to our same-port FastAPI attachment endpoint
            # is the primary reliable fallback. Gradio 6.3 serves .vrm files
            # as 'inline' at /gradio_api/file=, so that route is insufficient.
            def show_download_controls(path):
                if not path:
                    return gr.update(value=None, interactive=False), gr.update(
                        value="", visible=False,
                    )
                from tools.colab_download_contract import gradio_file_route
                route = gradio_file_route(path, OUTPUT_ROOT)
                return (
                    gr.update(value=path, interactive=True),
                    gr.update(
                        value=(
                            f"**[↓ avatar.vrm 다운로드 (브라우저 저장)]({route})**"
                            f"  \nColab 파일: `{path}`"
                        ),
                        visible=True,
                    ),
                )

            avatar_generation_event.then(
                fn=show_download_controls,
                inputs=avatar_result,
                outputs=[avatar_download_button, avatar_http_link],
                show_progress="hidden",
            )

        with gr.Column(visible=False) as accessory_view:
            gr.Markdown("## 악세사리 VRM")
            accessory_back = gr.Button("← 3D VRM 제작", size="sm", variant="secondary")
            with gr.Row():
                with gr.Column(scale=2, min_width=360):
                    use_latest = gr.Checkbox(
                        label="이 세션의 캐릭터 VRM 사용",
                        value=True,
                    )
                    base_vrm = gr.File(
                        label="또는 기준 VRM 업로드",
                        file_types=[".vrm"],
                        type="filepath",
                    )
                    accessory_inputs: List[Any] = []
                    for slot in range(8):
                        with gr.Accordion(f"악세사리 {slot + 1}", open=(slot == 0)):
                            with gr.Row():
                                image = gr.Image(
                                    label=f"이미지 {slot + 1}",
                                    sources=["upload"],
                                    type="filepath",
                                    height=200,
                                )
                                anchor = gr.Dropdown(
                                    label="부착 위치", choices=ANCHORS, value="HEAD_TOP",
                                )
                            with gr.Accordion("세부 위치", open=False):
                                custom_parent = gr.Dropdown(
                                    label="CUSTOM parent bone/node",
                                    choices=[
                                        "head", "neck", "chest", "upperChest", "hips",
                                        "leftShoulder", "rightShoulder",
                                        "leftHand", "rightHand",
                                        "leftFoot", "rightFoot",
                                    ],
                                    value="head", allow_custom_value=True,
                                )
                                with gr.Row():
                                    custom_x = gr.Number(label="X", value=0.0)
                                    custom_y = gr.Number(label="Y", value=0.0)
                                    custom_z = gr.Number(label="Z", value=0.0)
                                    custom_size = gr.Number(
                                        label="크기", value=0.12, minimum=0.001,
                                    )
                            accessory_inputs.extend([
                                image, anchor, custom_parent, custom_x,
                                custom_y, custom_z, custom_size,
                            ])

                    accessory_run = gr.Button("악세사리 적용", variant="primary")
                    accessory_result = gr.File(
                        label="완성 VRM", interactive=False,
                    )
                with gr.Column(scale=1, min_width=310, elem_id="generation-panel"):
                    accessory_status = gr.Markdown("대기 중")
                    accessory_log = gr.Textbox(
                        label="진행 로그", lines=21, max_lines=30,
                        interactive=False, autoscroll=True,
                    )
                    accessory_log_file = gr.File(
                        label="전체 로그", interactive=False,
                    )

            accessory_run.click(
                fn=stream_accessories_ui,
                inputs=[use_latest, base_vrm, latest_avatar, *accessory_inputs],
                outputs=[
                    accessory_status, accessory_log, accessory_result,
                    accessory_log_file,
                ],
                show_progress="full",
                concurrency_id="vtuber_gpu_pipeline",
                concurrency_limit=1,
            )

        selected_event = enter_workflow.click(
            fn=select_workflow_view, inputs=[mode, usage],
            outputs=[
                workflow_start, inochi2d_view, live2d_view, avatar_view,
                accessory_view, selected_usage, selected_mode,
                workflow_setup_status, workflow_setup_log,
            ],
            show_progress="hidden",
        )
        selected_event.then(
            fn=prepare_selected_workflow_ui,
            inputs=[selected_mode, selected_usage],
            outputs=[workflow_setup_status, workflow_setup_log],
            show_progress="full",
            concurrency_id="vtuber_model_setup",
            concurrency_limit=1,
        )
        for retry in (inochi_retry, live2d_retry, avatar_retry):
            retry.click(
                fn=prepare_selected_workflow_ui,
                inputs=[selected_mode, selected_usage],
                outputs=[workflow_setup_status, workflow_setup_log],
                show_progress="full",
                concurrency_id="vtuber_model_setup",
                concurrency_limit=1,
            )
        for back in (inochi_back, live2d_back, avatar_back):
            back.click(
                fn=return_to_workflow_choice,
                outputs=[workflow_start, inochi2d_view, live2d_view, avatar_view, accessory_view],
                show_progress="hidden",
            )
        avatar_to_accessory.click(
            fn=show_3d_accessory,
            outputs=[avatar_view, accessory_view],
            show_progress="hidden",
        )
        accessory_back.click(
            fn=show_3d_avatar,
            outputs=[avatar_view, accessory_view],
            show_progress="hidden",
        )

    return demo


def launch() -> None:
    # Notebook cells share one Python kernel even after a fresh git reset.
    # Old imported package modules can have incompatible stage contracts.
    _reload_pipeline_modules()
    # The 2D artwork-preparation route must not depend on 3D model assets.
    # build_avatar_ui and build_accessories_ui check 3D readiness at their
    # execution boundary, so they remain fail-closed without TripoSR.
    WORK_ROOT.mkdir(parents=True, exist_ok=True)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    demo = build_app()
    demo.queue(default_concurrency_limit=1)

    # Gradio 6.3.0 is pinned by the notebook because later 6.x releases have
    # a documented Colab share=False regression. Keep the cell alive while
    # the inline UI server is running.
    # Colab starts the server in a *fresh* Python process after pip completes.
    # Its iframe is displayed separately by the notebook kernel. Do not run
    # the server inside the kernel that may hold pre-install NumPy C modules.
    subprocess_ui = os.environ.get("VTUBER_COLAB_EXTERNAL_IFRAME") == "1"
    port = int(os.environ.get("VTUBER_COLAB_SERVER_PORT", "7860"))
    demo.launch(
        inline=not subprocess_ui,
        share=False,
        debug=not subprocess_ui,
        prevent_thread_lock=subprocess_ui,
        server_name="0.0.0.0" if subprocess_ui else None,
        server_port=port if subprocess_ui else None,
        show_error=True,
        height=1100,
        allowed_paths=[str(WORK_ROOT), str(OUTPUT_ROOT)],
        css=CSS,
        theme=gr.themes.Soft(),
    )
    # Install the HTTP attachment route on the Gradio app *after* Gradio
    # creates its FastAPI instance, before blocking the subprocess. The route
    # is the only path guaranteeing that .vrm is downloaded, not viewed inline.
    if subprocess_ui:
        from tools.colab_download_contract import install_direct_download_route
        install_direct_download_route(demo.server_app, OUTPUT_ROOT)
        demo.block_thread()


if __name__ == "__main__":
    launch()
