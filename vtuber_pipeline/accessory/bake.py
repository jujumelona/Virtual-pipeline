"""Static accessory baking into a base VRM/GLB container."""

import pathlib
from typing import Dict, Any, List, Optional


def find_bone_node_index(gltf, bone_name: str) -> Optional[int]:
    """Find one skeleton node by exact name first, then conservative substring."""
    for i, node in enumerate(gltf.nodes or []):
        if node.name and node.name.lower() == bone_name.lower():
            return i
    for i, node in enumerate(gltf.nodes or []):
        if node.name and bone_name.lower() in node.name.lower():
            return i
    return None


def _remap_material_textures(material_dict: Dict[str, Any], texture_offset: int) -> None:
    pbr = material_dict.get("pbrMetallicRoughness") or {}
    for key in ("baseColorTexture", "metallicRoughnessTexture"):
        info = pbr.get(key)
        if isinstance(info, dict) and info.get("index") is not None:
            info["index"] += texture_offset
    for key in ("normalTexture", "occlusionTexture", "emissiveTexture"):
        info = material_dict.get(key)
        if isinstance(info, dict) and info.get("index") is not None:
            info["index"] += texture_offset


def _root_node_indices(gltf) -> List[int]:
    child_indices = set()
    for node in gltf.nodes or []:
        child_indices.update(node.children or [])
    return [i for i in range(len(gltf.nodes or [])) if i not in child_indices]


