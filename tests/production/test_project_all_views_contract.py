"""An observed UV atlas must have exactly matching editable interchange files."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image


def test_native_projection_writes_matching_base_color_uv_and_materials(tmp_path):
    import trimesh
    from vtuber_pipeline.avatar.uv_projection import project_all_views

    photo = tmp_path / "original.png"
    Image.new("RGBA", (160, 256), (224, 128, 92, 255)).save(photo)
    mesh_path = tmp_path / "canonical.glb"
    mesh = trimesh.creation.icosphere(subdivisions=3)
    mesh.apply_scale([.45, 1, .35])
    mesh.export(mesh_path)
    report = tmp_path / "references.json"
    report.write_text(json.dumps({
        "status": "complete",
        "images": {"front": {"path": str(photo), "size": [160, 256]}},
    }))
    out = project_all_views(
        str(mesh_path), str(report), None, 1024,
        str(tmp_path / "render"), full_body=False,
        face_bbox=[35, 20, 125, 100],
    )
    assert out["status"] == "complete", out
    assert Path(out["base_color"]).read_bytes() == Path(out["texture_png"]).read_bytes()
    uv = json.loads(Path(out["uv_json"]).read_text())
    materials = json.loads(Path(out["materials_json"]).read_text())
    assert uv["vertex_count"] == len(mesh.vertices)
    assert len(uv["uv"]) == len(mesh.vertices)
    assert len(uv["triangles"]) == len(mesh.faces)
    assert materials["materials"][0]["baseColorTexture"] == "base_color.png"
    assert out["visibility"]["painted_texels"] > 0
    assert out["visibility"]["inferred_colors_are_observed"] is False


def test_project_all_views_rejects_fabricated_rear_reference(tmp_path, monkeypatch):
    from vtuber_pipeline.avatar.uv_projection import project_all_views

    front = tmp_path / "front.png"
    Image.new("RGBA", (64, 64), "white").save(front)
    rear = tmp_path / "unregistered-back.png"
    Image.new("RGBA", (64, 64), "black").save(rear)
    manifest = tmp_path / "references.json"
    manifest.write_text(json.dumps({
        "status": "complete",
        "images": {"front": {"path": str(front)}},
    }))
    with __import__("pytest").raises(ValueError, match="unobserved"):
        project_all_views(str(tmp_path / "unused.glb"), str(manifest), None, 1024,
                          str(tmp_path / "out"), back_image_path=str(rear))
