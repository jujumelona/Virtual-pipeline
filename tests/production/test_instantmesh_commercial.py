"""Commercial InstantMesh uses only synthetic TripoSR priors and official LRM."""
from pathlib import Path
import numpy as np
import pytest
import trimesh
from PIL import Image

from tools.model_workers.instantmesh_commercial import _render_coarse_views
from tools.model_workers.instantmesh_worker import infer


def test_triposr_mesh_renders_six_inferred_lrm_views(tmp_path):
    mesh = trimesh.creation.icosphere(subdivisions=2, radius=0.8)
    mesh.visual.vertex_colors = np.tile(
        np.array([[60, 120, 180, 255]], dtype=np.uint8), (len(mesh.vertices), 1)
    )
    prior = tmp_path / "prior.obj"
    mesh.export(prior)
    front = tmp_path / "front.png"
    Image.new("RGBA", (256, 256), (60, 120, 180, 255)).save(front)
    images = _render_coarse_views(str(prior), str(front))
    assert images.shape == (6, 320, 320, 3)
    assert images.dtype == np.uint8
    assert (images != 255).any()
    assert np.mean(np.abs(images[0].astype(float) - images[1])) > 0.01


def test_commercial_instantmesh_cannot_fall_back_to_nc_upstream(tmp_path, monkeypatch):
    monkeypatch.delenv("INSTANTMESH_DIR", raising=False)
    with pytest.raises(RuntimeError, match="Commercial LRM requires"):
        infer({"front_rgba": str(tmp_path / "front.png"),
               "output_dir": str(tmp_path / "out"),
               "commercial_usage": "corporation",
               "coarse_obj": str(tmp_path / "prior.obj")})
