import pytest
from tools.colab_mode_ui import select_mode

def test_bust_up_image_guide_not_executable():
    with pytest.raises(ValueError, match="ZIP"):
        select_mode("live2d_bust_up", "body")
