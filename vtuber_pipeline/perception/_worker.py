"""Serial CPU/GPU worker interface with per-worker Python executables."""
import json
import os
from pathlib import Path
import sys
from vtuber_pipeline.common.stage_runner import run_stage

ROOT = Path(__file__).resolve().parents[2]
def invoke(worker: str, request: dict, output_dir: str, timeout: int = 1800) -> dict:
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    req, result = output / (worker + ".request.json"), output / (worker + ".result.json")
    request = dict(request)
    keys = {'anime_alpha': 'skytnt_anime_seg_isnet_is', 'florence': 'florence2_base',
            'sam': 'sam2_1_hiera_tiny', 'flux': 'flux2_klein_4b',
            'depth': 'depth_anything_v2_small', 'instantmesh': 'instantmesh_large'}
    if worker in keys:
        from vtuber_pipeline.common.model_assets import model_pin
        request['model_identity'] = model_pin(keys[worker])
    req.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
    executable = os.environ.get("VTUBER_WORKER_" + worker.upper().replace("-", "_"), sys.executable)
    return run_stage(worker=str(ROOT / "tools" / "model_workers" / (worker + "_worker.py")),
                     request_json=str(req), result_json=str(result),
                     executable=executable, cwd=str(ROOT), timeout_sec=timeout)
