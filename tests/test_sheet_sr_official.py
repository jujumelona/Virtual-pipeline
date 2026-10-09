"""Compare the still-image SR contract against the official anime 6B release."""
import pytest


def test_still_image_preparation_uses_official_anime_6b_release():
    from tools import sheet_super_resolution as sr
    assert sr.MODEL_NAME == 'RealESRGAN_x4plus_anime_6B.pth'
    assert sr.EXPECTED_BYTES == 17938799
    assert sr.MODEL_URL.endswith('v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth')


def test_rrdb_loads_exact_checkpoint_shapes_and_keeps_x4_geometry():
    torch = pytest.importorskip('torch')
    from tools.sheet_super_resolution import _model_class
    torch.set_num_threads(1)
    model = _model_class()().eval()
    state = model.state_dict()
    assert tuple(state['conv_first.weight'].shape) == (64, 3, 3, 3)
    assert tuple(state['body.5.rdb3.conv5.weight'].shape) == (64, 192, 3, 3)
    assert 'body.6.rdb1.conv1.weight' not in state
    with torch.inference_mode():
        output = model(torch.zeros(1, 3, 9, 13))
    assert tuple(output.shape) == (1, 3, 36, 52)
    assert torch.isfinite(output).all()
