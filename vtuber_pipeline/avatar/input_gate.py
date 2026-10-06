"""Input validation and face detection quality checks for VTuber Pipeline.

This module provides the validate_input function for checking image quality
and detecting faces before processing through the pipeline.
"""

import hashlib
import pathlib
from typing import Dict, Any


def validate_input(image_path: str, output_dir: str) -> Dict[str, Any]:
    """Validate input image and detect face quality metrics.
    
    Performs the following checks:
    1. Image decodes correctly with PIL
    2. Minimum resolution 256x256
    3. Aspect ratio between 0.5 and 2.0
    4. Face detection with anime-face-detector (stub if not installed)
    5. Face confidence > 0.5
    6. Face area ratio between 0.05 and 0.8
    7. All 28 landmarks detected with confidence (stub)
    8. Face symmetry check (stub)
    9. Yaw proxy < 30 degrees (stub)
    10. Head bbox not touching frame edges
    
    Args:
        image_path: Path to the input image.
        output_dir: Directory to write quality.json.
        
    Returns:
        Dictionary with quality check results and pass/fail status.
    """
    result = {
        "image_path": image_path,
        "valid": False,
        "checks": {},
        "errors": []
    }
    
    # Check 1: Image decodes with PIL
    try:
        from PIL import Image
        with Image.open(image_path) as img:
            img.verify()
        
        # Re-open to get dimensions (verify closes the file)
        with Image.open(image_path) as img:
            width, height = img.size
            result["width"] = width
            result["height"] = height
            result["checks"]["image_decodes"] = True
    except Exception as e:
        result["checks"]["image_decodes"] = False
        result["errors"].append(f"Failed to decode image: {e}")
        _write_quality_json(output_dir, result)
        return result
    
    # Check 2: Minimum resolution 256x256
    result["checks"]["min_resolution"] = width >= 256 and height >= 256
    if not result["checks"]["min_resolution"]:
        result["errors"].append(f"Resolution {width}x{height} below minimum 256x256")
    
    # Check 3: Aspect ratio 0.5-2.0
    aspect_ratio = width / height if height > 0 else 0
    result["aspect_ratio"] = aspect_ratio
    result["checks"]["aspect_ratio"] = 0.5 <= aspect_ratio <= 2.0
    if not result["checks"]["aspect_ratio"]:
        result["errors"].append(f"Aspect ratio {aspect_ratio:.2f} outside range [0.5, 2.0]")
    
    # Stub checks for face detection (require anime-face-detector)
    # These are stubbed when the detector is not available
    try:
        import numpy as np
        from PIL import Image as PILImage
        
        # Try to import anime-face-detector
        try:
            import anime_face_detector
            detector = anime_face_detector.create_detector('yolov3')
            
            img = np.array(PILImage.open(image_path).convert('RGB'))
            preds = detector(img)
            
            if len(preds) > 0:
                pred = preds[0]
                bbox = pred['bbox'][:4].tolist()
                score = float(pred['bbox'][4])
                landmarks = pred.get('keypoints', [])[:28]
                
                result["checks"]["face_detected"] = True
                result["checks"]["confidence"] = score > 0.5
                result["confidence"] = score
                
                # Face area ratio
                face_area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
                image_area = width * height
                face_area_ratio = face_area / image_area if image_area > 0 else 0
                result["checks"]["face_area_ratio"] = 0.05 <= face_area_ratio <= 0.8
                result["face_area_ratio"] = face_area_ratio
                
                # Landmark check (stub for quality)
                result["checks"]["landmark_confidence"] = len(landmarks) >= 28
                result["landmark_count"] = len(landmarks)
                
                # Symmetry check (stub: always pass)
                result["checks"]["face_symmetry"] = True
                
                # Yaw proxy (stub: always pass)
                result["checks"]["yaw_proxy"] = True
                result["yaw_degrees"] = 0.0
                
                # Head bbox frame contact
                margin = 10
                touches_frame = (
                    bbox[0] < margin or
                    bbox[1] < margin or
                    bbox[2] > width - margin or
                    bbox[3] > height - margin
                )
                result["checks"]["head_bbox_frame_contact"] = not touches_frame
                
                result["bbox"] = bbox
                result["landmarks"] = landmarks
            else:
                result["checks"]["face_detected"] = False
                result["errors"].append("No face detected in image")
        except ImportError:
            # Stub all face detection checks
            result["checks"]["face_detected"] = True
            result["checks"]["confidence"] = True
            result["checks"]["face_area_ratio"] = True
            result["checks"]["landmark_confidence"] = True
            result["checks"]["face_symmetry"] = True
            result["checks"]["yaw_proxy"] = True
            result["checks"]["head_bbox_frame_contact"] = True
            result["warnings"] = ["anime-face-detector not installed, using stub values"]
            
    except ImportError:
        result["errors"].append("numpy or PIL not available")
    
    # Determine overall pass/fail
    result["pass"] = all(result["checks"].values())
    result["valid"] = result["pass"]
    
    # Compute input hash
    result["input_hash"] = _compute_file_hash(image_path)
    
    # Write quality.json
    _write_quality_json(output_dir, result)
    
    return result


def _compute_file_hash(path: str) -> str:
    """Compute SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def _write_quality_json(output_dir: str, result: Dict[str, Any]) -> None:
    """Write quality.json to output directory."""
    from vtuber_pipeline.core.utils import save_json
    
    pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)
    output_path = pathlib.Path(output_dir) / "quality.json"
    save_json(result, str(output_path))
