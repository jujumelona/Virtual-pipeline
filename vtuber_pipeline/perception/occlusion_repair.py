"""Masked reference editing; restored pixels NEVER replace visible source pixels."""
from pathlib import Path
from vtuber_pipeline.common.schemas import PartsDocument
from ._worker import invoke

def fill_hidden_parts(parts: PartsDocument, original_path: str, output_dir: str) -> PartsDocument:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    manifest = parts.write(str(out / "pre_repair_parts.json"))
    result = invoke("flux", {"parts_json": manifest, "image_path": original_path,
                             "output_dir": output_dir}, output_dir, timeout=3600)
    return PartsDocument.read(result["parts_json"])
