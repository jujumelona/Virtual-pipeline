from ._worker import invoke
def detect_semantic_parts(image_path: str, face_landmarks_json: str, output_dir: str) -> dict:
    return invoke("florence", {"image_path": image_path, "landmarks_json": face_landmarks_json,
                               "output_dir": output_dir}, output_dir)
