"""Unit tests for deterministic input-gate logic."""

import pathlib

import pytest
from PIL import Image


def create_test_image(width: int, height: int, path: pathlib.Path) -> None:
    Image.new("RGB", (width, height), color="white").save(path)


class FakeDetector:
    score = 0.95
    landmark_score = 0.90

    def detect(self, image_path: str):
        with Image.open(image_path) as image:
            width, height = image.size
        cx = width * 0.5
        landmarks = []
        for index in range(28):
            side = -1.0 if index < 14 else 1.0
            y = height * (0.38 + 0.012 * (index % 14))
            landmarks.append([cx + side * width * 0.10, y])
        return {
            "bbox": [
                width * 0.25,
                height * 0.20,
                width * 0.75,
                height * 0.80,
            ],
            "landmarks": landmarks,
            "landmark_scores": [self.landmark_score] * 28,
            "score": self.score,
        }


@pytest.fixture(autouse=True)
def fake_detector(monkeypatch):
    import vtuber_pipeline.avatar.face_detector as detector_module

    monkeypatch.setattr(detector_module, "AnimeFaceDetector", FakeDetector)


def test_valid_256x256_image(tmp_path):
    from vtuber_pipeline.avatar.input_gate import validate_input

    image_path = tmp_path / "test.png"
    create_test_image(256, 256, image_path)

    result = validate_input(str(image_path), str(tmp_path))

    assert result["status"] == "complete", result
    assert result["valid"] is True
    assert result["checks"]["image_decodes"] is True
    assert result["checks"]["min_resolution"] is True
    assert result["checks"]["landmark_confidence"] is True
    assert result["landmark_count"] == 28
    assert result["landmark_score_median"] == pytest.approx(0.9)


def test_too_small_image_is_rejected(tmp_path):
    from vtuber_pipeline.avatar.input_gate import validate_input

    image_path = tmp_path / "small.png"
    create_test_image(128, 128, image_path)

    result = validate_input(str(image_path), str(tmp_path))

    assert result["checks"]["min_resolution"] is False
    assert result["valid"] is False
    assert result["status"] == "error"


def test_extreme_aspect_ratio_is_rejected(tmp_path):
    from vtuber_pipeline.avatar.input_gate import validate_input

    image_path = tmp_path / "wide.png"
    create_test_image(600, 200, image_path)

    result = validate_input(str(image_path), str(tmp_path))

    assert result["aspect_ratio"] == pytest.approx(3.0)
    assert result["checks"]["aspect_ratio"] is False
    assert result["valid"] is False


def test_low_landmark_confidence_is_rejected(tmp_path, monkeypatch):
    from vtuber_pipeline.avatar.input_gate import validate_input
    import vtuber_pipeline.avatar.face_detector as detector_module

    class LowConfidenceDetector(FakeDetector):
        landmark_score = 0.10

    monkeypatch.setattr(
        detector_module,
        "AnimeFaceDetector",
        LowConfidenceDetector,
    )

    image_path = tmp_path / "low-confidence.png"
    create_test_image(512, 512, image_path)

    result = validate_input(str(image_path), str(tmp_path))

    assert result["checks"]["landmark_confidence"] is False
    assert result["valid"] is False


def test_quality_json_and_sha_are_written(tmp_path):
    from vtuber_pipeline.avatar.input_gate import validate_input

    image_path = tmp_path / "test.png"
    create_test_image(512, 512, image_path)

    result = validate_input(str(image_path), str(tmp_path))

    quality_path = tmp_path / "quality.json"
    assert quality_path.is_file()
    assert len(result["input_hash"]) == 64
