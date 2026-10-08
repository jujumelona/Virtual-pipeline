"""Worker contract; exceptions fail without creating success artifacts."""
import json
from pathlib import Path
import sys
import traceback

def execute(fn):
    if len(sys.argv) != 3:
        raise SystemExit("usage: worker.py request.json result.json")
    req = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    try:
        result = fn(req)
        if not isinstance(result, dict):
            raise TypeError("worker returned non-object")
        result["status"] = "complete"
    except Exception as exc:
        result = {"status": "error", "error": str(exc), "traceback": traceback.format_exc()}
    Path(sys.argv[2]).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if result["status"] != "complete":
        raise SystemExit(1)
