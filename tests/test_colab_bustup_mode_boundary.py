from tools.colab_mode_ui import select_mode

def test_bust_up_brief_and_colab_runtime_are_separate_but_compatible():
    selected = select_mode("live2d_bust_up", "body")
    assert selected.family == "live2d"
    assert selected.framing == "upper"
    assert selected.asset_kind == "body"
    assert selected.top_mode == "live2d_bust_up"
