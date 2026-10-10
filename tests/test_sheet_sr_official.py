"""Compare the still-image SR contract against the official anime 6B release."""
import pytest


@pytest.mark.parametrize('scale', [1, 2, 4])
def test_outscale_resamples_complete_native_canvas_with_official_filters(scale):
    import cv2
    import numpy as np
    from tools.sheet_super_resolution import _finish_rgba
    rng = np.random.default_rng(42)
    rgb4 = rng.random((28, 52, 3), dtype=np.float32)
    alpha = rng.integers(0, 256, (7, 13), dtype=np.uint8)
    alpha4 = cv2.resize(alpha.astype(np.float32) / 255, (52, 28), interpolation=cv2.INTER_LINEAR)
    expected = np.rint(np.dstack((rgb4, alpha4)) * 255).astype(np.uint8)
    if scale != 4:
        expected = cv2.resize(expected, (13 * scale, 7 * scale), interpolation=cv2.INTER_LANCZOS4)
    actual = _finish_rgba(rgb4, alpha, output_scale=scale)
    assert np.array_equal(np.asarray(actual), expected)


def test_wrong_native_sr_canvas_is_rejected():
    import numpy as np
    from tools.sheet_super_resolution import _finish_rgba
    with pytest.raises(ValueError, match='native x4'):
        _finish_rgba(np.zeros((28, 51, 3), np.float32), np.zeros((7, 13), np.uint8), output_scale=2)


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
