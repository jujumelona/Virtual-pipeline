"""Input quality gate for VTuber avatar reconstruction."""

import hashlib
import pathlib
from typing import Dict, Any


def validate_input(image_path: str, output_dir: str) -> Dict[str, Any]:
    """Validate image geometry and real anime-face detector output.

    Detector failures are hard failures; no synthetic "all checks passed"
    fallback is permitted.
    """
    result: Dict[str, Any] = {
        "image_path": image_path, "valid": False, "checks": {}, "errors": []
    }
    try:
        from PIL import Image
        import numpy as np
        from vtuber_pipeline.avatar.face_detector import AnimeFaceDetector

        with Image.open(image_path) as img:
            img.verify()
        with Image.open(image_path) as img:
            width, height = img.size

        result.update({"width": width, "height": height})
        result["checks"]["image_decodes"] = True
        result["checks"]["min_resolution"] = width >= 256 and height >= 256
        aspect = width / max(height, 1)
        result["aspect_ratio"] = aspect
        result["checks"]["aspect_ratio"] = 0.5 <= aspect <= 2.0

        face = AnimeFaceDetector().detect(image_path)
        bbox = np.asarray(face["bbox"], dtype=float)
        landmarks = np.asarray(face.get("landmarks", []), dtype=float)
        score = float(face.get("score", 0.0))

        result["checks"]["face_detected"] = True
        result["checks"]["confidence"] = score >= 0.5
        result["confidence"] = score

        face_area = max(bbox[2] - bbox[0], 0) * max(bbox[3] - bbox[1], 0)
        face_area_ratio = float(face_area / max(width * height, 1))
        result["face_area_ratio"] = face_area_ratio
        result["checks"]["face_area_ratio"] = 0.05 <= face_area_ratio <= 0.8

        valid_landmarks = landmarks.ndim == 2 and len(landmarks) >= 28 and landmarks.shape[1] >= 2
        result["checks"]["landmark_confidence"] = bool(valid_landmarks)
        result["landmark_count"] = int(len(landmarks)) if landmarks.ndim else 0
        result["bbox"] = bbox.tolist()
        result["landmarks"] = landmarks.tolist() if landmarks.ndim == 2 else []

        if valid_landmarks:
            xy = landmarks[:28, :2]
            center_x = float((bbox[0] + bbox[2]) / 2.0)
            left = xy[xy[:, 0] < center_x, 0]
            right = xy[xy[:, 0] >= center_x, 0]
            left_extent = float(center_x - left.mean()) if len(left) else 0.0
            right_extent = float(right.mean() - center_x) if len(right) else 0.0
            denom = max(left_extent + right_extent, 1e-6)
            asymmetry = abs(left_extent - right_extent) / denom
            result["face_asymmetry"] = float(asymmetry)
            result["checks"]["face_symmetry"] = asymmetry <= 0.30

            ratio = max(left_extent, 1e-6) / max(right_extent, 1e-6)
            yaw_proxy = min(45.0, abs(float(np.log(ratio))) * 30.0)
            result["yaw_degrees_proxy"] = yaw_proxy
            result["checks"]["yaw_proxy"] = yaw_proxy <= 30.0
        else:
            result["checks"]["face_symmetry"] = False
            result["checks"]["yaw_proxy"] = False

        margin = max(10, int(min(width, height) * 0.02))
        touches = (
            bbox[0] < margin or bbox[1] < margin or
            bbox[2] > width - margin or bbox[3] > height - margin
        )
        result["checks"]["head_bbox_frame_contact"] = not bool(touches)

    except Exception as exc:
        result["checks"].setdefault("image_decodes", False)
        result["errors"].append(str(exc))

    result["pass"] = bool(result["checks"]) and all(result["checks"].values())
    result["valid"] = result["pass"]
    result["status"] = "complete" if result["pass"] else "error"
    result["input_hash"] = _compute_file_hash(image_path) if pathlib.Path(image_path).is_file() else None
    _write_quality_json(output_dir, result)
    return result


def _compute_file_hash(path: str) -> str:
    sha = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            sha.update(chunk)
    return sha.hexdigest()


def _write_quality_json(output_dir: str, result: Dict[str, Any]) -> None:
    from vtuber_pipeline.core.utils import save_json

    pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)
    save_json(result, str(pathlib.Path(output_dir) / "quality.json"))
