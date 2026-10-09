"""CPU-only integration checks for genuine registered multiview surface influence."""
import json
from pathlib import Path

import numpy as np
import trimesh

from vtuber_pipeline.avatar.surface_refine import refine_anatomy


def _run(tmp_path, confidence):
    base = trimesh.creation.icosphere(subdivisions=3)
    source = tmp_path / "fitted.glb"
    base.export(source)
    generated = base.copy()
    generated.vertices = np.asarray(generated.vertices) + [0.02, 0.0, 0.0]
    aligned = tmp_path / "aligned.glb"
    generated.export(aligned)
    # The downstream silhouette contract consumes a real local alpha image.
    # A fake nonexistent "source.png" can no longer model an observed input.
    from PIL import Image, ImageDraw
    source_png = tmp_path / "source.png"
    foreground = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
    ImageDraw.Draw(foreground).ellipse((12, 5, 115, 123),
                                      fill=(150, 100, 200, 255))
    foreground.save(source_png)
    references = tmp_path / "reference_quality.json"
    references.write_text(json.dumps({
        "images": {"front": {"path": str(source_png.resolve())}}
    }))
    constraints = tmp_path / "constraints.json"
    constraints.write_text(json.dumps({
        "contract": "vtuber-multiview-constraints-v1",
        "aligned_multiview_glb": str(aligned),
        "registration": {"confidence": confidence},
    }))
    result = refine_anatomy(str(source), str(constraints), str(references),
                            str(tmp_path / "result"))
    refined = trimesh.load(result["refined_glb"], force="mesh")
    report = json.loads(Path(result["report_json"]).read_text())
    return base, refined, report


def test_registered_multiview_changes_surface_without_changing_topology(tmp_path):
    base, refined, report = _run(tmp_path, 1.0)
    assert len(refined.vertices) == len(base.vertices)
    assert len(refined.faces) == len(base.faces)
    assert np.isfinite(refined.vertices).all()
    assert report["multiview_constrained_vertex_count"] > 0
    assert report["mean_multiview_correction_mesh_units"] > 0
    assert np.mean(refined.vertices[:, 0] - base.vertices[:, 0]) > 0


def test_zero_alignment_confidence_disables_unverified_geometry(tmp_path):
    _base, _refined, report = _run(tmp_path, 0.0)
    assert report["registered_multiview_confidence"] == 0.0
    assert report["mean_multiview_correction_mesh_units"] == 0.0
