"""General utility functions for VTuber Pipeline."""

import hashlib
import json
import pathlib
from PIL import Image


def validate_image(path: str) -> bool:
    """Return True if the file exists and Pillow can open it."""
    try:
        Image.open(path).verify()
        return True
    except Exception:
        return False


def load_json(path: str) -> dict:
    """Load a JSON file.
    
    Args:
        path: Path to the JSON file.
        
    Returns:
        Dictionary containing the JSON data.
    """
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(data: dict, path: str) -> None:
    """Save data to a JSON file.
    
    Args:
        data: Dictionary to save as JSON.
        path: Path to the output JSON file.
    """
    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
