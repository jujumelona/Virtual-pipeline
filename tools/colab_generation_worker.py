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


def run_request(request: dict) -> list:
    kind = request.get("mode")
    values = request.get("args")
    if kind not in MODES or not isinstance(values, list):
        raise ValueError("Unknown production mode or invalid arguments")
    # runpy's setup-only entrypoint suppresses the Gradio import even if
    # the subprocess is missing/changing server-side UI dependencies.
    app = runpy.run_path(str(ROOT / "tools" / "colab_app.py"), run_name="vtuber_prepare")
    if kind == "inochi2d":
        if len(values) != 2:
            raise ValueError("Inochi2D expects character image and usage")
        return list(app["_run_2d_production_inline"](*values, target="inochi2d"))
    if kind == "live2d":
        if len(values) != 2:
            raise ValueError("Live2D expects character image and usage")
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
    try:
        os.environ["VTUBER_GENERATION_WORKER"] = "1"
        request = json.loads(request_path.read_text(encoding="utf-8"))
        result = run_request(request)
        if len(result) != (4 if request["mode"] == "avatar" else 3):
            raise RuntimeError("Production callback result dimension mismatch")
        temp = result_path.with_suffix(".tmp")
        temp.write_text(json.dumps({"result": result}, ensure_ascii=False), encoding="utf-8")
        temp.replace(result_path)
        emit("complete", mode=request["mode"])
        return 0
    except BaseException:
        traceback.print_exc()
        emit("failed", mode="unknown", error=traceback.format_exc()[-4000:])
        return 1


if __name__ == "__main__":
    sys.exit(main())
