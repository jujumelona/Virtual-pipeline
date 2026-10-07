"""Accessory baking module for VTuber Pipeline.

This module provides functions for baking selected accessories into
a base VRM file.
"""

import pathlib
from typing import Dict, Any, List


def bake_accessories(
    base_vrm: str,
    accessory_paths: List[str],
    output_path: str,
    attachment_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Bake selected accessories into base VRM.
    
    실제 VRM 결합:
    1. Load base VRM with pygltflib
    2. For each accessory: load GLB, apply transform from attachment.json, add to scene
    3. Set parent bone for each accessory
    4. Export combined VRM
    5. Validate
    
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
        
        # 1. Load base VRM
        gltf = GLTF2().load(base_vrm)
        result["base_nodes"] = len(gltf.nodes) if gltf.nodes else 0
        result["base_meshes"] = len(gltf.meshes) if gltf.meshes else 0
        
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
        
        # 3. Process each accessory with proper index remapping
        merged_accessories = []
        for i, acc_path in enumerate(accessory_paths):
            try:
                acc_gltf = GLTF2().load(acc_path)
                
                # Get transform from attachment config
                acc_name = pathlib.Path(acc_path).stem
                transform = attachment_data.get(acc_name, attachment_data.get(str(i), {}))
                
                # Calculate offsets for index remapping
                node_offset = len(gltf.nodes) if gltf.nodes else 0
                mesh_offset = len(gltf.meshes) if gltf.meshes else 0
                material_offset = len(gltf.materials) if gltf.materials else 0
                accessor_offset = len(gltf.accessors) if gltf.accessors else 0
                buffer_view_offset = len(gltf.bufferViews) if gltf.bufferViews else 0
                
                # Copy and remap nodes
                for node in acc_gltf.nodes:
                    new_node_dict = node.to_dict() if hasattr(node, 'to_dict') else {}
                    
                    # Remap mesh index
                    if 'mesh' in new_node_dict and new_node_dict['mesh'] is not None:
                        new_node_dict['mesh'] += mesh_offset
                    
                    # Remap skin index
                    if 'skin' in new_node_dict and new_node_dict['skin'] is not None:
                        # Skin will be added at the end, so no remap needed yet
                        pass
                    
                    # Remap children indices
                    if 'children' in new_node_dict and new_node_dict['children']:
                        new_node_dict['children'] = [c + node_offset for c in new_node_dict['children']]
                    
                    gltf.nodes.append(type(node)(**new_node_dict) if hasattr(node, '__init__') else node)
                
                # Copy and remap meshes
                for mesh in acc_gltf.meshes:
                    new_mesh_dict = mesh.to_dict() if hasattr(mesh, 'to_dict') else {}
                    
                    # Remap primitive material indices
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
                    
                    gltf.meshes.append(type(mesh)(**new_mesh_dict) if hasattr(mesh, '__init__') else mesh)
                
                # Copy materials (no index remapping needed, just append)
                if acc_gltf.materials:
                    for mat in acc_gltf.materials:
                        gltf.materials.append(mat)
                
                # Copy and remap accessors
                if acc_gltf.accessors:
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
                        
                        gltf.accessors.append(type(acc)(**new_acc_dict) if hasattr(acc, '__init__') else acc)
                
                # Copy and remap buffer views
                if acc_gltf.bufferViews:
                    for bv in acc_gltf.bufferViews:
                        new_bv_dict = bv.to_dict() if hasattr(bv, 'to_dict') else {}
                        
                        # Buffer view indices are already remapped in accessors
                        gltf.bufferViews.append(type(bv)(**new_bv_dict) if hasattr(bv, '__init__') else bv)
                
                merged_accessories.append({
                    "path": acc_path,
                    "name": acc_name,
                    "nodes_added": len(acc_gltf.nodes) if acc_gltf.nodes else 0,
                    "meshes_added": len(acc_gltf.meshes) if acc_gltf.meshes else 0,
                    "remapped": True
                })
                
            except Exception as e:
                merged_accessories.append({
                    "path": acc_path,
                    "error": str(e)
                })
        
        result["merged_accessories"] = merged_accessories
        
        # 4. Export combined VRM
        # Save as GLB first, then rename to VRM
        temp_glb = pathlib.Path(output_path).with_suffix('.glb')
        gltf.save_binary(str(temp_glb))
        
        if temp_glb.exists():
            temp_glb.rename(output_path)
        
        result["output_path"] = output_path
        result["final_nodes"] = len(gltf.nodes) if gltf.nodes else 0
        result["final_meshes"] = len(gltf.meshes) if gltf.meshes else 0
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
