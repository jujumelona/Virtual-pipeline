"""T4-compatible Blender native bone-heat skin enhancement.

Explicit provider. Keep authoritative canonical geometry, humanoid/eye/hair
nodes, texture, UV and all glTF metadata; accept only validated body weights.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess

import numpy as np
from pygltflib import GLTF2

from vtuber_pipeline.avatar.skintokens_bridge import _read, graft_weights


def _joint_palette(gltf: GLTF2) -> list[str]:
    if len(gltf.skins or []) != 1 or not gltf.skins[0].joints:
        raise ValueError("No canonical skin palette")
    names = [gltf.nodes[i].name for i in gltf.skins[0].joints]
    if any(not n for n in names) or len(set(names)) != len(names):
        raise ValueError("Invalid canonical joint names")
    return names


def _neck_height(gltf: GLTF2) -> float:
    nodes = gltf.nodes or []
    names = _joint_palette(gltf)
    if "neck" not in names:
        raise ValueError("Canonical neck joint missing")
    index = gltf.skins[0].joints[names.index("neck")]
    parents = {}
    for n, node in enumerate(nodes):
        for child in node.children or []:
            if child in parents:
                raise ValueError("Canonical glTF is not a joint tree")
            parents[child] = n
    y = 0.
    visited = set()
    while index is not None:
        if index in visited:
            raise ValueError("Canonical joint hierarchy has a cycle")
        visited.add(index)
        y += float((nodes[index].translation or [0., 0., 0.])[1])
        index = parents.get(index)
    return y


def _inject_skin(base: GLTF2, joints: np.ndarray, weights: np.ndarray,
                 candidate_path: Path) -> None:
    attr = base.meshes[0].primitives[0].attributes
    binary = bytearray(base.binary_blob())
    for name, values, dtype, component_type in (
        ("JOINTS_0", joints, "<u2", 5123),
        ("WEIGHTS_0", weights, "<f4", 5126),
    ):
        index = getattr(attr, name)
        accessor = base.accessors[index]
        view = base.bufferViews[accessor.bufferView]
        if (view.buffer != 0 or view.byteStride is not None
                or accessor.componentType != component_type
                or accessor.type != "VEC4"):
            raise ValueError("Unexpected canonical GLB skin layout")
        data = np.asarray(values, dtype=dtype).tobytes()
        start = (view.byteOffset or 0) + (accessor.byteOffset or 0)
        if len(data) != accessor.count * 4 * np.dtype(dtype).itemsize:
            raise ValueError("Bone heat skin vertex count mismatch")
        if start + len(data) > len(binary):
            raise ValueError("Bone heat skin buffer outside GLB")
        binary[start:start + len(data)] = data
    base.set_binary_blob(bytes(binary))
    base.save_binary(str(candidate_path))


def graft_blender_weight_groups(baseline_file: str, weights_npz: str,
                               output_file: str) -> dict:
    """Translate native Blender groups into the original skin joint palette."""
    gltf = GLTF2().load_binary(str(baseline_file))
    if len(gltf.meshes or []) != 1 or len(gltf.meshes[0].primitives) != 1:
        raise ValueError("Expected one canonical avatar mesh")
    attrs = gltf.meshes[0].primitives[0].attributes
    vertices = _read(gltf, attrs.POSITION)
    canonical_names = _joint_palette(gltf)
    lookup = {name: i for i, name in enumerate(canonical_names)}
    old_joint = _read(gltf, attrs.JOINTS_0).astype(np.uint16)
    old_weight = _read(gltf, attrs.WEIGHTS_0).astype(np.float32)
    with np.load(weights_npz, allow_pickle=False) as record:
        group_names = [str(n) for n in record["group_names"].tolist()]
        groups = np.asarray(record["group_indices"])
        raw_weights = np.asarray(record["group_weights"], dtype=float)

    n = len(vertices)
    if (groups.shape != (n, 4) or raw_weights.shape != (n, 4)
            or not np.issubdtype(groups.dtype, np.integer)
            or len(set(group_names)) != len(group_names)
            or any(not name for name in group_names)):
        raise ValueError("Blender bone heat output shape or group names invalid")
    if (not np.isfinite(raw_weights).all() or (raw_weights < 0).any()
            or (raw_weights > 1.001).any()
            or (groups < -1).any()
            or (groups >= len(group_names)).any()):
        raise ValueError("Blender bone heat output references invalid weights/groups")

    extras = gltf.meshes[0].extras or {}
    hair_start = int(extras.get("hairVertexStart", n))
    if not 0 < hair_start <= n:
        raise ValueError("Canonical hair vertex boundary invalid")
    # Original eye/head skin and all physical hair strands must survive
    # unchanged. Only torso/limb skin below the neck is eligible for the
    # Blender heat solver.
    neck_y = _neck_height(gltf)
    eligible = np.arange(n) < hair_start
    eligible &= vertices[:, 1] < neck_y - 0.01
    if not np.any(eligible):
        raise ValueError("No torso/limb vertices eligible for bone heat skin")
    new_joint = old_joint.copy()
    new_weight = old_weight.copy()
    rejected = 0
    modified = 0
    for i in np.flatnonzero(eligible):
        contribution = {}
        for group, strength in zip(groups[i], raw_weights[i]):
            if group < 0 or strength <= 0:
                continue
            name = group_names[int(group)]
            if name not in lookup or name.startswith("hair"):
                continue
            joint = lookup[name]
            contribution[joint] = contribution.get(joint, 0.) + float(strength)
        if not contribution:
            rejected += 1
            continue
        top = sorted(contribution.items(), key=lambda x: x[1], reverse=True)[:4]
        total = sum(w for _, w in top)
        if not np.isfinite(total) or total <= 0:
            rejected += 1
            continue
        new_joint[i] = 0
        new_weight[i] = 0
        for slot, (joint, weight) in enumerate(top):
            new_joint[i, slot] = joint
            new_weight[i, slot] = weight / total
        if (not np.array_equal(new_joint[i], old_joint[i])
                or not np.allclose(new_weight[i], old_weight[i], atol=1e-4)):
            modified += 1

    eligible_count = int(eligible.sum())
    if rejected > max(1, int(.01 * eligible_count)):
        raise ValueError(f"Bone heat left {rejected}/{eligible_count} body vertices unweighted")
    if modified == 0:
        raise ValueError("Blender bone heat changed no canonical body skin weights")

    candidate = Path(output_file).with_name("blender_heat_candidate.glb")
    _inject_skin(gltf, new_joint, new_weight, candidate)
    result = graft_weights(baseline_file, str(candidate), output_file)
    result.update({"model": "Blender ARMATURE_AUTO", "body_vertices": eligible_count,
                   "changed_body_vertices": modified, "unweighted_body_vertices": rejected})
    return result


def run_blender_heat(baseline_file: str, output_dir: str,
                     *, timeout: int = 900) -> dict:
    blender = os.environ.get("VTUBER_BLENDER_BINARY") or shutil.which("blender")
    if not blender or not Path(blender).is_file():
        raise RuntimeError("Blender is not installed; run 3D Blender setup first")
    if not Path(baseline_file).is_file():
        raise FileNotFoundError(baseline_file)
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    npz = directory / "auto_skin_weights.npz"
    native_report = directory / "blender_bone_heat_report.json"
    logfile = directory / "blender_bone_heat.log"
    output = directory / "blender_heat_skin.glb"
    script = Path(__file__).resolve().parents[2] / "tools" / "blender_jobs" / "avatar_auto_weights.py"
    for old in (npz, native_report, output):
        old.unlink(missing_ok=True)
    with logfile.open("w", encoding="utf-8") as log:
        try:
            proc = subprocess.run(
                [str(blender), "--background", "--factory-startup", "--python",
                 str(script), "--", str(Path(baseline_file).resolve()),
                 str(npz.resolve()), str(native_report.resolve())],
                stdout=log, stderr=subprocess.STDOUT, timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"Blender heat skin timed out; log={logfile}") from exc
    if proc.returncode or not npz.is_file() or not native_report.is_file():
        raise RuntimeError(f"Blender automatic bone weights failed; log={logfile}")
    native = json.loads(native_report.read_text(encoding="utf-8"))
    if native.get("real_operator_passed") is not True:
        raise RuntimeError("Blender heat weight evidence missing")
    result = graft_blender_weight_groups(baseline_file, str(npz), str(output))
    result["log_path"] = str(logfile)
    result["native_report"] = str(native_report)
    report = directory / "validated_bone_heat_report.json"
    report.write_text(json.dumps(result, indent=2), encoding="utf-8")
    result["report_json"] = str(report)
    return result
