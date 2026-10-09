"""Real CPU integration for the accessory geometry and GLB bake path."""

from __future__ import annotations

import pathlib

import numpy as np


def _write_base_vrm(path: pathlib.Path):
    import trimesh
    from pygltflib import GLTF2

    seed = path.with_suffix(".glb")
    trimesh.creation.box(extents=[0.4, 0.6, 0.3]).export(seed)

    gltf = GLTF2().load(str(seed))
    mesh_node = next(
        i
        for i, node in enumerate(gltf.nodes or [])
        if getattr(node, "mesh", None) is not None
    )
    gltf.nodes[mesh_node].name = "head"
    gltf.extensions = dict(gltf.extensions or {})
    gltf.extensions["VRMC_vrm"] = {
        "specVersion": "1.0",
        "humanoid": {
            "humanBones": {
                "head": {"node": mesh_node},
            }
        },
    }
    gltf.extensionsUsed = list(gltf.extensionsUsed or [])
    if "VRMC_vrm" not in gltf.extensionsUsed:
        gltf.extensionsUsed.append("VRMC_vrm")
    gltf.save_binary(str(path))
    assert path.is_file() and path.stat().st_size > 0
    return mesh_node


def _write_accessory(path: pathlib.Path):
    import trimesh

    mesh = trimesh.creation.icosphere(subdivisions=1, radius=0.08)
    colors = np.tile(
        np.asarray([[180, 90, 220, 255]], dtype=np.uint8),
        (len(mesh.vertices), 1),
    )
    mesh.visual.vertex_colors = colors
    mesh.export(path)
    assert path.is_file() and path.stat().st_size > 0


def test_real_cpu_accessory_geometry_chain_and_bake(tmp_path):
    from pygltflib import GLTF2
    from pygltflib.validator import validate as validate_gltf
    from vtuber_pipeline.core.gltf import load_gltf

    from vtuber_pipeline.accessory.anchors import generate_anchor_manifest
    from vtuber_pipeline.accessory.artifacts import (
        render_preview,
        write_attachment_manifest,
    )
    from vtuber_pipeline.accessory.bake import bake_accessories
    from vtuber_pipeline.accessory.collision import resolve_collision
    from vtuber_pipeline.accessory.fitting import fit_accessory
    from vtuber_pipeline.accessory.normalize import normalize_glb

    base_vrm = tmp_path / "base.vrm"
    source_glb = tmp_path / "source.glb"
    normalized_glb = tmp_path / "normalized.glb"
    output_vrm = tmp_path / "combined.vrm"

    base_head = _write_base_vrm(base_vrm)
    _write_accessory(source_glb)

    base_before = load_gltf(base_vrm)
    validate_gltf(base_before)

    normalized = normalize_glb(str(source_glb), str(normalized_glb))
    assert normalized["status"] == "complete", normalized
    assert normalized_glb.is_file()
    assert normalized["scale"] > 0.0

    anchors = generate_anchor_manifest(str(base_vrm), str(tmp_path / "anchor"))
    assert anchors["status"] == "complete", anchors
    head_top = next(
        item for item in anchors["anchors"] if item["name"] == "HEAD_TOP"
    )
    assert head_top["bone"] == "head"
    assert head_top["node_index"] == base_head
    assert head_top["target_size"] == 0.18
    assert len(head_top["world_to_local_linear"]) == 3

    fitted = fit_accessory(
        str(normalized_glb),
        "HEAD_TOP",
        anchors,
        str(tmp_path / "fit"),
    )
    assert fitted["status"] == "complete", fitted
    fitted_path = pathlib.Path(fitted["output_path"])
    assert fitted_path.is_file()
    assert fitted["parent_bone"] == "head"
    assert fitted["target_size"] == 0.18
    assert fitted["transform"]["translation"] == [0.0, 0.1, 0.0]

    collision = resolve_collision(
        str(fitted_path),
        str(base_vrm),
        world_transform=fitted["world_transform"],
        clearance=0.007,
    )
    assert collision["status"] == "complete", collision
    assert collision["clearance"] == 0.007
    assert len(collision["pushout_vector"]) == 3
    assert len(collision["corrected_world_translation"]) == 3
    assert np.all(np.isfinite(collision["pushout_vector"]))

    local_transform = dict(fitted["transform"])
    if collision["resolved"]:
        local_push = (
            np.asarray(fitted["world_to_local_linear"], dtype=float)
            @ np.asarray(collision["pushout_vector"], dtype=float)
        )
        local_transform["translation"] = (
            np.asarray(local_transform["translation"], dtype=float)
            + local_push
        ).tolist()

    attachment = write_attachment_manifest(
        str(fitted_path),
        "HEAD_TOP",
        {**fitted, "transform": local_transform},
        collision,
        str(tmp_path / "artifacts"),
    )
    assert attachment["status"] == "complete", attachment
    assert attachment["attachment"]["parent_bone"] == "head"
    assert attachment["attachment"]["transform"] == local_transform

    preview = render_preview(
        str(fitted_path),
        str(tmp_path / "artifacts"),
        size=192,
    )
    assert preview["status"] == "complete", preview
    assert pathlib.Path(preview["output_path"]).is_file()
    assert preview["rendered_face_count"] > 0

    accessory_before = load_gltf(fitted_path)
    validate_gltf(accessory_before)
    base_node_count = len(base_before.nodes or [])
    base_mesh_count = len(base_before.meshes or [])
    base_accessor_count = len(base_before.accessors or [])
    base_bv_count = len(base_before.bufferViews or [])

    bake = bake_accessories(
        str(base_vrm),
        [str(fitted_path)],
        str(output_vrm),
        attachment_config={
            fitted_path.stem: {
                **local_transform,
                "parent_bone": "head",
            }
        },
    )
    assert bake["status"] == "complete", bake
    assert output_vrm.is_file() and output_vrm.stat().st_size > 0

    merged = load_gltf(output_vrm)
    validate_gltf(merged)

    assert len(merged.nodes or []) == (
        base_node_count + len(accessory_before.nodes or [])
    )
    assert len(merged.meshes or []) == (
        base_mesh_count + len(accessory_before.meshes or [])
    )
    assert len(merged.accessors or []) == (
        base_accessor_count + len(accessory_before.accessors or [])
    )
    assert len(merged.bufferViews or []) == (
        base_bv_count + len(accessory_before.bufferViews or [])
    )

    merged_entry = bake["merged_accessories"][0]
    root_nodes = merged_entry["root_nodes"]
    assert root_nodes
    parent = merged.nodes[base_head]
    assert all(root in (parent.children or []) for root in root_nodes)

    for root in root_nodes:
        node = merged.nodes[root]
        assert node.translation == local_transform["translation"]
        assert node.rotation == local_transform["rotation"]
        assert node.scale == local_transform["scale"]

    # Accessory mesh and accessor index spaces must be shifted after the base
    # model, not left pointing into the base VRM's arrays.
    appended_mesh = merged.meshes[base_mesh_count]
    primitive = appended_mesh.primitives[0]
    position_accessor = primitive.attributes.POSITION
    assert position_accessor >= base_accessor_count
    if primitive.indices is not None:
        assert primitive.indices >= base_accessor_count

    appended_view = merged.bufferViews[base_bv_count]
    assert int(appended_view.byteOffset or 0) >= len(base_before.binary_blob() or b"")

    assert merged.extensions["VRMC_vrm"] == base_before.extensions["VRMC_vrm"]


