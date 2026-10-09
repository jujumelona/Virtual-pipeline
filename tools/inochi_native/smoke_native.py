"""Run an actual D SDK -> INP -> SDK reimport, not a mocked file-header test."""
from __future__ import annotations
import json
import os
from pathlib import Path
import sys

from PIL import Image


def main() -> None:
    from vtuber_pipeline.two_d.inochi_bridge import export_inp, inspect_native_inp

    root = Path(sys.argv[1]).resolve()
    root.mkdir(parents=True, exist_ok=True)
    model = root / "observed_face.png"
    # Synthetic test artwork: no user image or generated inference claims.
    Image.new("RGBA", (64, 64), (180, 90, 175, 255)).save(model)
    vertices = [[8, 8], [54, 8], [8, 54], [54, 54]]
    uv = [[x / 64, y / 64] for x, y in vertices]
    triangles = [[0, 1, 2], [1, 3, 2]]
    mesh = {
        "semantic_id": "hair.front", "rgba_png": str(model),
        "z_order": 70, "vertices_xy": vertices, "uv": uv,
        "triangles": triangles,
    }
    zeros = [[0, 0]] * 4
    positive = [[1, 0], [1, 0], [2, 0], [2, 0]]
    negative = [[-1, 0], [-1, 0], [-2, 0], [-2, 0]]
    spec = {
        "schema": "vtuber-puppet-interchange-v1",
        "canvas": [64, 64],
        "textures": [str(model)],
        "parts": [{
            "semantic_id": "hair.front", "rgba_png": str(model),
            "z_order": 70, "bbox_xyxy": [8, 8, 54, 54],
        }],
        "mesh": [mesh],
        "parameters": {
            "head.angle_x": [-30, 0, 30],
            "physics.hair.front.sway": [-1, 0, 1],
        },
        "keyforms": [{
            "semantic_id": "hair.front",
            "deltas": {
                "head.angle_x": {
                    "min": negative, "default": zeros, "max": positive,
                },
                "physics.hair.front.sway": {
                    "min": negative, "default": zeros, "max": positive,
                },
            },
        }],
        "physics": [{
            "semantic_id": "hair.front",
            "target_parameter": "physics.hair.front.sway",
            "stiffness": 15., "damping": .72,
        }],
        "draw_order": ["hair.front"],
    }
    path = root / "puppet_spec.json"
    path.write_text(json.dumps(spec), encoding="utf-8")
    assert os.environ.get("VTUBER_INOCHI_NATIVE")
    result = export_inp(str(path), str(root / "result"))
    evidence = json.loads(Path(result["native_report"]).read_text())
    actual = inspect_native_inp(result["inp"])
    assert evidence["sdk_roundtrip_read"] is True
    assert evidence["sdk_reimport_binding_count"] >= 2
    assert actual["binding_count"] >= 2
    assert actual["physics_drivers"] >= 1
    assert actual["textures"] >= 1
    print("official native Inochi SDK write/read + deformation + physics: PASS")


if __name__ == "__main__":
    main()
