"""Real D SDK 0.8.7 INP product acceptance; no model/GPU mocks.

Invoked only from the Inochi native GitHub workflow under a headless SDL2
OpenGL context after compiling the production exporter.
"""
from __future__ import annotations
import json
from io import BytesIO
import os
import struct
from pathlib import Path
import tempfile

from PIL import Image

from vtuber_pipeline.two_d.inochi_bridge import export_inp, inspect_native_inp
from vtuber_pipeline.common.completion import validate_build_result
from vtuber_pipeline.common.schemas import BuildResult


def main():
    native = os.getenv("VTUBER_INOCHI_NATIVE")
    if not native or not Path(native).is_file():
        raise RuntimeError("A real compiled native Inochi SDK exporter is mandatory")
    with tempfile.TemporaryDirectory(prefix="inochi-sdk-") as tmp:
        root = Path(tmp)
        source_png = root / "hair.png"
        artwork = Image.new("RGBA", (96, 96), (100, 60, 160, 255))
        # Deliberately retain RGB in transparent/partial-alpha source pixels.
        # Checking actual INP texture bytes catches missing or double premultiply.
        alpha_samples = {
            (24, 24): (100, 60, 160, 128),
            (48, 48): (100, 60, 160, 0),
            (72, 72): (100, 60, 160, 64),
            (36, 60): (100, 60, 160, 255),
        }
        for point, rgba in alpha_samples.items():
            artwork.putpixel(point, rgba)
        artwork.save(source_png)
        vertices = [[12, 12], [84, 12], [12, 84], [84, 84]]
        zeros = [[0.0, 0.0] for _ in vertices]
        model = {
            "schema": "vtuber-puppet-interchange-v1",
            "canvas": [96, 96],
            "textures": [str(source_png)],
            "parts": [{"semantic_id": "hair.front", "rgba_png": str(source_png),
                       "z_order": 1}],
            "mesh": [{
                "semantic_id": "hair.front",
                "rgba_png": str(source_png), "z_order": 1,
                "vertices_xy": vertices, "uv": [
                    [0.125, 0.125], [.875, .125], [.125, .875], [.875, .875]],
                "triangles": [[0, 1, 2], [2, 1, 3]],
            }],
            "parameters": {"physics.hair.front.sway": [-1.0, 0.0, 1.0]},
            "keyforms": [{
                "semantic_id": "hair.front",
                "deltas": {"physics.hair.front.sway": {
                    "min": [[-3.0, 0.0] for _ in vertices],
                    "default": zeros,
                    "max": [[3.0, 0.0] for _ in vertices],
                }},
            }],
            "physics": [{
                "semantic_id": "hair.front",
                "target_parameter": "physics.hair.front.sway",
                "stiffness": 15.0,
                "damping": .72,
            }],
            "draw_order": ["hair.front"],
        }
        spec = root / "puppet_spec.json"
        spec.write_text(json.dumps(model), encoding="utf-8")
        result = export_inp(str(spec), str(root))
        asset = Path(result["inp"])
        assert asset.stat().st_size > 128
        info = inspect_native_inp(str(asset))
        raw = asset.read_bytes()
        payload_size = struct.unpack_from(">I", raw, 8)[0]
        payload = json.loads(raw[12:12 + payload_size])
        texture_offset = 12 + payload_size
        assert raw[texture_offset:texture_offset + 8] == b"TEX_SECT"
        assert struct.unpack_from(">I", raw, texture_offset + 8)[0] == 1
        texture_offset += 12
        texture_size = struct.unpack_from(">I", raw, texture_offset)[0]
        texture_offset += 5  # Length plus official texture encoding byte.
        with Image.open(BytesIO(raw[texture_offset:texture_offset + texture_size])) as embedded:
            assert embedded.format == "TGA"  # SDK 0.8.7's native texture serializer.
            embedded_rgba = embedded.convert("RGBA")
            assert embedded_rgba.size == artwork.size
            for point, (red, green, blue, alpha) in alpha_samples.items():
                assert embedded_rgba.getpixel(point) == (
                    red * alpha // 255, green * alpha // 255,
                    blue * alpha // 255, alpha,
                ), f"Native INP texture has incorrect premultiplied alpha at {point}"

        def meshes(value):
            if isinstance(value, dict):
                if "verts" in value:
                    yield value
                for child in value.values():
                    yield from meshes(child)
            elif isinstance(value, list):
                for child in value:
                    yield from meshes(child)

        actual_meshes = list(meshes(payload["nodes"]))
        assert len(actual_meshes) == 1
        # SDK 0.8.7 camera/quad convention: centered coordinates, Y down.
        # Reading actual output catches a vertically mirrored native model.
        assert actual_meshes[0]["verts"] == [-36, -36, 36, -36, -36, 36, 36, 36]
        assert actual_meshes[0]["uvs"] == [.125, .125, .875, .125, .125, .875, .875, .875]
        assert info["format"] == "INP1"
        assert info["textures"] == 1
        assert info["part_count"] == 1
        assert info["physics_drivers"] >= 1
        validate_build_result(
            BuildResult("inochi2d", "complete", str(asset), str(spec), str(root))
        )
        print(json.dumps({
            "SDK_REAL_INP_NATIVE_COMPLETE": True,
            "size": asset.stat().st_size, "format": info["format"],
            "mesh_bindings": info["binding_count"],
            "physics": info["physics_drivers"],
            "premultiplied_texture_pixels_verified": True,
        }, indent=2), flush=True)


if __name__ == "__main__":
    main()
