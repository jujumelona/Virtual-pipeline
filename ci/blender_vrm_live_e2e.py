"""Real Blender 4.2/VRM Add-on headless production integration test.

The source mesh is a CPU-generated neutral fixture, but texture projection,
skinning, facial morphs, gaze, spring physics, VRM serialization, official
Blender import/export, .blend writing, and final product validation are real.
"""
from __future__ import annotations
import json
from pathlib import Path
import tempfile
import numpy as np
import trimesh
from PIL import Image

from tools.setup_blender_runtime import ensure_blender_runtime
from vtuber_pipeline.avatar.texture_transfer import transfer_texture
from vtuber_pipeline.avatar.rigging import rig_avatar
from vtuber_pipeline.avatar.expressions import generate_expressions, validate_expressions
from vtuber_pipeline.avatar.gaze import configure_gaze
from vtuber_pipeline.avatar.springbone import generate_springbone_config
from vtuber_pipeline.avatar.vrm_export import export_vrm
from vtuber_pipeline.avatar.blender_bridge import export_blender_from_vrm
from vtuber_pipeline.avatar.validator import validate_vrm


def main():
    with tempfile.TemporaryDirectory(prefix="vrm-blender-real-") as directory:
        root = Path(directory)
        blender = ensure_blender_runtime(str(root / "blender"))
        assert Path(blender).is_file()
        neutral = trimesh.creation.icosphere(subdivisions=4)
        neutral.apply_scale([0.55, 1.0, .48])
        neutral.apply_translation([0.0, 1.0, 0.0])
        mesh_path = root / "fitted.glb"
        neutral.export(mesh_path)
        yy, xx = np.mgrid[:256, :256]
        rgba = np.zeros((256, 256, 4), dtype=np.uint8)
        rgba[..., 0] = 120 + xx // 4
        rgba[..., 1] = 60 + yy // 4
        rgba[..., 2] = 100 + (xx + yy) // 7
        rgba[..., 3] = 255
        png = root / "reference.png"
        Image.fromarray(rgba, "RGBA").save(png)
        transfer = transfer_texture(str(png), str(mesh_path),
                                    str(root / "texture"), texture_size=512)
        assert transfer["status"] == "complete", transfer
        rig = rig_avatar(str(mesh_path), str(root / "rigged.glb"),
                         texture_path=transfer["texture_png"],
                         uv_path=transfer["uv_path"])
        generated = generate_expressions(rig)
        assert generated["status"] == "complete", generated
        expressions = generated["expressions"]
        validated = validate_expressions(expressions, str(root / "expressions"))
        assert validated["pass"] is True, validated
        gaze = configure_gaze(rig, str(root / "gaze"))
        assert gaze["status"] == "complete", gaze
        springs = generate_springbone_config(rig, str(root / "spring"))
        assert springs["status"] == "complete", springs
        first = export_vrm(
            rig, str(root / "export"), expressions=expressions,
            commercial_usage="personalProfit", springbone_config=springs,
            gaze_config=gaze["config"],
        )
        assert first["status"] == "complete", first
        final = export_blender_from_vrm(first["vrm_path"], str(root / "final"))
        assert final["status"] == "complete", final
        report = validate_vrm(final["vrm_path"], str(root / "validation"),
                              product_contract=True)
        assert report.get("passed") is True, report
        assert Path(final["blend"]).read_bytes().startswith(b"BLENDER")
        assert Path(final["vrm_path"]).read_bytes().startswith(b"glTF")
        print(json.dumps({
            "REAL_BLENDER_NATIVE_VRM_E2E": "PASS",
            "blender": blender,
            "final_vrm_bytes": Path(final["vrm_path"]).stat().st_size,
            "editable_blend_bytes": Path(final["blend"]).stat().st_size,
        }, indent=2), flush=True)


if __name__ == "__main__":
    main()
