"""2D rig triangulation must preserve disconnected painted islands."""
import json

import cv2
import numpy as np
from PIL import Image

from vtuber_pipeline.two_d.mesh2d import generate_meshes, _triangle_coverage


def _run(mask, tmp_path):
    path = tmp_path / "mask.png"
    Image.fromarray(mask, "L").save(path)
    metadata = tmp_path / "parts.json"
    metadata.write_text(json.dumps({
        "width": mask.shape[1], "height": mask.shape[0],
        "parts": [{"semantic_id": "hair.front", "mask_png": str(path),
                   "rgba_png": str(path), "z_order": 70}],
    }))
    result = generate_meshes(str(metadata), str(tmp_path / "out"))
    return json.loads(open(result["meshes_json"]).read())["meshes"][0]


def test_all_separate_hair_strands_keep_mesh_triangles(tmp_path):
    image = np.zeros((256, 256), dtype=np.uint8)
    image[45:95, 30:80] = 255
    image[140:200, 170:230] = 255
    mesh = _run(image, tmp_path)
    assert mesh["connected_components"] == 2
    vertices = np.asarray(mesh["vertices_xy"])
    triangles = np.asarray(mesh["triangles"])
    assert (vertices[:, 0] < 100).any()
    assert (vertices[:, 0] > 150).any()
    assert len(triangles) > 2
    # No shared triangles between two disconnected components.
    for tri in triangles:
        region_x = vertices[tri, 0]
        assert not (region_x.min() < 100 and region_x.max() > 150)


def test_concave_hair_outline_never_bridges_empty_center(tmp_path):
    image = np.zeros((256, 256), dtype=np.uint8)
    image[30:190, 30:63] = 255
    image[30:65, 30:195] = 255
    image[155:190, 30:195] = 255
    mesh = _run(image, tmp_path)
    vertices = np.asarray(mesh["vertices_xy"])
    assert all(_triangle_coverage(image > 0, vertices[t], cv2) >= .92
               for t in mesh["triangles"])


def test_island_inside_foreground_hole_gets_its_own_mesh(tmp_path):
    """RETR_EXTERNAL on the whole mask loses the nested independent island."""
    image = np.zeros((256, 256), dtype=np.uint8)
    image[30:226, 30:226] = 255
    image[82:174, 82:174] = 0
    image[108:150, 108:150] = 255
    mesh = _run(image, tmp_path)
    assert mesh["connected_components"] == 2
    labels_count, labels = cv2.connectedComponents(np.uint8(image > 0), connectivity=8)
    assert labels_count == 3  # background, enclosing ring, interior island
    vertices = np.asarray(mesh["vertices_xy"], dtype=np.float64)
    touched = set()
    for triangle in mesh["triangles"]:
        coords = np.rint(vertices[triangle]).astype(np.int32)
        ids = {int(labels[y, x]) for x, y in coords}
        assert len(ids) == 1 and 0 not in ids, (
            "a triangle must never bridge independently observed components"
        )
        touched.update(ids)
    assert touched == {1, 2}


def test_holes_are_not_silently_filled_by_neighboring_island(tmp_path):
    image = np.zeros((192, 192), dtype=np.uint8)
    image[15:177, 15:177] = 255
    image[65:127, 65:127] = 0
    image[83:108, 83:108] = 255
    mesh = _run(image, tmp_path)
    assert mesh["connected_components"] == 2
    vertices = np.asarray(mesh["vertices_xy"], dtype=np.float64)
    count, labels = cv2.connectedComponents(np.uint8(image > 0), connectivity=8)
    assert count == 3
    for triangle in mesh["triangles"]:
        coords = np.rint(vertices[triangle]).astype(int)
        component_id = int(labels[coords[0, 1], coords[0, 0]])
        assert component_id != 0
        component = labels == component_id
        assert _triangle_coverage(component, vertices[triangle], cv2) >= 0.92
