"""Accessory reconstruction module for VTuber Pipeline."""

import pathlib
from vtuber_pipeline.avatar.reconstruction import reconstruct_avatar


def reconstruct_accessories(image_paths: list, output_dir: str) -> list:
    """여러 액세서리 이미지를 배치로 3D 재구성합니다."""
    pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)
    results = []
    for i, img_path in enumerate(image_paths):
        acc_out = str(pathlib.Path(output_dir) / f'accessory_{i:03d}')
        try:
            mesh = reconstruct_avatar(img_path, acc_out, profile='commercial')
            results.append({'image': img_path, 'mesh': mesh, 'status': 'ok'})
        except Exception as e:
            results.append({'image': img_path, 'mesh': None, 'status': str(e)})
    return results
