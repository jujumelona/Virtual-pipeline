"""Independent, genuinely mesh-bound spring/damping specifications for secondary motion.

The previous physics document referenced physics.*.sway parameters that did
not exist in keyforms.json. That made every spring inert at the SDK handoff.
This step serializes positive/negative local vertex deformation endpoints
at each observed part's top pivot and binds each spring to a real parameter.
"""
from pathlib import Path
import json
import math

import numpy as np

PHYSICAL_CLASSES = ("hair", "sleeve", "ribbon", "earring", "accessory", "ornament")


def mesh_sway_keyforms(vertices_xy, pivot_xy, max_degrees):
    vertices = np.asarray(vertices_xy, dtype=np.float64)
    pivot = np.asarray(pivot_xy, dtype=np.float64)
    if (vertices.ndim != 2 or vertices.shape[1] != 2
            or len(vertices) < 3 or not np.isfinite(vertices).all()
            or pivot.shape != (2,) or not np.isfinite(pivot).all()):
        raise ValueError("Physical sway requires finite mesh vertices and pivot")
    offsets = vertices - pivot
    angle = math.radians(float(max_degrees))
    if not 0 < angle <= math.radians(35):
        raise ValueError("Unreasonable spring maximum angle")
    result = {}
    for name, theta in (("min", -angle), ("max", angle)):
        co, si = math.cos(theta), math.sin(theta)
        rotated = offsets @ np.array([[co, si], [-si, co]])
        result[name] = (rotated - offsets).tolist()
    result["default"] = np.zeros_like(offsets).tolist()
    return result


def build_physics(keyforms_json: str, parts_json: str, output_dir: str,
                  *, meshes_json: str | None = None) -> dict:
    data = json.loads(Path(parts_json).read_text(encoding="utf-8"))
    keyform_path = Path(keyforms_json)
    authored = json.loads(keyform_path.read_text(encoding="utf-8"))
    if not isinstance(authored.get("parameters"), dict) or not isinstance(authored.get("keyforms"), list):
        raise ValueError("Invalid keyform producer contract")
    mesh_by_name = {}
    if meshes_json:
        mesh_data = json.loads(Path(meshes_json).read_text(encoding="utf-8"))
        mesh_by_name = {item["semantic_id"]: item for item in mesh_data["meshes"]}
    entries = []
    keyform_by_name = {item["semantic_id"]: item for item in authored["keyforms"]}
    for part in data["parts"]:
        name = part["semantic_id"]
        if not any(kind in name for kind in PHYSICAL_CLASSES):
            continue
        if name not in mesh_by_name or name not in keyform_by_name:
            raise ValueError(f"{name}: cannot bind spring without an authored mesh/keyform")
        left, top, right, _bottom = part["bbox_xyxy"]
        pivot = [(float(left) + float(right)) / 2, float(top)]
        max_degrees = 14 if "hair" in name else 8
        parameter = "physics." + name + ".sway"
        if parameter in authored["parameters"]:
            raise ValueError(f"Duplicate physical parameter: {parameter}")
        authored["parameters"][parameter] = [-1.0, 0.0, 1.0]
        keyform_by_name[name].setdefault("deltas", {})[parameter] = mesh_sway_keyforms(
            mesh_by_name[name]["vertices_xy"], pivot, max_degrees,
        )
        entries.append({
            "semantic_id": name, "pivot_xy": pivot,
            "stiffness": 15.0 if "hair" in name else 25.0,
            "damping": 0.72, "max_degrees": max_degrees,
            "target_parameter": parameter,
            "deformation_keyforms_bound": True,
            "driver_range": [-1.0, 0.0, 1.0],
        })

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    # All downstream consumers receive the upgraded authored keyforms.
    keyform_path.write_text(json.dumps(authored, ensure_ascii=False, indent=2,
                                      allow_nan=False), encoding="utf-8")
    dest = output / "physics2d.json"
    dest.write_text(json.dumps({"springs": entries}, ensure_ascii=False, indent=2,
                               allow_nan=False), encoding="utf-8")
    return {"physics_json": str(dest), "keyforms_json": str(keyform_path)}
