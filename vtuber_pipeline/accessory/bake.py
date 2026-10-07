"""Static accessory baking into a base VRM/GLB container."""

import copy
import pathlib
from typing import Dict, Any, List, Optional


def _humanoid_node_map(gltf) -> Dict[str, int]:
    extensions = gltf.extensions or {}
    if not isinstance(extensions, dict):
        return {}
    vrm = extensions.get("VRMC_vrm") or {}
    humanoid = vrm.get("humanoid") if isinstance(vrm, dict) else None
    human_bones = (
        humanoid.get("humanBones")
        if isinstance(humanoid, dict)
        else None
    )
    if not isinstance(human_bones, dict):
        return {}

    node_count = len(gltf.nodes or [])
    result: Dict[str, int] = {}
    for semantic, binding in human_bones.items():
        node = binding.get("node") if isinstance(binding, dict) else None
        if isinstance(node, int) and 0 <= node < node_count:
            result[str(semantic)] = node
    return result


def find_bone_node_index(gltf, bone_name: str) -> Optional[int]:
    """Resolve VRM semantic humanoid name first, then exact raw node name."""
    semantic = _humanoid_node_map(gltf).get(bone_name)
    if semantic is not None:
        return semantic

    nodes = gltf.nodes or []
    for i, node in enumerate(nodes):
        if node.name == bone_name:
            return i

    lowered = bone_name.lower()
    matches = [
        i
        for i, node in enumerate(nodes)
        if node.name and node.name.lower() == lowered
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def _remap_texture_info(info, texture_offset: int) -> None:
    if info is not None and getattr(info, "index", None) is not None:
        info.index = int(info.index) + texture_offset


def _remap_material_textures(material, texture_offset: int) -> None:
    pbr = getattr(material, "pbrMetallicRoughness", None)
    if pbr is not None:
        _remap_texture_info(
            getattr(pbr, "baseColorTexture", None),
            texture_offset,
        )
        _remap_texture_info(
            getattr(pbr, "metallicRoughnessTexture", None),
            texture_offset,
        )
    _remap_texture_info(getattr(material, "normalTexture", None), texture_offset)
    _remap_texture_info(getattr(material, "occlusionTexture", None), texture_offset)
    _remap_texture_info(getattr(material, "emissiveTexture", None), texture_offset)


def _remap_attributes(attributes, accessor_offset: int) -> None:
    if attributes is None:
        return
    for name, value in vars(attributes).items():
        if isinstance(value, int) and not isinstance(value, bool):
            setattr(attributes, name, value + accessor_offset)


def _root_node_indices(gltf) -> List[int]:
    child_indices = set()
    for node in gltf.nodes or []:
        child_indices.update(int(child) for child in (node.children or []))
    return [
        i
        for i in range(len(gltf.nodes or []))
        if i not in child_indices
    ]


def _require_static_accessory_contract(acc, acc_path: str) -> None:
    """Reject glTF features whose internal references this static baker cannot remap."""
    if len(acc.buffers or []) != 1 or acc.binary_blob() is None:
        raise ValueError(
            f"Accessory must be a single-buffer binary GLB: {acc_path}"
        )
    if acc.animations:
        raise ValueError(
            f"Animated accessory is not supported by static bake: {acc_path}"
        )
    if acc.cameras:
        raise ValueError(
            f"Accessory cameras are not supported by static bake: {acc_path}"
        )
    if acc.skins or any(
        getattr(node, "skin", None) is not None
        for node in (acc.nodes or [])
    ):
        raise ValueError(
            f"Skinned accessory is not supported by static bake: {acc_path}"
        )
    if acc.extensionsRequired or acc.extensionsUsed or acc.extensions:
        raise ValueError(
            f"Accessory glTF extensions are not supported by static bake: {acc_path}"
        )
    if any(
        getattr(image, "uri", None)
        for image in (acc.images or [])
    ):
        raise ValueError(
            f"Accessory contains external image URIs; embedded GLB required: {acc_path}"
        )
    if any(
        getattr(node, "extensions", None)
        for node in (acc.nodes or [])
    ):
        raise ValueError(
            f"Accessory node extensions are not supported by static bake: {acc_path}"
        )
    if any(
        getattr(primitive, "extensions", None)
        for mesh in (acc.meshes or [])
        for primitive in (mesh.primitives or [])
    ):
        raise ValueError(
            f"Accessory primitive extensions are not supported by static bake: {acc_path}"
        )
    if any(
        getattr(material, "extensions", None)
        for material in (acc.materials or [])
    ):
        raise ValueError(
            f"Accessory material extensions are not supported by static bake: {acc_path}"
        )


def _ensure_base_lists(base) -> None:
    for name in (
        "bufferViews",
        "accessors",
        "images",
        "samplers",
        "textures",
        "materials",
        "meshes",
        "nodes",
    ):
        if getattr(base, name, None) is None:
            setattr(base, name, [])


def bake_accessories(
    base_vrm: str,
    accessory_paths: List[str],
    output_path: str,
    attachment_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Merge static accessory GLBs, parent roots to bones, and save one VRM.

    Typed pygltflib objects are deep-copied and remapped in-place. This avoids
    silently replacing nested Primitive/Attributes/Sparse objects with plain
    dictionaries during serialization.
    """
    result: Dict[str, Any] = {
        "status": "pending",
        "base_vrm": base_vrm,
        "accessory_count": len(accessory_paths),
        "accessories": accessory_paths,
    }
    pathlib.Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    try:
        from pygltflib import GLTF2
        from pygltflib.validator import validate as validate_gltf

        base = GLTF2().load(base_vrm)
        if len(base.buffers or []) != 1 or base.binary_blob() is None:
            raise ValueError(
                "Base VRM must contain exactly one embedded GLB buffer"
            )
        validate_gltf(base)
        _ensure_base_lists(base)

        binary = bytearray(base.binary_blob() or b"")
        attachment_data = attachment_config or {}
        merged: List[Dict[str, Any]] = []

        for i, acc_path in enumerate(accessory_paths):
            acc = GLTF2().load(acc_path)
            validate_gltf(acc)
            _require_static_accessory_contract(acc, acc_path)

            roots = _root_node_indices(acc)
            if not roots:
                raise ValueError(
                    f"Accessory has no root node and may contain a cycle: {acc_path}"
                )

            acc_binary = acc.binary_blob() or b""
            acc_name = pathlib.Path(acc_path).stem
            cfg = attachment_data.get(
                acc_name,
                attachment_data.get(str(i), {}),
            )
            if not isinstance(cfg, dict):
                raise ValueError(
                    f"Attachment configuration must be an object: {acc_name}"
                )

            node_offset = len(base.nodes)
            mesh_offset = len(base.meshes)
            material_offset = len(base.materials)
            accessor_offset = len(base.accessors)
            bv_offset = len(base.bufferViews)
            image_offset = len(base.images)
            texture_offset = len(base.textures)
            sampler_offset = len(base.samplers)

            while len(binary) % 4:
                binary.append(0)
            binary_offset = len(binary)

            # Buffer views and accessors.
            for source in acc.bufferViews or []:
                item = copy.deepcopy(source)
                item.buffer = 0
                item.byteOffset = int(item.byteOffset or 0) + binary_offset
                base.bufferViews.append(item)

            for source in acc.accessors or []:
                item = copy.deepcopy(source)
                if item.bufferView is not None:
                    item.bufferView = int(item.bufferView) + bv_offset
                if item.sparse is not None:
                    if (
                        item.sparse.indices is not None
                        and item.sparse.indices.bufferView is not None
                    ):
                        item.sparse.indices.bufferView = (
                            int(item.sparse.indices.bufferView) + bv_offset
                        )
                    if (
                        item.sparse.values is not None
                        and item.sparse.values.bufferView is not None
                    ):
                        item.sparse.values.bufferView = (
                            int(item.sparse.values.bufferView) + bv_offset
                        )
                base.accessors.append(item)

            # Embedded images, samplers, textures and materials.
            for source in acc.images or []:
                item = copy.deepcopy(source)
                if item.bufferView is not None:
                    item.bufferView = int(item.bufferView) + bv_offset
                base.images.append(item)

            for source in acc.samplers or []:
                base.samplers.append(copy.deepcopy(source))

            for source in acc.textures or []:
                item = copy.deepcopy(source)
                if item.source is not None:
                    item.source = int(item.source) + image_offset
                if item.sampler is not None:
                    item.sampler = int(item.sampler) + sampler_offset
                base.textures.append(item)

            for source in acc.materials or []:
                item = copy.deepcopy(source)
                _remap_material_textures(item, texture_offset)
                base.materials.append(item)

            # Mesh primitive index spaces.
            for source in acc.meshes or []:
                item = copy.deepcopy(source)
                for primitive in item.primitives or []:
                    if primitive.material is not None:
                        primitive.material = (
                            int(primitive.material) + material_offset
                        )
                    _remap_attributes(
                        primitive.attributes,
                        accessor_offset,
                    )
                    if primitive.indices is not None:
                        primitive.indices = (
                            int(primitive.indices) + accessor_offset
                        )
                    for target in primitive.targets or []:
                        _remap_attributes(target, accessor_offset)
                base.meshes.append(item)

            # Node hierarchy.
            for source in acc.nodes or []:
                item = copy.deepcopy(source)
                if item.mesh is not None:
                    item.mesh = int(item.mesh) + mesh_offset
                if item.children:
                    item.children = [
                        int(child) + node_offset
                        for child in item.children
                    ]
                base.nodes.append(item)

            parent_bone = str(cfg.get("parent_bone", "head"))
            parent_idx = find_bone_node_index(base, parent_bone)
            if parent_idx is None:
                raise ValueError(
                    f"Parent bone/node not found in base VRM: {parent_bone}"
                )

            translation = list(
                cfg.get("translation", [0.0, 0.0, 0.0])
            )
            rotation = list(
                cfg.get("rotation", [0.0, 0.0, 0.0, 1.0])
            )
            scale = list(cfg.get("scale", [1.0, 1.0, 1.0]))
            if len(translation) != 3 or len(rotation) != 4 or len(scale) != 3:
                raise ValueError(
                    f"Invalid attachment transform for {acc_name}"
                )

            parent_node = base.nodes[parent_idx]
            if parent_node.children is None:
                parent_node.children = []

            for root in roots:
                root_idx = node_offset + root
                root_node = base.nodes[root_idx]
                root_node.translation = [float(v) for v in translation]
                root_node.rotation = [float(v) for v in rotation]
                root_node.scale = [float(v) for v in scale]
                if root_idx not in parent_node.children:
                    parent_node.children.append(root_idx)

            binary.extend(acc_binary)
            merged.append({
                "path": acc_path,
                "name": acc_name,
                "parent_bone": parent_bone,
                "parent_node_idx": parent_idx,
                "root_nodes": [
                    node_offset + root
                    for root in roots
                ],
                "nodes_added": len(acc.nodes or []),
                "meshes_added": len(acc.meshes or []),
                "binary_size": len(acc_binary),
            })

        base.buffers[0].byteLength = len(binary)
        base.set_binary_blob(bytes(binary))
        validate_gltf(base)
        base.save_binary(output_path)

        out = pathlib.Path(output_path)
        if not out.is_file() or out.stat().st_size == 0:
            raise RuntimeError("Accessory bake did not produce a VRM file")

        # Fresh parse catches serialization-only failures.
        reloaded = GLTF2().load(str(out))
        validate_gltf(reloaded)

        result.update({
            "status": "complete",
            "output_path": output_path,
            "merged_accessories": merged,
            "final_binary_size": len(binary),
        })
    except Exception as exc:
        result["status"] = "error"
        result["error"] = str(exc)

    return result
