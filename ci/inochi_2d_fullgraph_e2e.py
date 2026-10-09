"""Unmocked CPU 2D producer chain -> official D SDK animated/physical INP.

The only synthetic data are the starting RGBA parts and face coordinates:
art layers, contour meshing, physically-bound vertex keyframes, PSD/ORA,
portable puppet spec, D SDK serialization, native SDK reimport and final
production validation all execute their real production implementations.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

import numpy as np
from PIL import Image, ImageDraw

from vtuber_pipeline.common.schemas import Part, PartsDocument, BuildResult
from vtuber_pipeline.two_d.layer_export import write_psd_and_ora
from vtuber_pipeline.two_d.mesh2d import generate_meshes
from vtuber_pipeline.two_d.keyforms import build_keyforms
from vtuber_pipeline.two_d.physics2d import build_physics
from vtuber_pipeline.two_d.rig_spec import build_puppet_spec
from vtuber_pipeline.two_d.inochi_bridge import export_inp, inspect_native_inp


def _source_parts(root: Path) -> PartsDocument:
    width, height = 256, 256
    observed = [
        ("hair.back", (55, 8, 201, 146), (35, 30, 65, 255)),
        ("body", (70, 136, 188, 253), (85, 110, 150, 255)),
        ("face", (68, 38, 186, 185), (235, 180, 155, 255)),
        ("eye.left.white", (84, 107, 115, 130), (240, 242, 250, 255)),
        ("eye.right.white", (142, 107, 173, 130), (240, 242, 250, 255)),
        ("mouth.inner", (109, 150, 143, 166), (85, 15, 60, 255)),
        ("hair.front", (56, 16, 201, 104), (70, 40, 80, 255)),
    ]
    parts = []
    for idx, (semantic_id, bounds, fill) in enumerate(observed):
        image = Image.new("RGBA", (width, height))
        draw = ImageDraw.Draw(image)
        draw.ellipse(bounds, fill=fill)
        arr = np.asarray(image)
        occupied = arr[:, :, 3] > 32
        ys, xs = np.nonzero(occupied)
        if not len(xs):
            raise RuntimeError(f"{semantic_id}: missing observed pixels")
        rgba = root / f"part_{idx:02d}.png"
        mask = root / f"mask_{idx:02d}.png"
        image.save(rgba)
        Image.fromarray((occupied * 255).astype("uint8"), "L").save(mask)
        landmarks = []
        if "eye" in semantic_id:
            landmarks = [[float((bounds[0] + bounds[2]) / 2),
                          float((bounds[1] + bounds[3]) / 2)]]
        parts.append(Part(
            semantic_id=semantic_id, rgba_png=str(rgba),
            mask_png=str(mask), hidden_fill_mask_png=None,
            bbox_xyxy=[int(xs.min()), int(ys.min()), int(xs.max()+1), int(ys.max()+1)],
            z_order=idx * 10, landmarks_xy=landmarks, source_stage="observed_fixture",
        ))
    return PartsDocument(width=width, height=height,
                         parts=parts, psd_path=None, ora_path="")


def run(root: Path) -> dict:
    if not os.environ.get("VTUBER_INOCHI_NATIVE"):
        raise RuntimeError("Official compiled Inochi D SDK is mandatory")
    root.mkdir(parents=True, exist_ok=True)
    parts = _source_parts(root)
    part_json = parts.write(str(root / "parts.json"))
    layers = write_psd_and_ora(parts, str(root))
    meshes = generate_meshes(part_json, str(root))
    observed_landmarks = root / "face_landmarks.json"
    observed_landmarks.write_text(json.dumps({
        "coordinate_space": "original_canvas",
        "landmarks": [[110 + (idx % 7)*4, 115 + (idx // 7)*4]
                      for idx in range(28)],
    }), encoding="utf-8")
    keyforms = build_keyforms(meshes["meshes_json"], part_json,
                              str(observed_landmarks), str(root))
    physics = build_physics(keyforms["keyforms_json"], part_json,
                            str(root), meshes_json=meshes["meshes_json"])
    spec_path = build_puppet_spec(part_json, meshes["meshes_json"],
                                  keyforms["keyforms_json"],
                                  physics["physics_json"], str(root),
                                  str(root / "puppet_spec.json"))
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    if not len(spec["physics"]) >= 2:
        raise RuntimeError("Actual physics producer failed to bind two independent hair layers")
    if not len(spec["mesh"]) >= 7:
        raise RuntimeError("Actual contour mesh producer lost observed layers")
    if not all(item["deltas"] for item in spec["keyforms"]):
        raise RuntimeError("Actual rigging keyforms are empty")
    native = export_inp(spec_path, str(root))
    inp = Path(native["inp"])
    report = inspect_native_inp(str(inp))
    if report["part_count"] < 7 or report["physics_drivers"] < 2 or report["binding_count"] < 3:
        raise RuntimeError("SDK lost real seven-part mesh / multi-spring binding")
    final = BuildResult("inochi2d", "complete", str(inp), layers["psd"], str(root))
    manifest = final.write(str(root))
    if not inp.is_file() or not Path(layers["ora"]).is_file() or not Path(manifest).is_file():
        raise RuntimeError("Inochi graph has no actual deliverable artifacts")
    print(json.dumps({
        "REAL_2D_LAYER_TO_NATIVE_INP": "PASS",
        "part_count": report["part_count"],
        "physics_drivers": report["physics_drivers"],
        "parameter_bindings": report["binding_count"],
        "psd_bytes": Path(layers["psd"]).stat().st_size,
        "ora_bytes": Path(layers["ora"]).stat().st_size,
        "inp_bytes": inp.stat().st_size,
    }, indent=2), flush=True)
    return {"inp": str(inp), "psd": layers["psd"], "ora": layers["ora"]}


def main():
    artifact = os.environ.get("VTUBER_REAL_2D_NATIVE_E2E_DIR")
    if artifact:
        run(Path(artifact).resolve())
    else:
        with tempfile.TemporaryDirectory(prefix="inochi-real-2d-") as tmp:
            run(Path(tmp))


if __name__ == "__main__":
    main()
