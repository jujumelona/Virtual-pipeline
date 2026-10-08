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
    *,
    face_image_path: Optional[str] = None,
    back_image_path: Optional[str] = None,
    left_image_path: Optional[str] = None,
    right_image_path: Optional[str] = None,
    full_body: bool = False,
    texture_size: int = 1024,
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
    if type(texture_size) is not int or texture_size not in (1024, 2048):
        raise ValueError("texture_size must be 1024 or 2048")
    if full_body and not face_image_path:
        raise ValueError("full-body texture transfer needs an independent face reference")
    result = {
        "status": "pending",
        "image_path": image_path,
        "mesh_path": mesh_path
    }
    
    # Create output directory
    pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    try:
        from PIL import Image
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
        
        face_pixels = None
        face_width = face_height = 0
        if face_image_path:
            with Image.open(face_image_path) as face_img:
                face_rgba = face_img.convert("RGBA")
                face_width, face_height = face_rgba.size
                face_pixels = np.asarray(face_rgba)
        back_pixels = None
        back_width = back_height = 0
        if back_image_path:
            with Image.open(back_image_path) as back_img:
                back_rgba = back_img.convert("RGBA")
                back_width, back_height = back_rgba.size
                back_pixels = np.asarray(back_rgba)
        side_pixels = {}
        for role, path in (("left", left_image_path), ("right", right_image_path)):
            if path:
                with Image.open(path) as side_img:
                    side_pixels[role] = np.asarray(side_img.convert("RGBA"))
        result["reference_sources"] = {
            "front": image_path,
            "face": face_image_path,
            "back": back_image_path,
            "left": left_image_path,
            "right": right_image_path,
        }

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

            # Full-body texture coordinates must cover feet, torso, sleeves
            # and hair. Projecting every vertex through the *face* bounding
            # box (legacy behavior) paints much of the body from face pixels.
            if full_body:
                margin_x = src_width * 0.07
                margin_y = src_height * 0.045
                source_bbox = result.get("front_alpha_bbox")
                if source_bbox is None:
                    rgba_alpha = src_pixels[:, :, 3]
                    foreground = rgba_alpha > 32
                    if np.any(foreground) and np.any(~foreground):
                        yy, xx = np.nonzero(foreground)
                        source_bbox = (int(xx.min()), int(yy.min()),
                                       int(xx.max()) + 1, int(yy.max()) + 1)
                if source_bbox is not None:
                    lx, ty, rx, by = source_bbox
                    margin_x, margin_y = float(lx), float(ty)
                    frame_w = max(float(rx - lx), 1.)
                    frame_h = max(float(by - ty), 1.)
                    result["projection_mode"] = "full_body_alpha_bounds"
                else:
                    frame_w = src_width - 2 * margin_x
                    frame_h = src_height - 2 * margin_y
                    result["projection_mode"] = "full_body_canvas_bounds"
                cx = margin_x + frame_w / 2
                cy = margin_y + frame_h / 2
                scale_x = frame_w / max(float(pmax[0] - pmin[0]), 1e-8)
                scale_y = frame_h / mesh_height
                projected_image_xy = np.column_stack([
                    cx + (vertices[:, 0] - (pmin[0] + pmax[0])/2) * scale_x,
                    cy - (vertices[:, 1] - (pmin[1] + pmax[1])/2) * scale_y,
                ])
            else:
                projected_image_xy = np.column_stack([
                bbox_cx + (vertices[:, 0] - hcenter[0]) * scale_x,
                bbox_cy - (vertices[:, 1] - hcenter[1]) * scale_y,
                ])
            # Face texture uses a separate zoomed reference; pixels must be
            # projected with the face image's own landmark bbox.
            face_projected_xy = None
            if face_pixels is not None:
                fx1, fy1, fx2, fy2 = (
                    [float(x) for x in face_bbox[:4]]
                    if valid_bbox else [
                        face_width * .25, face_height * .20,
                        face_width * .75, face_height * .75,
                    ]
                )
                face_projected_xy = np.column_stack([
                    (fx1 + fx2) * .5 +
                    (vertices[:, 0] - hcenter[0]) * ((fx2 - fx1) / head_width),
                    (fy1 + fy2) * .5 -
                    (vertices[:, 1] - hcenter[1]) * ((fy2 - fy1) / head_height),
                ])
            back_projected_xy = None
            if back_pixels is not None:
                back_projected_xy = np.column_stack([
                    back_width * .5 - (vertices[:, 0] - (pmin[0]+pmax[0])*.5) /
                    max(float(pmax[0] - pmin[0]), 1e-8) * back_width*.86,
                    back_height*.5 - (vertices[:, 1] - (pmin[1]+pmax[1])*.5) /
                    mesh_height * back_height*.91,
                ])

            # Side orthographic projections come from independently supplied
            # real views. Local depth (Z) is horizontal from a side camera;
            # left/right views mirror that axis. Preserve source alpha margins.
            side_xy = {}
            for role, pixels in side_pixels.items():
                sh, sw = pixels.shape[:2]
                fg = pixels[:, :, 3] > 32
                if fg.any() and (~fg).any():
                    sy, sx = np.nonzero(fg)
                    lx, ty = float(sx.min()), float(sy.min())
                    rx, by = float(sx.max() + 1), float(sy.max() + 1)
                else:
                    lx, ty, rx, by = sw * .05, sh * .05, sw * .95, sh * .95
                center_z = float((pmin[2] + pmax[2]) * .5)
                center_y = float((pmin[1] + pmax[1]) * .5)
                depth_span = max(float(pmax[2] - pmin[2]), 1e-8)
                flip = 1.0 if role == "left" else -1.0
                side_xy[role] = np.column_stack([
                    (lx + rx) * .5 + flip * (vertices[:, 2] - center_z)
                    * ((rx - lx) / depth_span),
                    (ty + by) * .5 - (vertices[:, 1] - center_y)
                    * ((by - ty) / mesh_height),
                ])

            # Every occupied UV texel is projected independently (not a
            # triangle-center color fill). Unobserved areas stay transparent.
            from vtuber_pipeline.avatar.uv_projection import rasterize_multiview_texture
            texels, visibility = rasterize_multiview_texture(
                vertices, faces, uv_coords, src_pixels, projected_image_xy,
                texture_size, face_pixels=face_pixels,
                face_xy=face_projected_xy, back_pixels=back_pixels,
                back_xy=back_projected_xy,
                left_pixels=side_pixels.get("left"),
                left_xy=side_xy.get("left"),
                right_pixels=side_pixels.get("right"),
                right_xy=side_xy.get("right"),
            )
            if visibility["painted_texels"] == 0:
                raise RuntimeError("No visible source image pixels project onto the UV atlas")
            result["visibility"] = visibility
            texture = Image.fromarray(texels, mode="RGBA")

            # Save texture atlas
            texture_path = pathlib.Path(output_dir) / "texture_atlas.png"
            texture.save(texture_path)
            result["texture_atlas"] = str(texture_path)
            result["texture_size"] = [texture_size, texture_size]
            
            # Dedicated facial crop is saved for inspection and iteration.
            if face_image_path:
                face_source = Image.open(face_image_path).convert('RGBA')
            else:
                face_source = source_img
            width, height = face_source.size
            min_dim = min(width, height)
            left = (width - min_dim) // 2
            top = (height - min_dim) // 2
            face_crop = face_source.crop((left, top, left + min_dim, top + min_dim))
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
