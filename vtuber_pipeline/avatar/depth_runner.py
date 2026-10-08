"""Depth Anything V2 Small: independent per-observed-view relative depth."""
from __future__ import annotations
from pathlib import Path
import json
import os
import sys
from vtuber_pipeline.common.stage_runner import run_stage

def estimate_depth(front_image: str, back_image: str | None,
                   left_image: str | None, right_image: str | None,
                   output_dir: str) -> dict:
    images={"front":front_image,"back":back_image,"left":left_image,"right":right_image}
    for role,path in images.items():
        if path and not Path(path).is_file():
            raise FileNotFoundError(f"{role}: {path}")
    output=Path(output_dir).resolve()
    output.mkdir(parents=True,exist_ok=True)
    request=output/"depth.request.json"
    response=output/"depth.result.json"
    request.write_text(json.dumps({"images":images,"output_dir":str(output)}),encoding="utf-8")
    worker=Path(__file__).resolve().parents[2]/"tools/model_workers/depth_worker.py"
    return run_stage(worker=str(worker),request_json=str(request),result_json=str(response),
                     executable=os.getenv("VTUBER_WORKER_DEPTH",sys.executable),
                     cwd=str(Path(__file__).resolve().parents[2]),timeout_sec=1800)
