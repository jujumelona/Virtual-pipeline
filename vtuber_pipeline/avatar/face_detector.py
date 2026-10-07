"""Anime face detection module for VTuber Pipeline."""

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


class AnimeFaceDetector:
    """anime-face-detector 래퍼. bbox와 28개 랜드마크를 반환합니다."""

    def __init__(self):
        # anime-face-detector가 설치된 경우에만 임포트
        try:
            import anime_face_detector
            self._detector = anime_face_detector.create_detector('yolov3')
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
        bbox = pred["bbox"][:4].tolist()
        landmarks = pred["keypoints"][:28].tolist() if "keypoints" in pred else []
        return {
            "bbox": bbox,
            "landmarks": landmarks,
            "score": float(pred["bbox"][4]),
        }

    def detect_and_save(self, image_path: str, output_json: str) -> dict:
        """감지 결과를 JSON 파일로 저장합니다."""
        from vtuber_pipeline.core.utils import save_json
        result = self.detect(image_path)
        save_json(result, output_json)
        return result
