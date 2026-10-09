"""Out-of-process Colab generation entrypoint.

Only one selected mode is executed. Gradio/its ASGI server are deliberately not
imported here: pip dependency changes, model import crashes and GPU OOMs must
not take down the UI process. The supervising process records stdout on disk.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import runpy
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
EVENT_PREFIX = "VTUBER_GENERATION_EVENT "
MODES = ("inochi2d", "live2d", "avatar", "accessory")


def emit(kind: str, **details) -> None:
    print(EVENT_PREFIX + json.dumps({"kind": kind, **details}, ensure_ascii=False), flush=True)


def materialize_sheet_request(request: dict, values: list) -> list:
    """GPU super-resolution exits BEFORE running other model stages."""
    import subprocess
    kind = request["mode"]
    if not (
        (kind in {"live2d", "inochi2d"} and len(values) == 3
         and values[2] == "__sheet_pack__")
        or (kind == "avatar" and len(values) == 10
            and values[2] == "__sheet_pack__")
    ):
        return values
    path = Path(values[0]).resolve(strict=True)
    output = Path(request.get("_sheet_workdir", path.parent / "sheet_generated"))
    output.mkdir(parents=True, exist_ok=True)
    stage_request = output / "request.json"
    stage_result = output / "result.json"
    stage_result.unlink(missing_ok=True)
    stage_request.write_text(json.dumps({
        "mode": "3d" if kind == "avatar" else kind,
        "sheet_zip": str(path), "output_dir": str(output / "rendered"),
    }, ensure_ascii=False), encoding="utf-8")
    emit("stage", stage="sheet-extract-neural-sr", status="running",
         detail="real GPU-tiled anime super-resolution in disposable PID")
    try:
        from tools.colab_gpu_warmup import available_face_worker, stop_face_worker
        from vtuber_pipeline.common.stage_runner import _process_gpu_lock
        if available_face_worker():
            stop_face_worker()
        with _process_gpu_lock(timeout_sec=7200):
            proc = subprocess.run([
                sys.executable, "-u", str(ROOT / "tools" / "sheet_prepare_worker.py"),
                "--request", str(stage_request), "--result", str(stage_result),
            ], timeout=7200, check=False)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Sheet neural SR timed out after 7200s") from exc
    if proc.returncode:
        raise RuntimeError(
            f"Sheet extraction/neural SR failed: exit={proc.returncode}; "
            f"input={stage_request}; output={stage_result}; "
            "checkpoint must be prepared in cell ③; no silent interpolation"
        )
    if not stage_result.is_file():
        raise RuntimeError("Sheet SR stage reported zero output manifest")
    result = json.loads(stage_result.read_text(encoding="utf-8"))
    emit("stage", stage="sheet-extract-neural-sr", status="complete",
         detail="SR model PID exited and CUDA memory released")
    if kind in {"live2d", "inochi2d"}:
        return [result["front"], values[1], result["layers"]]
    return [
        result["front"], values[1], None,
        result["face"], result["back"], True,
        values[6], result["left"], result["right"], values[9],
    ]


def run_request(request: dict) -> list:
    kind = request.get("mode")
    values = request.get("args")
    if kind not in MODES or not isinstance(values, list):
        raise ValueError("Unknown production mode or invalid arguments")
    values = materialize_sheet_request(request, values)
    # runpy's setup-only entrypoint suppresses the Gradio import even if
    # the subprocess is missing/changing server-side UI dependencies.
    app = runpy.run_path(str(ROOT / "tools" / "colab_app.py"), run_name="vtuber_prepare")
    if kind == "inochi2d":
        if len(values) not in (2, 3):
            raise ValueError("Inochi2D expects master image, usage, optional layer ZIP")
        return list(app["_run_2d_production_inline"](*values, target="inochi2d"))
    if kind == "live2d":
        if len(values) not in (2, 3):
            raise ValueError("Live2D expects master image, usage, optional layer ZIP")
        return list(app["_run_2d_production_inline"](*values, target="live2d"))
    if kind == "avatar":
        if len(values) != 10:
            raise ValueError("Avatar production argument contract mismatch")
        from vtuber_pipeline.core.stage_progress import stage_reporter
        def progress(fraction, desc=""):
            emit("progress", fraction=float(fraction), description=str(desc))
        with stage_reporter(lambda name, status, detail: emit(
                "stage", stage=str(name), status=str(status), detail=str(detail or ""))):
            return list(app["build_avatar_ui"](*values, progress=progress))
    if len(values) < 3 or (len(values) - 3) % 7:
        raise ValueError("Accessory production slots have invalid dimensions")
    from vtuber_pipeline.core.stage_progress import stage_reporter
    def progress(fraction, desc=""):
        emit("progress", fraction=float(fraction), description=str(desc))
    with stage_reporter(lambda name, status, detail: emit(
            "stage", stage=str(name), status=str(status), detail=str(detail or ""))):
        return list(app["build_accessories_ui"](*values, progress=progress))


def main() -> int:
    if len(sys.argv) != 3:
        print("Expected JSON request path and result path", file=sys.stderr, flush=True)
        return 2
    request_path, result_path = map(Path, sys.argv[1:])
    previous_cuda_policy = os.environ.get("VTUBER_REQUIRE_CUDA")
    try:
        # Under system-RAM pressure the disposable AI process should be killed
        # before the persistent Gradio/Colab control process. This is advisory
        # only; do not assume every Colab container permits writing procfs.
        try:
            Path("/proc/self/oom_score_adj").write_text("600", encoding="ascii")
        except (OSError, PermissionError):
            pass
        os.environ["VTUBER_GENERATION_WORKER"] = "1"
        os.environ["VTUBER_REQUIRE_CUDA"] = "1"
        request = json.loads(request_path.read_text(encoding="utf-8"))
        request["_sheet_workdir"] = str(request_path.parent / "sheet_generated")
        result = run_request(request)
        if len(result) != (4 if request["mode"] == "avatar" else 3):
            raise RuntimeError("Production callback result dimension mismatch")
        temp = result_path.with_suffix(".tmp")
        temp.write_text(json.dumps({"result": result}, ensure_ascii=False), encoding="utf-8")
        temp.replace(result_path)
        callback_status = str(result[0])
        # Callback-level failures are structured results, not successful model
        # completions. Preserve the result payload for notebook diagnostics,
        # but never emit a misleading "complete" event for a dead FLUX worker.
        if callback_status.startswith("❌") or " 제작 실패" in callback_status:
            emit("failed", mode=request["mode"],
                 callback_status=callback_status[:400],
                 details=str(result[1])[-2000:])
        else:
            emit("complete", mode=request["mode"])
        return 0
    except BaseException:
        traceback.print_exc()
        emit("failed", mode="unknown", error=traceback.format_exc()[-4000:])
        return 1
    finally:
        if previous_cuda_policy is None:
            os.environ.pop("VTUBER_REQUIRE_CUDA", None)
        else:
            os.environ["VTUBER_REQUIRE_CUDA"] = previous_cuda_policy


if __name__ == "__main__":
    sys.exit(main())
