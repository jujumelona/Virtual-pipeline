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


def _model_marker() -> pathlib.Path:
    tag = f"py{sys.version_info.major}{sys.version_info.minor}"
    return WORK_ROOT / (
        f".models-{RUNTIME_CONTRACT}-{tag}-{_model_fingerprint()[:16]}.ready"
    )


def prepare_models() -> None:
    """Separate prerequisite: download/verify every model before opening UI."""
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
    marker = _model_marker()
    if marker.is_file():
        lines = marker.read_text(encoding="utf-8").splitlines()
        if f"model_fingerprint={_model_fingerprint()}" in lines:
            if f"installed_from_main={head}" not in lines:
                lines = [line for line in lines if not line.startswith("installed_from_main=")]
                lines.append(f"installed_from_main={head}")
                marker.write_text("\n".join(lines) + "\n", encoding="utf-8")
            print("[models] 검증된 모델 캐시 사용", flush=True)
            return
    print("[models] TripoSR / YOLO / HRNet / u2net / DINO / MakeHuman", flush=True)
    _run(
        [sys.executable, "-u", str(REPO_DIR / "tools" / "prefetch_model_assets.py")],
        timeout=3000,
    )
    # A success marker must only exist after all parallel workers finish.
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(
        f"model_fingerprint={_model_fingerprint()}\n"
        f"installed_from_main={head}\n",
        encoding="utf-8",
    )


def _reload_pipeline_modules() -> None:
    for name in list(sys.modules):
        if name == "vtuber_pipeline" or name.startswith("vtuber_pipeline."):
            del sys.modules[name]


def ensure_runtime(
    progress: Optional[gr.Progress] = None,
) -> Tuple[str, List[str]]:
    global _RUNTIME_READY_HEAD

    logs: List[str] = []

    if progress:
        progress(0.04, desc="최신 main 확인")
    head = _sync_repo()
    logs.append(f"최신 main: {head[:12]}")

    if _RUNTIME_READY_HEAD == head:
        os.environ["TRIPOSR_DIR"] = str(TRIPOSR_DIR)
        return head, logs

    if progress:
        progress(0.12, desc="TripoSR 준비")
    _sync_triposr()
    logs.append(f"TripoSR: {TRIPOSR_COMMIT[:12]}")

    if progress:
        progress(0.20, desc="필요 패키지 준비")
    _install_runtime(head)
    logs.append("Python 환경 준비 완료")

    _reload_pipeline_modules()
    _RUNTIME_READY_HEAD = head
    return head, logs



