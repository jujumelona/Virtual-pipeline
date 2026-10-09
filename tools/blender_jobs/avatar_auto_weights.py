"""Blender-native automatic bone-heat skinning to a per-vertex artifact.

The official Blender glTF importer supplies the canonical armature. This
script exports *only* weighted vertex-group data by original vertex index.
It does not re-export the GLB or replace canonical VRM nodes or textures.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main():
    import bpy

    if "--" not in sys.argv:
        raise ValueError("Expected canonical GLB and output NPZ after --")
    args = sys.argv[sys.argv.index("--") + 1:]
    if len(args) != 3:
        raise ValueError("Expected GLB input, output NPZ and report JSON")
    source, weights_out, report_out = map(lambda p: str(Path(p).resolve()), args)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    imported = bpy.ops.import_scene.gltf(filepath=source)
    if "FINISHED" not in imported:
        raise RuntimeError("Blender failed to import canonical rigged glTF")
    meshes = [obj for obj in bpy.data.objects if obj.type == "MESH"]
    if len(meshes) != 1:
        raise RuntimeError(f"Expected one canonical mesh, imported {len(meshes)}")
    mesh = meshes[0]
    attached = [
        mod.object for mod in mesh.modifiers
        if mod.type == "ARMATURE" and mod.object is not None
    ]
    if len(attached) != 1:
        raise RuntimeError("Imported canonical mesh has no unique bound armature")
    arm = attached[0]
    if not arm.data.bones:
        raise RuntimeError("Imported armature has no bones")
    source_vertex_count = len(mesh.data.vertices)
    if source_vertex_count < 3:
        raise RuntimeError("Imported mesh has fewer than three vertices")

    # Do not let existing canonical weights mask the Blender heat-weight pass.
    for mod in list(mesh.modifiers):
        if mod.type == "ARMATURE":
            mesh.modifiers.remove(mod)
    for group in list(mesh.vertex_groups):
        mesh.vertex_groups.remove(group)
    # Preserve world transforms while changing the parenting relationship.
    original_world = mesh.matrix_world.copy()
    mesh.parent = None
    mesh.matrix_world = original_world
    bpy.ops.object.select_all(action="DESELECT")
    mesh.select_set(True)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    result = bpy.ops.object.parent_set(type="ARMATURE_AUTO", keep_transform=True)
    if "FINISHED" not in result:
        raise RuntimeError("Blender ARMATURE_AUTO heat binding failed")
    if len(mesh.data.vertices) != source_vertex_count:
        raise RuntimeError("Blender heat binding changed vertex count")

    import numpy as np
    names = [group.name for group in mesh.vertex_groups]
    group_indices = np.full((source_vertex_count, 4), -1, dtype=np.int32)
    group_weights = np.zeros((source_vertex_count, 4), dtype=np.float32)
    missing = 0
    for vertex in mesh.data.vertices:
        influences = sorted(
            [(int(group.group), float(group.weight)) for group in vertex.groups
             if group.weight > 0],
            key=lambda entry: entry[1], reverse=True,
        )[:4]
        if not influences:
            missing += 1
        for i, (index, weight) in enumerate(influences):
            group_indices[vertex.index, i] = index
            group_weights[vertex.index, i] = weight

    if missing == source_vertex_count:
        raise RuntimeError("Blender produced no bone heat skin weights")
    target = Path(weights_out)
    target.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        str(target),
        group_names=np.asarray(names, dtype="U128"),
        group_indices=group_indices,
        group_weights=group_weights,
    )
    Path(report_out).write_text(
        json.dumps({
            "engine": "Blender ARMATURE_AUTO",
            "blender_version": bpy.app.version_string,
            "source_vertex_count": source_vertex_count,
            "armature_bones": len(arm.data.bones),
            "weighted_vertices": source_vertex_count - missing,
            "unweighted_vertices": missing,
            "real_operator_passed": True,
        }, indent=2), encoding="utf-8",
    )


if __name__ == "__main__":
    main()
