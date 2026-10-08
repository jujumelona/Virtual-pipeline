"""Build-free marching cubes bridge for the pinned TripoSR model.

The pinned TripoSR imports only `marching_cubes` from torchmcubes. Its
native CUDA/PyTorch extension is not needed for this integration. Implement
that API with scikit-image's versioned wheel instead of compiling on Colab.

Contract: torchmcubes returns vertices in XYZ order for an input volume
indexed ZYX; TripoSR reverses them back in MarchingCubeHelper.forward.
"""

from __future__ import annotations

import sys
import types
from typing import Any

import numpy as np


def marching_cubes_numpy(
    volume: np.ndarray, threshold: float
) -> tuple[np.ndarray, np.ndarray]:
    """Return the same vertex coordinate order and dtypes as torchmcubes."""
    from skimage.measure import marching_cubes

    field = np.asarray(volume, dtype=np.float32)
    if field.ndim != 3 or min(field.shape) < 2:
        raise ValueError("marching_cubes requires a 3D field with at least 2 voxels per axis")
    if not np.isfinite(field).all() or not np.isfinite(threshold):
        raise ValueError("marching_cubes requires finite field values and threshold")
    low, high = float(field.min()), float(field.max())
    if not low < float(threshold) < high:
        raise ValueError(
            f"no isosurface at level {threshold}: scalar field range=[{low}, {high}]"
        )

    # scikit-image returns (z,y,x) for a ZYX volume; torchmcubes returns
    # (x,y,z). TripoSR itself reverses this order in isosurface.py.
    vertices_zyx, faces, _, _ = marching_cubes(
        field,
        level=float(threshold),
        gradient_direction="descent",
        allow_degenerate=False,
        method="lewiner",
    )
    return (
        np.ascontiguousarray(vertices_zyx[:, ::-1], dtype=np.float32),
        np.ascontiguousarray(faces, dtype=np.int64),
    )


def _marching_cubes_torch(volume: Any, threshold: float) -> tuple[Any, Any]:
    import torch

    # Mesh extraction runs on the CPU (no native torch/CUDA extension);
    # return tensors on the calling device as required by upstream TripoSR.
    vertices, faces = marching_cubes_numpy(
        volume.detach().to(device="cpu", dtype=torch.float32).numpy(),
        threshold,
    )
    return (
        torch.from_numpy(vertices).to(volume.device),
        torch.from_numpy(faces).to(volume.device),
    )


def install_triposr_marching_cubes() -> None:
    """Register the scoped torchmcubes API before importing pinned TripoSR.

    This is intentionally called only inside the isolated TripoSR subprocess.
    Do not change the pinned upstream checkout or affect the notebook process.
    """
    existing = sys.modules.get("torchmcubes")
    if existing is not None:
        if getattr(existing, "_vtuber_scikit_image_bridge", False):
            return
        raise RuntimeError(
            "torchmcubes was imported before the pinned TripoSR backend was installed"
        )

    module = types.ModuleType("torchmcubes")
    module.marching_cubes = _marching_cubes_torch
    module._vtuber_scikit_image_bridge = True
    sys.modules["torchmcubes"] = module
