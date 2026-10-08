import numpy as np
import pytest
from PIL import Image


def test_original_pixels_outside_repair_unchanged():
    from vtuber_pipeline.perception.compose import masked_repair
    original=np.random.default_rng(2).integers(0,256,(16,20,4),dtype=np.uint8)
    generated=np.full((16,20,3),99,dtype=np.uint8)
    mask=np.zeros((16,20),dtype=np.uint8);mask[3:5,8:12]=255
    result=masked_repair(original,generated,mask)
    assert np.array_equal(result[mask==0],original[mask==0])
    assert np.all(result[mask>0,:3]==99)
    assert np.all(result[mask>0,3]==255)


def test_crop_inverse_and_character_side():
    from vtuber_pipeline.common.image_space import CropTransform
    transform=CropTransform(20,40,100,200,50,100)
    assert transform.point_to_original(50,100)==[120,240]


def test_mode_model_selection_excludes_unrelated_models():
    from vtuber_pipeline.common.model_assets import MODE_ASSETS
    assert 'triposr' not in MODE_ASSETS['common_2d']
    assert 'flux2_klein_4b' not in MODE_ASSETS['3d']


def test_layer_split_preserves_readonly_source_and_alpha(tmp_path):
    import json
    from vtuber_pipeline.perception.layer_split import split_semantic_layers
    original=np.zeros((32,32,4),dtype=np.uint8);original[:]=[12,24,36,255]
    source=tmp_path/'source.png';Image.fromarray(original).save(source)
    mask=np.zeros((32,32),dtype=np.uint8);mask[8:24,8:24]=255
    mp=tmp_path/'mask.png';Image.fromarray(mask).save(mp)
    index=tmp_path/'masks.json';index.write_text(json.dumps({'parts':[{'semantic_id':'face','mask_png':str(mp)}]}))
    landmarks=tmp_path/'landmarks.json';landmarks.write_text('{}')
    parts=split_semantic_layers(str(source),str(index),str(landmarks),str(tmp_path/'parts'))
    pixels=np.asarray(Image.open(parts.parts[0].rgba_png))
    assert np.array_equal(pixels[:,:,:3],original[:,:,:3])
    assert np.array_equal(pixels[:,:,3],mask)
