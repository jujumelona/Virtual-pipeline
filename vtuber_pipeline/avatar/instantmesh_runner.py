"""Native InstantMesh large adapter in a disposable model-worker process."""
from __future__ import annotations
from pathlib import Path
import json
import os
import sys
from vtuber_pipeline.common.stage_runner import run_stage

def reconstruct_multiview(front_rgba: str, output_dir: str, *,
                          commercial_usage: str = "corporation",
                          coarse_obj: str | None = None) -> dict:
    source=Path(front_rgba).resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    root=Path(output_dir).resolve()
    root.mkdir(parents=True,exist_ok=True)
    request=root/"instantmesh.request.json"
    result=root/"instantmesh.result.json"
    if coarse_obj is not None and not Path(coarse_obj).is_file():
        raise FileNotFoundError(coarse_obj)
    request.write_text(json.dumps({"front_rgba":str(source),"output_dir":str(root),
                                   "commercial_usage":commercial_usage,
                                   "coarse_obj":str(Path(coarse_obj).resolve()) if coarse_obj else None}),encoding="utf-8")
    worker=Path(__file__).resolve().parents[2]/"tools/model_workers/instantmesh_worker.py"
    return run_stage(worker=str(worker),request_json=str(request),result_json=str(result),
                     executable=os.getenv("VTUBER_WORKER_INSTANTMESH",sys.executable),
                     cwd=str(Path(__file__).resolve().parents[2]),timeout_sec=3600)
