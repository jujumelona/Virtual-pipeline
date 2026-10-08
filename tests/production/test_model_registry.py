import re


def test_new_models_have_immutable_revisions_and_selective_files():
    from vtuber_pipeline.common.model_assets import model_pin
    for name in ('skytnt_anime_seg_isnet_is','florence2_base','sam2_1_hiera_tiny','flux2_klein_4b','instantmesh_large','depth_anything_v2_small'):
        pin=model_pin(name)
        assert re.fullmatch('[0-9a-f]{40}',pin['revision'])
        assert pin['allow_patterns']
    assert model_pin('instantmesh_large')['allow_patterns']==['instant_mesh_large.ckpt','diffusion_pytorch_model.bin','README.md']
    assert 'isnetis.onnx' not in model_pin('skytnt_anime_seg_isnet_is')['allow_patterns']
