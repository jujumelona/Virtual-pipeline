"""Anime face detection module for VTuber Pipeline."""

from typing import Dict, List, Any


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
        from PIL import Image as PILImage
        import numpy as np
        img = np.array(PILImage.open(image_path).convert('RGB'))
        preds = self._detector(img)
        if len(preds) == 0:
            raise ValueError(f"얼굴을 감지하지 못했습니다: {image_path}")
        pred = preds[0]  # 첫 번째 얼굴
        bbox = pred['bbox'][:4].tolist()
        landmarks = pred['keypoints'][:28].tolist() if 'keypoints' in pred else []
        return {"bbox": bbox, "landmarks": landmarks, "score": float(pred['bbox'][4])}

    def detect_and_save(self, image_path: str, output_json: str) -> dict:
        """감지 결과를 JSON 파일로 저장합니다."""
        from vtuber_pipeline.core.utils import save_json
        result = self.detect(image_path)
        save_json(result, output_json)
        return result
