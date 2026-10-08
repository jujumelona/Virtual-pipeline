"""Headless Blender process: VRM Add-on import, deform audit, save, export."""
from __future__ import annotations
import json
import sys
from pathlib import Path


def main():
    import bpy
    if "--" not in sys.argv:
        raise ValueError("Pass source VRM, blend, target VRM and report paths after --")
    args = sys.argv[sys.argv.index("--") + 1:]
    if len(args) != 4:
        raise ValueError("Expected four explicit artifact paths")
    source, blend, target, report = map(lambda x: str(Path(x).resolve()), args)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    # Blender 4.2+ supports extensions; older installs expose io_scene_vrm.
    for name in ("bl_ext.user_default.vrm", "io_scene_vrm"):
        try:
            bpy.ops.preferences.addon_enable(module=name)
        except Exception:
            pass
    if not hasattr(bpy.ops.import_scene, "vrm"):
        raise RuntimeError("Official VRM Add-on importer was not registered")
    imported = bpy.ops.import_scene.vrm(filepath=source)
    if "FINISHED" not in imported:
        raise RuntimeError(f"VRM Add-on import failed: {imported}")
    armatures = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    if not armatures or not meshes:
        raise RuntimeError("Official VRM import lost armature/mesh objects")
    skinned = [
        obj for obj in meshes
        if obj.vertex_groups and any(
            m.type == "ARMATURE" and m.object in armatures
            for m in obj.modifiers
        )
    ]
    if not skinned:
        raise RuntimeError("Imported avatar is not actually skinned to an armature")
    # A named, but all-zero, Shape Key is not a functioning facial expression.
    animated_keys = 0
    for obj in meshes:
        if obj.data.shape_keys is None:
            continue
        blocks = list(obj.data.shape_keys.key_blocks)
        if len(blocks) < 2:
            continue
        basis = blocks[0]
        for block in blocks[1:]:
            if any((block.data[i].co - basis.data[i].co).length > 1e-7
                   for i in range(len(obj.data.vertices))):
                animated_keys += 1
    if animated_keys < 1:
        raise RuntimeError("No geometrically functional facial Shape Key survived import")
    bpy.ops.wm.save_as_mainfile(filepath=blend)
    if not Path(blend).is_file():
        raise RuntimeError("Blender failed to write the editable .blend project")
    exported = bpy.ops.export_scene.vrm(filepath=target)
    if "FINISHED" not in exported:
        raise RuntimeError(f"Official VRM Add-on export failed: {exported}")
    evidence = {
        "native_addon_export": True,
        "blender_version": bpy.app.version_string,
        "armature_count": len(armatures),
        "mesh_count": len(meshes),
        "skinned_mesh_count": len(skinned),
        "nonzero_shape_key_count": animated_keys,
        "rigged_skin": True,
        "nonempty_shape_keys": True,
    }
    Path(report).write_text(json.dumps(evidence, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
