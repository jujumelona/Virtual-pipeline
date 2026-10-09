"""Worker contract; exceptions fail without creating success artifacts."""
import json
from pathlib import Path
import sys
import traceback

# Direct script invocation also works in an isolated, non-editable worker venv.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

def require_cuda():
    """GPU production fails early; explicit CPU validation remains available."""
    import os
    if os.environ.get("VTUBER_REQUIRE_CUDA") == "1":
        import torch
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA GPU unavailable: production CPU fallback is disabled")


def execute(fn):
    if len(sys.argv) != 3:
        raise SystemExit("usage: worker.py request.json result.json")
    req = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    try:
        require_cuda()
        result = fn(req)
        if not isinstance(result, dict):
            raise TypeError("worker returned non-object")
        result["status"] = "complete"
    except Exception as exc:
        result = {"status": "error", "error": str(exc), "traceback": traceback.format_exc()}
    Path(sys.argv[2]).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if result["status"] != "complete":
        raise SystemExit(1)
