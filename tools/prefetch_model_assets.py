"""Download pinned model/template assets concurrently after dependency installation.

Every worker is a separate CPU-only Python process. Never run pip installs in
parallel, and never begin inference before all mandatory assets verify.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import deque
from pathlib import Path
import subprocess
import sys
import threading
from typing import Callable, Sequence

from tools.model_log_output import is_weight_progress, quiet_model_environment

ROOT = Path(__file__).resolve().parents[1]
MAX_WORKERS = 3
TASKS: tuple[tuple[str, str], ...] = (
    (
        "TripoSR",
        "from vtuber_pipeline.avatar.reconstruction import resolve_triposr_model; "
        "print(resolve_triposr_model(), flush=True)",
    ),
    (
        "YOLO/HRNet",
        "from vtuber_pipeline.avatar.face_detector import resolve_anime_face_model_paths; "
        "print(resolve_anime_face_model_paths(), flush=True)",
    ),
    (
        "u2net",
        "from vtuber_pipeline.avatar.triposr_runner import _verify_rembg_u2net; "
        "print(_verify_rembg_u2net(), flush=True)",
    ),
    (
        "DINO",
        "from vtuber_pipeline.avatar.triposr_runner import DINO_MODEL_ID, DINO_MODEL_REVISION; "
        "from huggingface_hub import hf_hub_download; "
        "print(hf_hub_download(repo_id=DINO_MODEL_ID, filename='config.json', "
        "revision=DINO_MODEL_REVISION), flush=True)",
    ),
    (
        "MakeHuman",
        "from vtuber_pipeline.avatar.template_mesh import get_template_path; "
        "print(get_template_path(), flush=True)",
    ),
)


def run_model_task(label: str, code: str, *, timeout: int = 2400) -> None:
    """Run one immutable model verification and emit labeled lines immediately."""
    process = subprocess.Popen(
        [sys.executable, "-u", "-c", code],
        cwd=str(ROOT),
        env=quiet_model_environment(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    # Never accumulate entire multi-GB checkpoint transfer transcripts in RAM.
    lines: deque[str] = deque(maxlen=60)

    def read_output() -> None:
        assert process.stdout is not None
        for line in process.stdout:
            line = line.rstrip("\n")
            if is_weight_progress(line):
                continue
            lines.append(line)
            print(f"[{label}] {line}", flush=True)

    reader = threading.Thread(target=read_output, daemon=True)
    reader.start()
    try:
        code_status = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        process.kill()
        process.wait(timeout=10)
        reader.join(timeout=10)
        raise RuntimeError(f"{label} 준비 시간 초과 ({timeout}s)") from exc
    reader.join(timeout=10)
    if code_status:
        raise RuntimeError(
            f"{label} 모델 준비 실패 (exit={code_status}): "
            + "\n".join(lines[-15:])
        )


def prefetch_assets(
    tasks: Sequence[tuple[str, str]] = TASKS,
    *,
    workers: int = MAX_WORKERS,
    runner: Callable[[str, str], None] = run_model_task,
) -> None:
    if not 1 <= workers <= MAX_WORKERS:
        raise ValueError(f"workers must be between 1 and {MAX_WORKERS}")
    if len(set(label for label, _ in tasks)) != len(tasks):
        raise ValueError("Duplicate model task labels")
    print(f"[models] {len(tasks)}개 모델/메시 자산 검증 (최대 {workers}개 병렬)", flush=True)
    failures: list[str] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(runner, label, code): label
            for label, code in tasks
        }
        for future in as_completed(futures):
            label = futures[future]
            try:
                future.result()
                print(f"[models] {label}: 완료", flush=True)
            except Exception as exc:
                failures.append(f"{label}: {exc}")
                print(f"[models] {label}: 실패 — {exc}", flush=True)
    if failures:
        raise RuntimeError("모델 준비 실패: " + " | ".join(failures))
    print("[models] 모든 필수 모델 준비 완료", flush=True)


# Explicit per-mode opt-in; legacy prefetch_assets() still verifies existing 3D pins.
from vtuber_pipeline.common.model_assets import MODE_ASSETS, MODELS, record_artifacts
MODEL_ASSETS = MODE_ASSETS

def prefetch_mode(mode: str, *, cache_dir: str | None = None, timeout: int = 2400) -> None:
    """Download only requested mode checkpoints using a separate, short-lived process.

    The active model process will subsequently import/verify its own code dependencies.
    A network error raises, without writing a success marker or treating a partial file as ready.
    """
    if mode not in ("common_2d", "common_2d_layers", "3d"):
        raise ValueError("unsupported prefetch mode")
    # CPU-only checkpoint verification processes are independent. Reuse the
    # bounded executor instead of serially waiting through HF downloads.
    # Actual neural inference remains strictly serialized by the UI queue.
    import os

    warm_first_face = os.environ.get("VTUBER_GPU_PREWARM") == "1"
    work: list[tuple[str, str]] = []
    if warm_first_face:
        # Launch verified YOLO/HRNet on GPU as soon as THEIR checkpoints
        # arrive, while two other CPU-only asset download slots continue.
        # The persistent one-shot worker is reused by real face inference;
        # it is not a throwaway CUDA smoke test.
        work.append((
            "first-gpu-face-detector",
            "from vtuber_pipeline.avatar.face_detector import "
            "resolve_anime_face_model_paths; "
            "resolve_anime_face_model_paths(); "
            "from tools.colab_gpu_warmup import start_face_worker; "
            "print('[gpu-prewarm] resident=' + str(start_face_worker()),flush=True)",
        ))
    for name in MODE_ASSETS[mode]:
        if warm_first_face and name in (
            "anime_face_yolov3", "anime_face_hrnetv2"
        ):
            continue
        # The InstantMesh model checkpoint is not a clearance to execute the
        # bundled CC-BY-NC Zero123++/Nvidia source renderer. Delay this large
        # download until a permitted end-to-end runtime is explicitly verified.
        if mode == "3d" and name == "instantmesh_large":
            print("[prefetch] InstantMesh checkpoint deferred: runtime licence "
                  "gate must pass before full-body inference", flush=True)
            continue
        if name in ("anime_face_yolov3", "anime_face_hrnetv2"):
            code = "from vtuber_pipeline.avatar.face_detector import resolve_anime_face_model_paths; resolve_anime_face_model_paths()"
        elif name == "triposr":
            code = "from vtuber_pipeline.avatar.reconstruction import resolve_triposr_model; resolve_triposr_model()"
        else:
            code = (
                "from vtuber_pipeline.common.model_assets import resolve_snapshot; "
                f"print(resolve_snapshot({name!r}, cache_dir={cache_dir!r}), flush=True)"
            )
        work.append((name, code))
    if mode == "3d":
        # These files are not independent selectable model families, but the
        # deployed TripoSR/rig pipeline requires them in its environment.
        for label, code in TASKS:
            if label in {"DINO", "u2net", "MakeHuman"}:
                work.append((label, code))
    if not work:
        raise RuntimeError("selected mode has no license-cleared model assets")
    prefetch_assets(
        tuple(work),
        workers=min(MAX_WORKERS, len(work)),
        runner=lambda label, code: run_model_task(label, code, timeout=timeout),
    )


def main(argv: Sequence[str] | None = None) -> None:
    """Explicit mode prefetch without auto-installing unrelated model families."""
    import argparse
    parser = argparse.ArgumentParser(description="VTuber mode-scoped model prefetch")
    parser.add_argument("--mode", choices=("common_2d", "common_2d_layers", "3d", "legacy"), default="legacy")
    parser.add_argument("--timeout", type=int, default=2400)
    arguments = parser.parse_args(argv)
    if arguments.timeout < 1:
        parser.error("--timeout must be positive")
    if arguments.mode == "legacy":
        prefetch_assets()
    else:
        prefetch_mode(arguments.mode, timeout=arguments.timeout)


if __name__ == "__main__":
    main()
