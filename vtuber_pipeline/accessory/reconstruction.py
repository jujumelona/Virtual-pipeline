"""Batch accessory reconstruction through the same pinned TripoSR backend."""

import pathlib
from vtuber_pipeline.avatar.reconstruction import reconstruct_avatar


def reconstruct_accessories(
    image_paths: list[str],
    output_dir: str,
    profile: str = "commercial",
    *,
    model_save_format: str = "glb",
    remove_background: bool = True,
) -> list[dict]:
    """Reconstruct each accessory independently and return normalized contracts."""
    pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    for i, image_path in enumerate(image_paths):
        acc_out = str(pathlib.Path(output_dir) / f"accessory_{i:03d}")
        try:
            mesh = reconstruct_avatar(
                image_path,
                acc_out,
                profile=profile,
                model_save_format=model_save_format,
                remove_background=remove_background,
            )
            results.append({
                "status": "complete",
                "image": image_path,
                "mesh": mesh,
                "output_path": mesh,
                "model_options": {
                    "profile": profile,
                    "model_save_format": model_save_format,
                    "remove_background": remove_background,
                },
            })
        except Exception as exc:
            results.append({
                "status": "error",
                "image": image_path,
                "mesh": None,
                "error": str(exc),
            })
    return results