def bake_accessories(
    base_vrm: str,
    accessory_paths: List[str],
    output_path: str,
    attachment_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Merge unskinned accessory GLBs, parent roots to bones, and save a VRM.

    All glTF index spaces and binary buffer offsets used by static TripoSR
    accessories are remapped. Skinned accessories are rejected explicitly
    instead of being silently corrupted.
    """
    result: Dict[str, Any] = {
        "status": "pending",
        "base_vrm": base_vrm,
        "accessory_count": len(accessory_paths),
        "accessories": accessory_paths,
    }
    pathlib.Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    try:
        from pygltflib import (
            GLTF2, BufferView, Accessor, Mesh, Node, Image, Texture, Sampler, Material
        )

        base = GLTF2().load(base_vrm)
        if len(base.buffers or []) != 1 or base.binary_blob() is None:
            raise ValueError("Base VRM must contain exactly one embedded GLB buffer")
        binary = bytearray(base.binary_blob() or b"")
        attachment_data = attachment_config or {}
        merged: List[Dict[str, Any]] = []

        for i, acc_path in enumerate(accessory_paths):
            acc = GLTF2().load(acc_path)
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
                getattr(node, "skin", None) is not None for node in (acc.nodes or [])
            ):
                raise ValueError(
                    f"Skinned accessory is not supported by static bake: {acc_path}"
                )
            if acc.extensionsRequired:
                raise ValueError(
                    f"Accessory requires unsupported glTF extensions: {acc.extensionsRequired}"
                )
            if any(getattr(image, "uri", None) for image in (acc.images or [])):
                raise ValueError(
                    f"Accessory contains external image URIs; embedded GLB required: {acc_path}"
                )
            if any(
                getattr(primitive, "extensions", None)
                for mesh in (acc.meshes or [])
                for primitive in (mesh.primitives or [])
            ):
                raise ValueError(
                    f"Accessory primitive extensions are not remapped by static bake: {acc_path}"
                )
            if any(
                getattr(material, "extensions", None)
                for material in (acc.materials or [])
            ):
                raise ValueError(
                    f"Accessory material extensions are not remapped by static bake: {acc_path}"
                )

            acc_binary = acc.binary_blob() or b""
            acc_name = pathlib.Path(acc_path).stem
            cfg = attachment_data.get(acc_name, attachment_data.get(str(i), {}))

            node_offset = len(base.nodes or [])
            mesh_offset = len(base.meshes or [])
            material_offset = len(base.materials or [])
            accessor_offset = len(base.accessors or [])
            bv_offset = len(base.bufferViews or [])
            image_offset = len(base.images or [])
            texture_offset = len(base.textures or [])
            sampler_offset = len(base.samplers or [])
            while len(binary) % 4:
                binary.append(0)
            binary_offset = len(binary)

            # Buffer views and accessors.
            for bv in acc.bufferViews or []:
                data = bv.to_dict()
                data["buffer"] = 0
                data["byteOffset"] = int(data.get("byteOffset") or 0) + binary_offset
                base.bufferViews.append(BufferView(**data))
            for accessor in acc.accessors or []:
                data = accessor.to_dict()
                if data.get("bufferView") is not None:
                    data["bufferView"] += bv_offset
                sparse = data.get("sparse")
                if isinstance(sparse, dict):
                    if sparse.get("indices", {}).get("bufferView") is not None:
                        sparse["indices"]["bufferView"] += bv_offset
                    if sparse.get("values", {}).get("bufferView") is not None:
                        sparse["values"]["bufferView"] += bv_offset
                base.accessors.append(Accessor(**data))

            # Image/texture/material index spaces.
            for image in acc.images or []:
                data = image.to_dict()
                if data.get("bufferView") is not None:
                    data["bufferView"] += bv_offset
                base.images.append(Image(**data))
            for sampler in acc.samplers or []:
                base.samplers.append(Sampler(**sampler.to_dict()))
            for texture in acc.textures or []:
                data = texture.to_dict()
                if data.get("source") is not None:
                    data["source"] += image_offset
                if data.get("sampler") is not None:
                    data["sampler"] += sampler_offset
                base.textures.append(Texture(**data))
            for material in acc.materials or []:
                data = material.to_dict()
                _remap_material_textures(data, texture_offset)
                base.materials.append(Material(**data))

            # Mesh primitives.
            for mesh in acc.meshes or []:
                data = mesh.to_dict()
                for primitive in data.get("primitives", []):
                    if primitive.get("material") is not None:
                        primitive["material"] += material_offset
                    attrs = primitive.get("attributes") or {}
                    for key, value in list(attrs.items()):
                        if isinstance(value, int):
                            attrs[key] = value + accessor_offset
                    if primitive.get("indices") is not None:
                        primitive["indices"] += accessor_offset
                    for target in primitive.get("targets") or []:
                        for key, value in list(target.items()):
                            if isinstance(value, int):
                                target[key] = value + accessor_offset
                base.meshes.append(Mesh(**data))

            # Nodes and hierarchy.
            roots = _root_node_indices(acc)
            for node in acc.nodes or []:
                data = node.to_dict()
                if data.get("mesh") is not None:
                    data["mesh"] += mesh_offset
                if data.get("children"):
                    data["children"] = [child + node_offset for child in data["children"]]
                base.nodes.append(Node(**data))

            parent_bone = cfg.get("parent_bone", "head")
            parent_idx = find_bone_node_index(base, parent_bone)
            if parent_idx is None:
                raise ValueError(f"Parent bone not found in base VRM: {parent_bone}")

            parent_node = base.nodes[parent_idx]
            if parent_node.children is None:
                parent_node.children = []
            for root in roots:
                root_idx = node_offset + root
                root_node = base.nodes[root_idx]
                root_node.translation = list(cfg.get("translation", [0.0, 0.0, 0.0]))
                root_node.rotation = list(cfg.get("rotation", [0.0, 0.0, 0.0, 1.0]))
                root_node.scale = list(cfg.get("scale", [1.0, 1.0, 1.0]))
                if root_idx not in parent_node.children:
                    parent_node.children.append(root_idx)

            binary.extend(acc_binary)
            merged.append({
                "path": acc_path,
                "name": acc_name,
                "parent_bone": parent_bone,
                "parent_node_idx": parent_idx,
                "root_nodes": [node_offset + root for root in roots],
                "nodes_added": len(acc.nodes or []),
                "meshes_added": len(acc.meshes or []),
                "binary_size": len(acc_binary),
            })

        if base.buffers:
            base.buffers[0].byteLength = len(binary)
        base.set_binary_blob(bytes(binary))
        base.save_binary(output_path)

        out = pathlib.Path(output_path)
        if not out.is_file() or out.stat().st_size == 0:
            raise RuntimeError("Accessory bake did not produce a VRM file")
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