def require_runtime_ready() -> Tuple[str, List[str]]:
    """Generation MUST NOT install dependencies, sync Git or download models."""
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
    model_marker = _model_marker()
    if not model_marker.is_file() or (
        f"installed_from_main={head}" not in model_marker.read_text(encoding="utf-8").splitlines()
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
    from vtuber_pipeline.core.stage_progress import stage_reporter

    events: queue.Queue = queue.Queue()
    run_id = uuid.uuid4().hex[:10]
    log_file = WORK_ROOT / "logs" / f"generation-{run_id}.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    transcript: List[str] = []
    stage_names = [
        "input_gate", "reference_reconstruction", "template_fitting",
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
    progress: gr.Progress = gr.Progress(),
):
    previous = latest_avatar if latest_avatar and pathlib.Path(latest_avatar).is_file() else None
    yield from _stream_ui_task(
        build_avatar_ui, (image_path, commercial_usage, latest_avatar),
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

        progress(0.30, desc="Avatar 생성 시작")
        build_avatar, _, _ = _pipeline_imports()

        run_id = uuid.uuid4().hex[:10]
        output_dir = OUTPUT_ROOT / f"avatar-{run_id}"
        output_dir.mkdir(parents=True, exist_ok=True)

        result = build_avatar(
            image_path=str(image_path),
            output_dir=str(output_dir),
            config={
                "profile": "commercial",
                "commercial_usage": commercial_usage,
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

        progress(1.0, desc="완료")
        logs.append(f"완료: {vrm_path.name}")
        return (
            f"✅ 캐릭터 VRM 생성 완료 · main {head[:12]}",
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


def choose_workflow(mode: str, usage: str):
    """Choose one existing pipeline and carry the user-selected license scope."""
    if mode not in {"avatar", "accessory"}:
        raise ValueError(f"Unsupported workflow mode: {mode!r}")
    if usage not in {"corporation", "personalProfit", "personalNonProfit"}:
        raise ValueError(f"Unsupported use scope: {usage!r}")
    return (
        gr.update(visible=False),
        gr.update(visible=(mode == "avatar")),
        gr.update(visible=(mode == "accessory")),
        usage,
    )


def return_to_workflow_choice():
    return (gr.update(visible=True), gr.update(visible=False),
            gr.update(visible=False))


def build_app() -> gr.Blocks:
    with gr.Blocks(title="VTuber Builder") as demo:
        latest_avatar = gr.State(value=None)
        selected_usage = gr.State(value="corporation")
        gr.Markdown("# VTuber Builder")

        with gr.Group(visible=True, elem_id="workflow-start") as workflow_start:
            mode = gr.Radio(
                label="작업 선택",
                choices=[("캐릭터 / 얼굴", "avatar"), ("악세사리", "accessory")],
                value="avatar",
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

        with gr.Column(visible=False) as avatar_view:
            gr.Markdown("## 캐릭터 VRM")
            avatar_back = gr.Button("← 모드 선택", size="sm", variant="secondary")
            with gr.Row():
                with gr.Column(scale=2, min_width=360):
                    avatar_image = gr.Image(
                        label="캐릭터 이미지",
                        sources=["upload"],
                        type="filepath",
                        height=430,
                    )
                    avatar_run = gr.Button("캐릭터 생성", variant="primary")
                    avatar_result = gr.File(
                        label="완성 VRM",
                        interactive=False,
                    )
                with gr.Column(scale=1, min_width=310, elem_id="generation-panel"):
                    avatar_status = gr.Markdown("대기 중")
                    avatar_log = gr.Textbox(
                        label="진행 로그", lines=21, max_lines=30,
                        interactive=False, autoscroll=True,
                    )
                    avatar_log_file = gr.File(
                        label="전체 로그", interactive=False,
                    )

            avatar_run.click(
                fn=stream_avatar_ui,
                inputs=[avatar_image, selected_usage, latest_avatar],
                outputs=[
                    avatar_status, avatar_log, avatar_result,
                    latest_avatar, avatar_log_file,
                ],
                show_progress="full",
                concurrency_id="vtuber_gpu_pipeline",
                concurrency_limit=1,
            )

        with gr.Column(visible=False) as accessory_view:
            gr.Markdown("## 악세사리 VRM")
            accessory_back = gr.Button("← 모드 선택", size="sm", variant="secondary")
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

        enter_workflow.click(
            fn=choose_workflow, inputs=[mode, usage],
            outputs=[workflow_start, avatar_view, accessory_view, selected_usage],
            show_progress="hidden",
        )
        for back in (avatar_back, accessory_back):
            back.click(
                fn=return_to_workflow_choice,
                outputs=[workflow_start, avatar_view, accessory_view],
                show_progress="hidden",
            )

    return demo


def launch() -> None:
    # Do not show a usable-looking UI before the model assets are verified.
    require_runtime_ready()
    WORK_ROOT.mkdir(parents=True, exist_ok=True)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    demo = build_app()
    demo.queue(default_concurrency_limit=1)

    # Gradio 6.3.0 is pinned by the notebook because later 6.x releases have
    # a documented Colab share=False regression. Keep the cell alive while
    # the inline UI server is running.
    demo.launch(
        inline=True,
        share=False,
        debug=True,
        prevent_thread_lock=False,
        show_error=True,
        height=1100,
        allowed_paths=[str(WORK_ROOT), str(OUTPUT_ROOT)],
        css=CSS,
        theme=gr.themes.Soft(),
    )


if __name__ == "__main__":
    launch()
