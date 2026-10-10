"""Disposable VTS process. Native crashes are observed by the notebook parent."""
from __future__ import annotations

import argparse
import faulthandler
import json
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True, type=Path)
    args = parser.parse_args()
    faulthandler.enable()
    request = json.loads(args.request.read_text(encoding="utf-8"))
    from tools.vts_handoff_process import memory_snapshot, _save
    print("[VTS] VTS_WORKER_START: " + json.dumps({"pid": os.getpid(), "memory": memory_snapshot()}), flush=True)
    from tools.vts_production import make_cubism_handoff
    options = request["options"]
    for key in ("reference_image", "external_psd", "generated_psd", "third_party"):
        if options.get(key) is not None:
            options[key] = Path(options[key])
    report = make_cubism_handoff(Path(request["master"]), Path(request["output"]), _worker=True, **options)
    _save(Path(request["output"]) / "handoff_result.json", report)


if __name__ == "__main__":
    main()
