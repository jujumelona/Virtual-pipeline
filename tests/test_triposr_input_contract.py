from pathlib import Path
from PIL import Image


def test_segmented_rgba_uses_official_foreground_resize_and_gray_composite(tmp_path):
    from vtuber_pipeline.avatar.triposr_runner import prepare_no_bg_image
    source = tmp_path / 'source.png'
    image = Image.new('RGBA', (16, 24), (240, 20, 80, 0))
    image.putpixel((8, 12), (200, 100, 60, 128)); image.save(source)
    calls = []
    def resize(rgba, ratio):
        calls.append((rgba.mode, ratio))
        return rgba
    target = tmp_path / 'input.png'
    assert prepare_no_bg_image(source, target, resize_foreground=resize) == target
    assert calls == [('RGBA', 0.85)]
    actual = Image.open(target)
    assert actual.mode == 'RGB'
    assert actual.getpixel((0, 0)) == (127, 127, 127)
    assert actual.getpixel((8, 12)) == (163, 113, 93)
    assert Image.open(source).mode == 'RGBA'  # source untouched


def test_opaque_prepared_input_is_not_normalized_twice(tmp_path):
    from vtuber_pipeline.avatar.triposr_runner import prepare_no_bg_image
    source = tmp_path / 'prepared.png'; Image.new('RGB', (16, 24), 'gray').save(source)
    def resize(*args):
        raise AssertionError('opaque preprocessed input must remain unchanged')
    assert prepare_no_bg_image(source, tmp_path / 'unused.png', resize_foreground=resize) == source
