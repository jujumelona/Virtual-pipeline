"""Exercise headless mode routing without importing Gradio, torch or model weights."""
from __future__ import annotations

import pytest

from tools import colab_generation_worker as worker


def test_inochi_and_live2d_use_native_auto_parts_pipeline(monkeypatch):
    calls = []
    def route(*args, target):
        calls.append((target, args))
        return ("prepared", "real layers", None)

    def fake_runpy(*args, **kwargs):
        assert kwargs["run_name"] == "vtuber_prepare"
        return {"_run_2d_production_inline": route}

    monkeypatch.setattr(worker.runpy, "run_path", fake_runpy)
    for mode in ("inochi2d", "live2d"):
        assert worker.run_request({
            "mode": mode, "args": ["/tmp/photo.png", "personalProfit"]
        }) == ["prepared", "real layers", None]
    assert calls == [
        ("inochi2d", ("/tmp/photo.png", "personalProfit")),
        ("live2d", ("/tmp/photo.png", "personalProfit")),
    ]


def test_invalid_mode_or_wrong_character_inputs_fail_before_generation(monkeypatch):
    monkeypatch.setattr(worker.runpy, "run_path", lambda *a, **kw: {
        "_run_2d_production_inline": lambda *a, **kw: pytest.fail("must not invoke"),
    })
    with pytest.raises(ValueError, match="Unknown production mode"):
        worker.run_request({"mode": "unsupported", "args": []})
    with pytest.raises(ValueError, match="expects character image and usage"):
        worker.run_request({"mode": "live2d", "args": ["photo.png", "usage", "parts.zip"]})


def test_generation_bootstrap_uses_stdlib_only():
    import ast
    tree = ast.parse((worker.ROOT / "tools" / "colab_generation_worker.py").read_text())
    imports = [
        alias.name.split(".")[0]
        for node in tree.body if isinstance(node, ast.Import)
        for alias in node.names
    ]
    assert not {"gradio", "torch", "numpy", "scipy"} & set(imports)
