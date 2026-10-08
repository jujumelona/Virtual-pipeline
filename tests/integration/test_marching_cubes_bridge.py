"""Real CPU mesh extraction contracts for the build-free TripoSR bridge."""

from __future__ import annotations

import sys
import types

import numpy as np
import pytest

from vtuber_pipeline.avatar.marching_cubes_backend import (
    install_triposr_marching_cubes,
    marching_cubes_numpy,
)


def _sphere_field() -> np.ndarray:
    z, y, x = np.mgrid[:15, :17, :21].astype(np.float32)
    return ((x - 11) / 5) ** 2 + ((y - 8) / 4) ** 2 + ((z - 6) / 3) ** 2


def test_bridge_runs_real_marching_cubes_with_torchmcubes_xyz_convention():
    from skimage.measure import marching_cubes as sk_marching_cubes

    field = _sphere_field()
    xyz, triangles = marching_cubes_numpy(field, 1.0)
    reference_zyx, reference_faces, _, _ = sk_marching_cubes(
        field, level=1.0, gradient_direction="descent",
        allow_degenerate=False, method="lewiner",
    )

    assert xyz.dtype == np.float32
    assert triangles.dtype == np.int64
    assert xyz.ndim == 2 and xyz.shape[1] == 3 and len(xyz) > 0
    assert triangles.ndim == 2 and triangles.shape[1] == 3 and len(triangles) > 0
    # TripoSR does v_pos[..., [2,1,0]]: this MUST recover the voxel ZYX axes.
    np.testing.assert_allclose(xyz[:, ::-1], reference_zyx)
    np.testing.assert_array_equal(triangles, reference_faces)
    assert triangles.min() >= 0 and triangles.max() < len(xyz)
    assert np.all(xyz >= 0)
    assert xyz[:, 0].max() < field.shape[2]
    assert xyz[:, 1].max() < field.shape[1]
    assert xyz[:, 2].max() < field.shape[0]


@pytest.mark.parametrize(
    "field,threshold",
    [
        (np.zeros((5, 5, 5), dtype=np.float32), 0.0),
        (np.full((4, 4, 4), np.nan, dtype=np.float32), 0.0),
        (np.ones((5, 5), dtype=np.float32), 0.5),
        (np.ones((1, 4, 4), dtype=np.float32), 0.5),
        (_sphere_field(), float("nan")),
    ],
)
def test_invalid_isosurface_fails_closed(field, threshold):
    with pytest.raises(ValueError):
        marching_cubes_numpy(field, threshold)


def test_scoped_torchmcubes_api_returns_original_tensor_device(monkeypatch):
    class FakeTensor:
        def __init__(self, value, device="cuda:0"):
            self._value = np.asarray(value)
            self.device = device

        def detach(self):
            return self

        def to(self, *args, **kwargs):
            device = kwargs.get("device", args[0] if args else self.device)
            return FakeTensor(self._value, device=device)

        def numpy(self):
            return self._value

    fake_torch = types.ModuleType("torch")
    fake_torch.float32 = np.float32
    fake_torch.from_numpy = lambda array: FakeTensor(array, device="cpu")
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.delitem(sys.modules, "torchmcubes", raising=False)
    install_triposr_marching_cubes()
    shim = sys.modules["torchmcubes"]
    install_triposr_marching_cubes()  # idempotent for the same bridge
    assert sys.modules["torchmcubes"] is shim
    assert shim._vtuber_scikit_image_bridge is True

    vertices, faces = shim.marching_cubes(FakeTensor(_sphere_field()), 1.0)
    assert vertices.device == faces.device == "cuda:0"
    assert vertices.numpy().dtype == np.float32
    assert faces.numpy().dtype == np.int64
    assert len(vertices.numpy()) > 0


def test_scoped_bridge_refuses_to_silently_override_a_real_native_import(monkeypatch):
    monkeypatch.setitem(sys.modules, "torchmcubes", types.ModuleType("torchmcubes"))
    with pytest.raises(RuntimeError, match="imported before"):
        install_triposr_marching_cubes()
