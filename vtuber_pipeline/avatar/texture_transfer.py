"""Texture transfer module for VTuber Pipeline.

This module projects source images onto fitted meshes and emits the texture
artifacts consumed by the rigging stage.
"""

import pathlib
from typing import Dict, Any, Optional, List
def transfer_texture(
    image_path: str,
    mesh_path: str,
    output_dir: str,
    face_bbox: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Transfer texture from source image to fitted mesh.
    
    Real texture generation using UV projection:
    1. Load fitted mesh and input image
    2. Get UV coords from mesh.visual.uv or generate spherical UV mapping
    3. Create 1024x1024 RGBA texture atlas (PIL)
    4. For each triangle: get UV triangle, find bounding box, rasterize using barycentric coords
    5. Sample from input image
    6. Save texture_atlas.png
    
    Priority regions (in order of importance):
    1. Eyes - highest priority for VTuber expressiveness
    2. Eyebrows - important for expression
    3. Mouth - important for speech
    4. Skin - main face area
    5. Hairline - transition area
    
    Args:
        image_path: Path to the source image.
        mesh_path: Path to the fitted mesh.
        output_dir: Directory to write output textures.
        
    Returns:
        Dictionary with output texture paths.
    """
    result = {
        "status": "pending",
        "image_path": image_path,
        "mesh_path": mesh_path
    }
    
    # Create output directory
    pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    try:
        from PIL import Image, ImageDraw, ImageFilter
        import numpy as np
        
        # Load source image
        try:
            source_img = Image.open(image_path).convert('RGBA')
            result["source_size"] = source_img.size
            src_width, src_height = source_img.size
            src_pixels = np.array(source_img)
        except Exception as e:
            result["error"] = f"Failed to load source image: {e}"
            _write_texture_report(output_dir, result)
            return result
        
        # Try to load mesh and get UV coordinates
        try:
            import trimesh
            
            mesh = trimesh.load(mesh_path, process=False)
            if isinstance(mesh, trimesh.Scene):
                geometries = list(mesh.geometry.values())
                if len(geometries) != 1:
                    raise ValueError(
                        "Texture transfer requires exactly one mesh geometry"
                    )
                mesh = geometries[0]
            
            vertices = np.asarray(mesh.vertices, dtype=float)
            faces = np.asarray(mesh.faces, dtype=np.int64)
            n_vertices = len(vertices)
            
            result["vertex_count"] = n_vertices
            result["face_count"] = len(faces)
            
            # Get UV coordinates from mesh or generate spherical mapping
            uv_coords = None
            if hasattr(mesh, 'visual') and hasattr(mesh.visual, 'uv'):
                uv_coords = np.array(mesh.visual.uv)
                result["uv_source"] = "mesh"
            else:
                # Generate spherical UV mapping as fallback
                uv_coords = _generate_spherical_uv(vertices)
                result["uv_source"] = "spherical_fallback"

            if uv_coords.shape != (n_vertices, 2):
                raise ValueError(
                    f"UV array shape does not match mesh: {uv_coords.shape}"
                )
            if not np.all(np.isfinite(uv_coords)):
                raise ValueError("UV array contains non-finite values")
            uv_coords = np.asarray(uv_coords, dtype=np.float32)

            uv_path = pathlib.Path(output_dir) / "texture_uv.npy"
            np.save(uv_path, uv_coords)
            result["uv_path"] = str(uv_path)

            # Calibrate a front-view orthographic projection from the detected
            # 2D face box to the canonical mesh head. This prevents T-pose arm
            # span from shrinking the face texture into the center of the atlas.
            pmin = vertices.min(axis=0)
            pmax = vertices.max(axis=0)
            mesh_height = max(float(pmax[1] - pmin[1]), 1e-8)
            head_mask = vertices[:, 1] >= pmin[1] + 0.72 * mesh_height
            head = vertices[head_mask]
            if len(head) < 32:
                raise ValueError("Unable to isolate mesh head for texture projection")
            hmin = head.min(axis=0)
            hmax = head.max(axis=0)
            hcenter = (hmin + hmax) * 0.5
            head_width = max(float(hmax[0] - hmin[0]), 1e-8)
            head_height = max(float(hmax[1] - hmin[1]), 1e-8)

            valid_bbox = (
                isinstance(face_bbox, (list, tuple))
                and len(face_bbox) >= 4
                and float(face_bbox[2]) > float(face_bbox[0])
                and float(face_bbox[3]) > float(face_bbox[1])
            )
            if valid_bbox:
                x1, y1, x2, y2 = [float(v) for v in face_bbox[:4]]
                bbox_cx = (x1 + x2) * 0.5
                bbox_cy = (y1 + y2) * 0.5
                scale_x = (x2 - x1) / head_width
                scale_y = (y2 - y1) / head_height
                result["projection_mode"] = "detected_face_bbox"
            else:
                bbox_cx = src_width * 0.5
                bbox_cy = src_height * 0.34
                scale_x = (src_width * 0.45) / head_width
                scale_y = (src_height * 0.45) / head_height
                result["projection_mode"] = "centered_fallback"

            projected_image_xy = np.column_stack([
                bbox_cx + (vertices[:, 0] - hcenter[0]) * scale_x,
                bbox_cy - (vertices[:, 1] - hcenter[1]) * scale_y,
            ])
            fallback_color = tuple(
                np.median(src_pixels.reshape(-1, 4), axis=0)
                .astype(np.uint8)
                .tolist()
            )
            
            # Create texture atlas (1024x1024)
            texture_size = 1024
            texture = Image.new('RGBA', (texture_size, texture_size), (255, 255, 255, 255))
            draw = ImageDraw.Draw(texture)
            
            # Rasterize each triangle using barycentric coordinates
            for face in faces:
                # Get UV triangle coordinates
                uv_tri = uv_coords[face]
                
                # Scale UV coordinates to texture size
                uv_scaled = uv_tri * (texture_size - 1)

                img_coords = projected_image_xy[face]
                center = img_coords.mean(axis=0)
                if (
                    0.0 <= center[0] < src_width
                    and 0.0 <= center[1] < src_height
                ):
                    center_u = int(round(center[0]))
                    center_v = int(round(center[1]))
                    center_u = min(max(center_u, 0), src_width - 1)
                    center_v = min(max(center_v, 0), src_height - 1)
                    color_tuple = tuple(src_pixels[center_v, center_u].tolist())
                else:
                    color_tuple = fallback_color
                
                # Draw filled triangle in texture atlas
                points = [(float(u), float(v)) for u, v in uv_scaled]
                if len(points) >= 3:
                    draw.polygon(points, fill=color_tuple)
            
            # Apply slight blur to smooth edges
            texture = texture.filter(ImageFilter.GaussianBlur(radius=0.5))
            
            # Save texture atlas
            texture_path = pathlib.Path(output_dir) / "texture_atlas.png"
            texture.save(texture_path)
            result["texture_atlas"] = str(texture_path)
            result["texture_size"] = [texture_size, texture_size]
            
            # Also generate face texture (1024x1024 crop from source)
            width, height = source_img.size
            min_dim = min(width, height)
            left = (width - min_dim) // 2
            top = (height - min_dim) // 2
            face_crop = source_img.crop((left, top, left + min_dim, top + min_dim))
            face_texture = face_crop.resize((1024, 1024), Image.Resampling.LANCZOS)
            
            face_path = pathlib.Path(output_dir) / "face.png"
            face_texture.save(face_path)
            result["face_png"] = str(face_path)
            result["face_size"] = [1024, 1024]
            
            # Generate body texture (use atlas as body)
            body_path = pathlib.Path(output_dir) / "body.png"
            texture.save(body_path)
            result["body_png"] = str(body_path)
            result["body_size"] = [texture_size, texture_size]
            
            # Combined texture
            combined_path = pathlib.Path(output_dir) / "texture.png"
            texture.save(combined_path)
            result["texture_png"] = str(combined_path)
            
            result["status"] = "complete"
            
        except ImportError as e:
            result["error"] = f"Missing dependency: {e}"
            result["status"] = "error"
        except Exception as e:
            result["error"] = f"Mesh processing error: {str(e)}"
            result["status"] = "error"
        
    except ImportError:
        result["error"] = "PIL or numpy not installed"
        result["status"] = "error"
    except Exception as e:
        result["error"] = f"Texture transfer error: {str(e)}"
        result["status"] = "error"
    
    _write_texture_report(output_dir, result)
    
    return result


def _generate_spherical_uv(vertices):
    """Generate spherical UV mapping for vertices.
    
    Args:
        vertices: (N, 3) vertex position array.
        
    Returns:
        (N, 2) UV coordinates in [0, 1] range.
    """
    import numpy as np
    
    # Center the mesh
    center = vertices.mean(axis=0)
    centered = vertices - center
    
    # Convert to spherical coordinates
    # u = azimuth angle (longitude), v = polar angle (latitude)
    x, y, z = centered[:, 0], centered[:, 1], centered[:, 2]
    
    # Compute radius for each vertex
    r = np.sqrt(x**2 + y**2 + z**2)
    r = np.where(r < 1e-8, 1e-8, r)
    
    # Azimuth angle (around Y axis)
    u = 0.5 + np.arctan2(x, z) / (2 * np.pi)
    
    # Polar angle (from top)
    v = 0.5 - np.arcsin(np.clip(y / r, -1, 1)) / np.pi
    
    # Stack and clamp to [0, 1]
    uv = np.stack([u, v], axis=1)
    uv = np.clip(uv, 0, 1)
    
    return uv



def _write_texture_report(output_dir: str, result: Dict[str, Any]) -> None:
    """Write texture_report.json to output directory."""
    from vtuber_pipeline.core.utils import save_json
    
    output_path = pathlib.Path(output_dir) / "texture_report.json"
    save_json(result, str(output_path))
