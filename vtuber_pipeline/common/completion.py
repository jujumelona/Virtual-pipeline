"""A package or placeholder is never a completed broadcast asset."""
from pathlib import Path

def _nonempty(path: str | None) -> bool:
    return bool(path and Path(path).is_file() and Path(path).stat().st_size > 0)

def validate_build_result(result) -> None:
    if result.status not in ("failed", "prepared", "needs_editor_export", "complete"):
        raise ValueError("invalid production status")
    if result.status != "complete":
        return
    if not _nonempty(result.primary_file):
        raise ValueError("complete requires an existing nonempty primary_file")
    suffix = Path(result.primary_file).suffix.lower()
    required = {"inochi2d": ".inp", "live2d": ".moc3", "3d": ".vrm"}
    if suffix != required[result.mode]:
        raise ValueError("primary format does not match mode")
    if result.mode == "live2d":
        from vtuber_pipeline.two_d.cubism_handoff import validate_official_export
        validate_official_export(str(Path(result.primary_file).parent))
    if result.mode == "3d":
        from vtuber_pipeline.avatar.validator import validate_vrm
        report = validate_vrm(result.primary_file, result.intermediate_dir, product_contract=True)
        if report.get("status") != "complete" or not report.get("passed"):
            raise ValueError("invalid VRM humanoid/product contract")