def test_bake_preserves_preexisting_accessory_root_transforms(tmp_path):
    """The attachment transform must COMPOSE with a source GLB root TRS."""
    from pygltflib import GLTF2
    from pygltflib.validator import validate as validate_gltf
    from vtuber_pipeline.accessory.bake import (
        bake_accessories, _root_node_indices,
    )

    avatar = tmp_path / "base.vrm"
    raw_glb = tmp_path / "transformed.glb"
    combined = tmp_path / "merged.vrm"
    head = _write_base_vrm(avatar)
    _write_accessory(raw_glb)

    original = GLTF2().load(str(raw_glb))
    roots = _root_node_indices(original)
    assert roots
    source_root = roots[0]
    source_translation = [0.14, 0.03, -0.21]
    original.nodes[source_root].translation = source_translation
    original.save_binary(str(raw_glb))
    validate_gltf(GLTF2().load(str(raw_glb)))

    attachment_translation = [0.0, 0.2, 0.04]
    result = bake_accessories(
        str(avatar), [str(raw_glb)], str(combined),
        attachment_config={raw_glb.stem: {
            "parent_bone": "head",
            "translation": attachment_translation,
            "rotation": [0.0, 0.0, 0.0, 1.0],
            "scale": [1.0, 1.0, 1.0],
        }},
    )
    assert result["status"] == "complete", result
    from vtuber_pipeline.core.gltf import load_gltf
    output = load_gltf(combined)
    validate_gltf(output)
    root = result["merged_accessories"][0]["root_nodes"][0]
    wrapper = result["merged_accessories"][0]["attachment_wrapper_node"]
    assert isinstance(wrapper, int)
    assert wrapper in output.nodes[head].children
    assert root in output.nodes[wrapper].children
    assert output.nodes[wrapper].translation == attachment_translation
    assert output.nodes[root].translation == source_translation
