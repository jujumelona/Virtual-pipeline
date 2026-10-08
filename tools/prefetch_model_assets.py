"""Download pinned model/template assets concurrently after dependency installation.

Every worker is a separate CPU-only Python process. Never run pip installs in
parallel, and never begin inference before all mandatory assets verify.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import subprocess
import sys
import threading
from typing import Callable, Sequence

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
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    lines: list[str] = []

    def read_output() -> None:
        assert process.stdout is not None
        for line in process.stdout:
            line = line.rstrip("\n")
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


if __name__ == "__main__":
    prefetch_assets()
