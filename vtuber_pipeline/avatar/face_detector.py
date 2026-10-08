"""Anime face detection module for VTuber Pipeline."""

import hashlib
import pathlib
from typing import Dict, List, Any

# Optional dependencies
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    np = None
    NUMPY_AVAILABLE = False

try:
    from PIL import Image as PILImage
    PIL_AVAILABLE = True
except ImportError:
    PILImage = None
    PIL_AVAILABLE = False




ANIME_FACE_MODEL_PINS = {
    "hysts/anime-face-detector-yolov3": {
        "revision": "afdd4226a79ae8bb81f334dbcffd34f8cc000c38",
        "sha256": "23bbc708146bcbc1c910f00fe152adbc70d7658d875a0121eaf4ee61d978b2c4",
    },
    "hysts/anime-face-detector-hrnetv2": {
        "revision": "9b3435248b26aeb82e2a8578fe9d86d5d57158af",
        "sha256": "e71271376406a743c01528a0460637fcc06e72aeeea583f85007cc72dc8b7a4a",
    },
}


def _sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _create_pinned_anime_face_detector():
    """Create YOLOv3+HRNetV2 while pinning and verifying both HF weights."""
    import anime_face_detector
    import anime_face_detector.detector as detector_module

    original_download = detector_module.hf_hub_download

    def pinned_download(repo_id, filename, *args, **kwargs):
        pin = ANIME_FACE_MODEL_PINS.get(repo_id)
        if pin is not None:
            requested = kwargs.get("revision")
            if requested not in (None, pin["revision"]):
                raise RuntimeError(
                    "anime-face-detector revision override rejected: "
                    f"{repo_id} requested={requested!r} expected={pin['revision']}"
                )
            kwargs["revision"] = pin["revision"]

        resolved = pathlib.Path(
            original_download(repo_id, filename, *args, **kwargs)
        ).expanduser().resolve()

        if pin is not None:
            if filename != "model.safetensors":
                raise RuntimeError(
                    f"Unexpected pinned anime-face model file: {repo_id}/{filename}"
                )
            if not resolved.is_file() or resolved.stat().st_size <= 0:
                raise RuntimeError(
                    f"anime-face-detector model is missing or empty: {resolved}"
                )
            actual = _sha256_file(resolved)
            if actual != pin["sha256"]:
                raise RuntimeError(
                    "anime-face-detector model SHA256 mismatch: "
                    f"{repo_id} expected={pin['sha256']} got={actual}"
                )
        return str(resolved)

    detector_module.hf_hub_download = pinned_download
    try:
        return anime_face_detector.create_detector("yolov3")
    finally:
        detector_module.hf_hub_download = original_download


class AnimeFaceDetector:
    """anime-face-detector 래퍼. bbox와 28개 랜드마크를 반환합니다."""

    def __init__(self):
        # anime-face-detector가 설치된 경우에만 임포트
        try:
            import anime_face_detector  # noqa: F401
            self._detector = _create_pinned_anime_face_detector()
        except ImportError:
            self._detector = None

    def detect(self, image_path: str) -> Dict[str, Any]:
        """
        이미지에서 애니메이션 얼굴을 감지합니다.
        Returns: {"bbox": [x1,y1,x2,y2], "landmarks": [[x,y]*28], "score": float}
        """
        if self._detector is None:
            raise ImportError("anime-face-detector가 설치되지 않았습니다. pip install anime-face-detector")
        if not NUMPY_AVAILABLE:
            raise ImportError("numpy가 설치되지 않았습니다. pip install numpy")
        if not PIL_AVAILABLE:
            raise ImportError("Pillow가 설치되지 않았습니다. pip install Pillow")
        
        # Upstream anime-face-detector consumes OpenCV-style BGR arrays.
        rgb = np.array(PILImage.open(image_path).convert("RGB"))
        bgr = np.ascontiguousarray(rgb[..., ::-1])
        preds = self._detector(bgr)
        if len(preds) == 0:
            raise ValueError(f"얼굴을 감지하지 못했습니다: {image_path}")

        # Use the highest-confidence face instead of relying on detector order.
        pred = max(preds, key=lambda item: float(item["bbox"][4]))
        bbox_raw = np.asarray(pred["bbox"], dtype=float)
        keypoints = np.asarray(pred.get("keypoints"), dtype=float)

        if bbox_raw.shape[0] < 5 or not np.all(np.isfinite(bbox_raw[:5])):
            raise ValueError("anime-face-detector returned an invalid bbox")
        if (
            keypoints.ndim != 2
            or keypoints.shape[0] < 28
            or keypoints.shape[1] < 3
            or not np.all(np.isfinite(keypoints[:28, :3]))
        ):
            raise ValueError(
                "anime-face-detector returned fewer than 28 scored landmarks"
            )

        return {
            "bbox": bbox_raw[:4].astype(float).tolist(),
            "landmarks": keypoints[:28, :2].astype(float).tolist(),
            "landmark_scores": keypoints[:28, 2].astype(float).tolist(),
            "score": float(bbox_raw[4]),
        }

    def detect_and_save(self, image_path: str, output_json: str) -> dict:
        """감지 결과를 JSON 파일로 저장합니다."""
        from vtuber_pipeline.core.utils import save_json
        result = self.detect(image_path)
        save_json(result, output_json)
        return result
