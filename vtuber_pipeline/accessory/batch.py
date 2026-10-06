"""Batch accessory reconstruction module for VTuber Pipeline."""

import pathlib
from vtuber_pipeline.avatar.reconstruction import reconstruct_avatar


def batch_reconstruct_accessories(
    image_paths: list, output_dir: str, profile: str = "commercial"
) -> list:
    """여러 액세서리 이미지를 배치로 3D 재구성합니다.

    Args:
        image_paths: 액세서리 이미지 경로 리스트
        output_dir: 출력 디렉토리
        profile: 사용 프로필 (기본값: 'commercial')

    Returns:
        각 이미지에 대한 재구성 결과 리스트
    """
    pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)
    results = []
    for i, img_path in enumerate(image_paths):
        acc_out = str(pathlib.Path(output_dir) / f"accessory_{i:03d}")
        try:
            mesh = reconstruct_avatar(img_path, acc_out, profile=profile)
            results.append({"image": img_path, "mesh": mesh, "status": "ok"})
        except Exception as e:
            results.append({"image": img_path, "mesh": None, "status": str(e)})
    return results
