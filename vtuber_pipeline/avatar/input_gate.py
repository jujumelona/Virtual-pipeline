"""Input quality gate for VTuber avatar reconstruction."""

import hashlib
import pathlib
import traceback
from typing import Dict, Any

from vtuber_pipeline.core.stage_progress import report_stage


def validate_input(image_path: str, output_dir: str) -> Dict[str, Any]:
    """Validate image geometry and real anime-face detector output.

    Detector failures are hard failures; no synthetic "all checks passed"
    fallback is permitted.
    """
    result: Dict[str, Any] = {
        "image_path": image_path, "valid": False, "checks": {}, "errors": [],
        "landmarks": [], "landmark_count": 0,
    }
    report_stage("input_diagnostics", "log", f"validate_input source={__file__}")
    try:
        from PIL import Image
        import numpy as np
        from vtuber_pipeline.avatar.face_detector import AnimeFaceDetector

        with Image.open(image_path) as img:
            img.verify()
        with Image.open(image_path) as img:
            width, height = img.size

        result.update({"width": width, "height": height})
        report_stage("input_diagnostics", "log", f"image={width}x{height} file={pathlib.Path(image_path).name}")
        result["checks"]["image_decodes"] = True
        result["checks"]["min_resolution"] = width >= 256 and height >= 256
        aspect = width / max(height, 1)
        result["aspect_ratio"] = aspect
        result["checks"]["aspect_ratio"] = 0.5 <= aspect <= 2.0

        detector = AnimeFaceDetector()
        report_stage(
            "input_diagnostics", "log",
            f"face detector={type(detector).__module__}.{type(detector).__name__}",
        )
        face = detector.detect(image_path)
        report_stage(
            "input_diagnostics", "log",
            f"detector result keys={sorted(face)} bbox={face.get('bbox')} "
            f"landmarks={len(face.get('landmarks') or [])} "
            f"scores={len(face.get('landmark_scores') or [])} "
            f"confidence={face.get('score')}",
        )
        bbox = np.asarray(face["bbox"], dtype=float)
        landmarks = np.asarray(face.get("landmarks", []), dtype=float)
        landmark_scores = np.asarray(
            face.get("landmark_scores", []),
            dtype=float,
        )
        score = float(face.get("score", 0.0))

        if bbox.shape != (4,) or not np.all(np.isfinite(bbox)):
            raise ValueError("Detected face bbox must contain 4 finite values")
        if bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
            raise ValueError("Detected face bbox has non-positive extent")

        result["checks"]["face_detected"] = True
        result["checks"]["confidence"] = score >= 0.5
        result["confidence"] = score

        face_area = max(bbox[2] - bbox[0], 0) * max(bbox[3] - bbox[1], 0)
        face_area_ratio = float(face_area / max(width * height, 1))
        result["face_area_ratio"] = face_area_ratio
        # VTuber half-body/torso portraits often place a valid face at 2–5%
        # of the whole frame. The detector still must return a confident,
        # finite face box and all 28 scored landmarks.
        result["checks"]["face_area_ratio"] = 0.015 <= face_area_ratio <= 0.8
        report_stage(
            "input_diagnostics", "log",
            f"face_area_ratio={face_area_ratio:.4f} required=[0.015,0.8]",
        )

        valid_landmarks = (
            landmarks.shape == (28, 2)
            and np.all(np.isfinite(landmarks))
            and landmark_scores.shape == (28,)
            and np.all(np.isfinite(landmark_scores))
        )
        if valid_landmarks:
            landmark_median = float(np.median(landmark_scores))
            landmark_min = float(np.min(landmark_scores))
        else:
            landmark_median = 0.0
            landmark_min = 0.0

        result["landmark_score_median"] = landmark_median
        result["landmark_score_min"] = landmark_min
        result["checks"]["landmark_confidence"] = bool(
            valid_landmarks
            and landmark_median >= 0.50
            and landmark_min >= 0.15
        )
        result["landmark_count"] = int(len(landmarks)) if landmarks.ndim else 0
        result["bbox"] = bbox.tolist()
        result["landmarks"] = landmarks.tolist() if valid_landmarks else []
        report_stage(
            "input_diagnostics", "log",
            f"parsed landmarks={result['landmark_count']}/28 "
            f"shape={landmarks.shape} score_shape={landmark_scores.shape} "
            f"median={landmark_median:.3f} min={landmark_min:.3f}",
        )

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
        result["checks"].setdefault("input_exception", False)
        result["errors"].append(f"{type(exc).__name__}: {exc}")
        report_stage("input_diagnostics", "error", traceback.format_exc())

    result["pass"] = bool(result["checks"]) and all(result["checks"].values())
    if not result["pass"] and not result["errors"]:
        failed = sorted(
            name for name, passed in result["checks"].items() if not passed
        )
        result["errors"].append(
            "Input quality checks failed: "
            + ", ".join(failed)
            + f" (landmarks={result.get('landmark_count', 0)}/28, "
            + f"median_confidence={result.get('landmark_score_median', 0.0):.3f})"
        )
    # Success cannot be based on checkbox booleans alone. A valid gate must
    # export the actual 28 points consumed by template fitting.
    if result["pass"] and len(result["landmarks"]) != 28:
        result["pass"] = False
        result["errors"].append(
            f"input output contract violation: {len(result['landmarks'])}/28 landmarks"
        )
    result["valid"] = result["pass"]
    result["status"] = "complete" if result["pass"] else "error"
    failed = [name for name, ok in result["checks"].items() if not ok]
    report_stage(
        "input_diagnostics", "log",
        f"gate status={result['status']} keys={sorted(result)} "
        f"checks={result['checks']} failed={failed} errors={result['errors']}",
    )
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
