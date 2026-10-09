"""Explicit, bounded parallel dependency and checkpoint preparation for Colab v8.

Never perform installs in a generation worker. Independent isolated worker
environments and external source checkouts may run concurrently, but the
shared base-Python pip resolver is run only by ensure_runtime(), first.
Model prefetch already uses bounded concurrent download workers and is
scheduled after the required worker environments have been installed.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
from pathlib import Path
import runpy
import sys
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]


def _run_parallel(tasks: tuple[tuple[str, Callable[[], object]], ...]) -> None:
    """Finish all scheduled independent setup tasks; aggregate every failure."""
    if not tasks:
        return
    print(f"[downloads] {len(tasks)} independent tasks, "
          f"parallel workers={min(3, len(tasks))}", flush=True)
    failures = []
    with ThreadPoolExecutor(max_workers=min(3, len(tasks))) as pool:
        futures = {pool.submit(fn): name for name, fn in tasks}
        for future in as_completed(futures):
            name = futures[future]
            try:
                future.result()
            except Exception as exc:
                print(f"[downloads] {name}: FAILED ({type(exc).__name__}: {exc})",
                      flush=True)
                failures.append(f"{name}: {exc}")
            else:
                print(f"[downloads] {name}: OK", flush=True)
    if failures:
        raise RuntimeError("Model/program setup failed: " + " | ".join(failures))


def prepare_selected_mode(
    mode: str, usage: str = "corporation", *,
    prewarm_first_gpu: bool = True,
) -> None:
    # Accessory fitting starts with different 3D GPU work; prewarming the
    # face detector would block that stage behind an unused CUDA allocation.
    if mode == "accessory":
        mode = "3d"
        prewarm_first_gpu = False
    if mode not in {"3d", "inochi2d", "live2d"}:
        raise ValueError(f"Unknown preparation mode: {mode}")
    if usage not in {"corporation", "personalProfit", "personalNonProfit"}:
        raise ValueError(f"Invalid usage: {usage}")
    os.environ["VTUBER_SETUP_ONLY"] = "1"
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    if prewarm_first_gpu:
        os.environ["VTUBER_GPU_PREWARM"] = "1"
    else:
        os.environ.pop("VTUBER_GPU_PREWARM", None)
        # If a user changes from portrait to full-body/accessories while a
        # detector is waiting, unload it before the actual first GPU stage.
        from tools.colab_gpu_warmup import stop_face_worker

        stop_face_worker()
    app = runpy.run_path(str(ROOT / "tools" / "colab_app.py"),
                         run_name="vtuber_prepare")
    # The base Python dependencies are shared and must NOT be installed
    # concurrently with another base pip invocation.
    app["ensure_runtime"]()
    if mode in {"inochi2d", "live2d"}:
        from tools.install_2d_workers import activate_2d_environment

        # The base runtime already contains HF and the pinned face detector.
        # Checkpoint transfers are independent of the isolated SAM/FLUX pip
        # installs; run both at once instead of waiting for package setup.
        tasks: list[tuple[str, Callable[[], object]]] = [
            ("2D alpha/SAM/FLUX worker software", activate_2d_environment),
            ("2D pinned model checkpoints / first GPU face loader",
             lambda: app["prepare_models"](mode)),
        ]
        if mode == "inochi2d":
            # The official SDK uses an independent native build root. Its
            # failure remains visible and cannot imply a completed INP puppet.
            tasks.append((
                "Inochi native exporter",
                lambda: app["_prepare_inochi_exporter_best_effort"](
                    "Inochi SDK native rig exporter"),
            ))
    else:
        from tools.install_2d_workers import activate_alpha_environment
        from tools.setup_blender_runtime import ensure_blender_runtime

        tasks = [
            ("3D TripoSR source checkout", app["_sync_triposr"]),
            ("3D alpha worker packages", activate_alpha_environment),
            ("3D Blender VRM runtime",
             lambda: ensure_blender_runtime(
                 str(app["WORK_ROOT"] / "third_party" / "blender"))),
            # Downloading the pinned TripoSR snapshot is independent of
            # checking out its source. Both files are verified separately.
            ("3D pinned model checkpoints / first GPU face loader",
             lambda: app["prepare_models"](mode)),
        ]
    _run_parallel(tuple(tasks))
    app["require_runtime_ready"](mode)
    # Model-cache hits return early; ensure that the next real face inference
    # can still reuse a resident model when previous downloads already exist.
    if prewarm_first_gpu:
        from tools.colab_gpu_warmup import available_face_worker, start_face_worker

        if not available_face_worker():
            print("[gpu-prewarm] checkpoint cache was already ready; "
                  "starting reusable face detector", flush=True)
            start_face_worker()
    print(f"[downloads] {mode}: all mandatory downloads and checks complete",
          flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("3d", "inochi2d", "live2d", "accessory"),
                        required=True)
    parser.add_argument("--usage",
                        choices=("corporation", "personalProfit", "personalNonProfit"),
                        default="corporation")
    parser.add_argument("--no-first-gpu-prewarm", action="store_true",
                        help="Do not load unused face detector before a full-body 3D job")
    args = parser.parse_args()
    prepare_selected_mode(args.mode, args.usage,
                          prewarm_first_gpu=not args.no_first_gpu_prewarm)


if __name__ == "__main__":
    main()
