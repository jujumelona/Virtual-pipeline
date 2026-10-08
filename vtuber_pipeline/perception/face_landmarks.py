"""Use the existing pinned anime face detector, not synthetic landmarks."""
from pathlib import Path
def detect(image_path: str, output_dir: str) -> dict:
    from vtuber_pipeline.avatar.face_detector import AnimeFaceDetector
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    target = out / "face_landmarks.json"
    result = AnimeFaceDetector().detect_and_save(image_path, str(target))
    # Coordinates are meaningful only in the pixel space of the image which
    # produced them. A separate face close-up cannot be used as boxes on the
    # full-body image without a calibrated registration.
    import json
    from PIL import Image
    with Image.open(image_path) as image:
        canvas_size = list(image.size)
    documented = dict(result)
    documented["image_size"] = canvas_size
    documented["source_image"] = str(Path(image_path).resolve())
    target.write_text(json.dumps(documented, indent=2), encoding="utf-8")
    if not target.is_file():
        raise RuntimeError("face detector did not save landmarks")
    return {"landmarks_json": str(target), "data": result}
