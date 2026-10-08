"""Use the existing pinned anime face detector, not synthetic landmarks."""
from pathlib import Path
def detect(image_path: str, output_dir: str) -> dict:
    from vtuber_pipeline.avatar.face_detector import AnimeFaceDetector
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    target = out / "face_landmarks.json"
    result = AnimeFaceDetector().detect_and_save(image_path, str(target))
    if not target.is_file():
        raise RuntimeError("face detector did not save landmarks")
    return {"landmarks_json": str(target), "data": result}
