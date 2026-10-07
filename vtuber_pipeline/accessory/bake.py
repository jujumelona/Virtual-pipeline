"""Accessory baking module for VTuber Pipeline.

This module provides functions for baking selected accessories into
a base VRM file.
"""

import pathlib
from typing import Dict, Any, List, Optional


def bake_accessories(
    base_vrm: str,
    accessory_paths: List[str],
    output_path: str,
    attachment_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Bake selected accessories into base VRM.
    
    Full pygltflib merge:
    1. Load base VRM and get binary_blob()
    2. For each accessory: load GLB, get binary_blob(), compute offsets
    3. Remap all index references in bufferViews, accessors, meshes, nodes
    4. Append remapped nodes/meshes/materials/accessors/bufferViews to base
    5. Concatenate binary blobs
    6. Call base.set_binary_blob(merged_binary)
    7. Save with base.save_binary(output_path)
    
    Args:
        base_vrm: Path to the base VRM file.
        accessory_paths: List of paths to fitted accessory files.
        output_path: Path to save the combined VRM.
        attachment_config: Optional attachment configuration with transforms.
        
    Returns:
        Dictionary with bake results.
    """
    result = {
        "status": "pending",
        "base_vrm": base_vrm,
        "accessory_count": len(accessory_paths),
        "accessories": accessory_paths
    }
    
    pathlib.Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    try:
        from pygltflib import GLTF2
        import json
        
        # 1. Load base VRM and get binary blob
        base_gltf = GLTF2().load(base_vrm)
        base_binary = bytearray(base_gltf.binary_blob())
        
        result["base_nodes"] = len(base_gltf.nodes) if base_gltf.nodes else 0
        result["base_meshes"] = len(base_gltf.meshes) if base_gltf.meshes else 0
        result["base_binary_size"] = len(base_binary)
        
        # 2. Load attachment config if provided
        attachment_data = {}
        if attachment_config:
            attachment_data = attachment_config
        else:
            # Try to load from attachment.json
            attachment_path = pathlib.Path(output_path).parent / "attachment.json"
            if attachment_path.exists():
                with open(attachment_path, 'r') as f:
                    attachment_data = json.load(f)
        
        # 3. Process each accessory with proper binary merge and index remapping
        merged_accessories = []
        
        for i, acc_path in enumerate(accessory_paths):
            try:
                acc_gltf = GLTF2().load(acc_path)
                acc_binary = acc_gltf.binary_blob()
                
                # Get transform from attachment config
                acc_name = pathlib.Path(acc_path).stem
                transform = attachment_data.get(acc_name, attachment_data.get(str(i), {}))
                
                # Calculate offsets for index remapping
                node_offset = len(base_gltf.nodes) if base_gltf.nodes else 0
                mesh_offset = len(base_gltf.meshes) if base_gltf.meshes else 0
                material_offset = len(base_gltf.materials) if base_gltf.materials else 0
                accessor_offset = len(base_gltf.accessors) if base_gltf.accessors else 0
                buffer_view_offset = len(base_gltf.bufferViews) if base_gltf.bufferViews else 0
                buffer_offset = len(base_binary)
                
                # Remap and copy buffer views with updated byteOffset
                for bv in acc_gltf.bufferViews:
                    new_bv_dict = bv.to_dict() if hasattr(bv, 'to_dict') else {}
                    
                    # Update byteOffset to account for base binary
                    if 'byteOffset' in new_bv_dict:
                        new_bv_dict['byteOffset'] = new_bv_dict.get('byteOffset', 0) + buffer_offset
                    else:
                        new_bv_dict['byteOffset'] = buffer_offset
                    
                    # Create new BufferView object
                    from pygltflib import BufferView
                    new_bv = BufferView(**new_bv_dict)
                    base_gltf.bufferViews.append(new_bv)
                
                # Remap and copy accessors with updated bufferView indices
                for acc in acc_gltf.accessors:
                    new_acc_dict = acc.to_dict() if hasattr(acc, 'to_dict') else {}
                    
                    # Remap bufferView index
                    if 'bufferView' in new_acc_dict and new_acc_dict['bufferView'] is not None:
                        new_acc_dict['bufferView'] += buffer_view_offset
                    
                    # Remap sparse accessor indices if present
                    if 'sparse' in new_acc_dict:
                        sparse = new_acc_dict['sparse']
                        if 'indices' in sparse and 'bufferView' in sparse['indices']:
                            sparse['indices']['bufferView'] += buffer_view_offset
                        if 'values' in sparse and 'bufferView' in sparse['values']:
                            sparse['values']['bufferView'] += buffer_view_offset
                    
                    # Create new Accessor object
                    from pygltflib import Accessor
                    new_acc = Accessor(**new_acc_dict)
                    base_gltf.accessors.append(new_acc)
                
                # Remap and copy meshes
                for mesh in acc_gltf.meshes:
                    new_mesh_dict = mesh.to_dict() if hasattr(mesh, 'to_dict') else {}
                    
                    # Remap primitive material and accessor indices
                    if 'primitives' in new_mesh_dict:
                        for prim in new_mesh_dict['primitives']:
                            if 'material' in prim and prim['material'] is not None:
                                prim['material'] += material_offset
                            # Remap accessor indices in attributes
                            if 'attributes' in prim:
                                attrs = prim['attributes']
                                for attr_name in ['POSITION', 'NORMAL', 'TANGENT', 'TEXCOORD_0', 'TEXCOORD_1', 'COLOR_0', 'JOINTS_0', 'WEIGHTS_0']:
                                    if attr_name in attrs and attrs[attr_name] is not None:
                                        attrs[attr_name] += accessor_offset
                            # Remap indices accessor
                            if 'indices' in prim and prim['indices'] is not None:
                                prim['indices'] += accessor_offset
                    
                    # Create new Mesh object
                    from pygltflib import Mesh
                    new_mesh = Mesh(**new_mesh_dict)
                    base_gltf.meshes.append(new_mesh)
                
                # Copy materials (no index remapping needed, just append)
                if acc_gltf.materials:
                    for mat in acc_gltf.materials:
                        base_gltf.materials.append(mat)
                
                # Remap and copy nodes
                for node in acc_gltf.nodes:
                    new_node_dict = node.to_dict() if hasattr(node, 'to_dict') else {}
                    
                    # Remap mesh index
                    if 'mesh' in new_node_dict and new_node_dict['mesh'] is not None:
                        new_node_dict['mesh'] += mesh_offset
                    
                    # Remap skin index
                    if 'skin' in new_node_dict and new_node_dict['skin'] is not None:
                        # Skin remap would go here if we're merging skins
                        pass
                    
                    # Remap children indices
                    if 'children' in new_node_dict and new_node_dict['children']:
                        new_node_dict['children'] = [c + node_offset for c in new_node_dict['children']]
                    
                    # Create new Node object
                    from pygltflib import Node
                    new_node = Node(**new_node_dict)
                    base_gltf.nodes.append(new_node)
                
                # Apply transform to root accessory node and parent to bone
                # The root node of the accessory is at node_offset (first node added for this accessory)
                root_node_idx = node_offset
                if root_node_idx < len(base_gltf.nodes):
                    root_node = base_gltf.nodes[root_node_idx]
                    
                    # Apply transform from attachment config
                    if 'translation' in transform:
                        root_node.translation = transform['translation']
                    if 'rotation' in transform:
                        root_node.rotation = transform['rotation']
                    if 'scale' in transform:
                        root_node.scale = transform['scale']
                    
                    # Parent to the appropriate bone (default: head)
                    parent_bone = attachment_data.get('parent_bone', 'head')
                    parent_node_idx = find_bone_node_index(base_gltf, parent_bone)
                    
                    if parent_node_idx is not None:
                        # Add root node as child of parent bone
                        parent_node = base_gltf.nodes[parent_node_idx]
                        if not parent_node.children:
                            parent_node.children = []
                        # Only add if not already a child
                        if root_node_idx not in parent_node.children:
                            parent_node.children.append(root_node_idx)
                        
                        merged_accessories[-1]["parented_to"] = parent_bone
                        merged_accessories[-1]["parent_node_idx"] = parent_node_idx
                
                # Append accessory binary to base binary
                base_binary.extend(acc_binary)
                
                merged_accessories.append({
                    "path": acc_path,
                    "name": acc_name,
                    "nodes_added": len(acc_gltf.nodes) if acc_gltf.nodes else 0,
                    "meshes_added": len(acc_gltf.meshes) if acc_gltf.meshes else 0,
                    "binary_size": len(acc_binary),
                    "remapped": True
                })
                
            except Exception as e:
                merged_accessories.append({
                    "path": acc_path,
                    "error": str(e)
                })
        
        result["merged_accessories"] = merged_accessories
        
        # 4. Update buffer size
        if base_gltf.buffers:
            base_gltf.buffers[0].byteLength = len(base_binary)
        
        # 5. Set merged binary blob and save
        base_gltf.set_binary_blob(bytes(base_binary))
        
        # Save as VRM
        base_gltf.save_binary(output_path)
        
        result["output_path"] = output_path
        result["final_nodes"] = len(base_gltf.nodes) if base_gltf.nodes else 0
        result["final_meshes"] = len(base_gltf.meshes) if base_gltf.meshes else 0
        result["final_binary_size"] = len(base_binary)
        result["status"] = "complete"
        
    except ImportError as e:
        result["status"] = "error"
        result["error"] = f"Missing dependency: {e}"
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
    
    return result


def merge_meshes(mesh_paths: List[str], output_path: str) -> Dict[str, Any]:
    """Merge multiple meshes into one.
    
    Args:
        mesh_paths: List of mesh file paths.
        output_path: Path to save the merged mesh.
        
    Returns:
        Dictionary with merge results.
    """
    result = {
        "status": "pending",
        "mesh_count": len(mesh_paths)
    }
    
    try:
        import trimesh
        
        meshes = []
        for path in mesh_paths:
            mesh = trimesh.load(path)
            if hasattr(mesh, 'vertices'):
                meshes.append(mesh)
        
        if meshes:
            combined = trimesh.util.concatenate(meshes)
            combined.export(output_path)
            result["output_path"] = output_path
            result["status"] = "complete"
        else:
            result["status"] = "error"
            result["error"] = "No valid meshes found"
            
    except ImportError:
        result["status"] = "stub"
        result["warning"] = "trimesh not installed"
    
    return result


def find_bone_node_index(gltf, bone_name: str) -> Optional[int]:
    """Find the node index for a bone by name.
    
    Searches through the gltf nodes to find a node matching the bone name.
    Common bone names: 'head', 'neck', 'spine', 'hips', 'leftHand', 'rightHand'
    
    Args:
        gltf: pygltflib GLTF2 object.
        bone_name: Name of the bone to find (e.g., 'head', 'neck').
        
    Returns:
        Node index if found, None otherwise.
    """
    if not gltf.nodes:
        return None
    
    # Direct name match
    for i, node in enumerate(gltf.nodes):
        if node.name and node.name.lower() == bone_name.lower():
            return i
    
    # Partial match (e.g., 'head' might be 'head_001' or 'J_Head')
    for i, node in enumerate(gltf.nodes):
        if node.name and bone_name.lower() in node.name.lower():
            return i
    
    return None
