"""Face landmarks preserve their original image frame and anatomical grouping."""
import numpy as np
from PIL import Image
import json

from vtuber_pipeline.perception.layer_split import (
    _landmark_subset, split_semantic_layers,
)


def test_anime_hrnet_groups_are_character_relative():
    landmarks = np.tile([110., 105.], (28, 1))
    landmarks[11:17, 0] = 70.   # viewer-left eye = character-right
    landmarks[17:23, 0] = 150.  # viewer-right eye = character-left
    landmarks[5:8, 0] = 65.
    landmarks[8:11, 0] = 160.
    assert np.mean(_landmark_subset("eye.left.iris", landmarks.tolist()), axis=0)[0] == 150.
    assert np.mean(_landmark_subset("eye.right", landmarks.tolist()), axis=0)[0] == 70.
    assert np.mean(_landmark_subset("brow.left", landmarks.tolist()), axis=0)[0] == 160.
    assert len(_landmark_subset("mouth.inner", landmarks.tolist())) == 5
    assert len(_landmark_subset("face", landmarks.tolist())) == 28
    assert not _landmark_subset("cloth.torso", landmarks.tolist())


def test_close_up_face_coordinates_cannot_escape_into_avatar_canvas(tmp_path):
    rgba = tmp_path / "source.png"
    Image.new("RGBA", (256, 256), (100, 40, 30, 255)).save(rgba)
    mask = tmp_path / "face_mask.png"
    Image.new("L", (256, 256), 255).save(mask)
    doc = tmp_path / "landmarks.json"
    doc.write_text(json.dumps({"image_size": [768, 768],
                               "landmarks": [[50, 50]] * 28}))
    masks = tmp_path / "masks.json"
    masks.write_text(json.dumps({"parts": [
        {"semantic_id": "face", "mask_png": str(mask)}
    ]}))
    result = split_semantic_layers(str(rgba), str(masks), str(doc),
                                   str(tmp_path / "layers"))
    assert result.parts[0].landmarks_xy == []
