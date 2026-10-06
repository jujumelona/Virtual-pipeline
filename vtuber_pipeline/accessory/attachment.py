"""Accessory attachment module for VTuber Pipeline."""

from enum import Enum
from vtuber_pipeline.core.utils import save_json


class AnchorType(str, Enum):
    HEAD_TOP = 'HEAD_TOP'
    FACE = 'FACE'
    LEFT_EAR = 'LEFT_EAR'
    RIGHT_EAR = 'RIGHT_EAR'
    NECK = 'NECK'
    CHEST = 'CHEST'
    BACK = 'BACK'
    LEFT_HAND = 'LEFT_HAND'
    RIGHT_HAND = 'RIGHT_HAND'
    HIPS = 'HIPS'
    CUSTOM = 'CUSTOM'


def generate_attachment_config(mesh_paths: list, output_path: str, anchor: AnchorType = AnchorType.HEAD_TOP) -> dict:
    """액세서리 메시 목록에서 attachment.json을 생성합니다."""
    import pathlib
    accessories = []
    for i, mesh_path in enumerate(mesh_paths):
        name = pathlib.Path(mesh_path).stem
        accessories.append({
            'id': name,
            'mesh': str(mesh_path),
            'anchor': anchor.value,
            'offset': {'x': 0.0, 'y': 0.0, 'z': 0.0},
            'rotation': {'x': 0.0, 'y': 0.0, 'z': 0.0},
            'scale': 1.0
        })
    config = {'version': '1.0', 'accessories': accessories}
    save_json(config, output_path)
    return config
