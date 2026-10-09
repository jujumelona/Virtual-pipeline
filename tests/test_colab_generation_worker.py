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
    with pytest.raises(ValueError, match="master image, usage, optional layer ZIP"):
        worker.run_request({"mode": "live2d", "args": ["photo.png", "usage", "parts.zip", "extra"]})


def test_2d_layered_mode_passes_exact_user_zip_to_production(monkeypatch):
    invoked = []
    def fake_runpy(*args, **kwargs):
        return {"_run_2d_production_inline": lambda *values, target: (
            invoked.append((target, values)) or ("prepared", "user layers", None)
        )}
    monkeypatch.setattr(worker.runpy, "run_path", fake_runpy)
    result = worker.run_request({
        "mode": "live2d", "args": ["master.png", "corporation", "26_layers.zip"]
    })
    assert result == ["prepared", "user layers", None]
    assert invoked == [("live2d", ("master.png", "corporation", "26_layers.zip"))]


def test_generation_bootstrap_uses_stdlib_only():
    import ast
    tree = ast.parse((worker.ROOT / "tools" / "colab_generation_worker.py").read_text())
    imports = [
        alias.name.split(".")[0]
        for node in tree.body if isinstance(node, ast.Import)
        for alias in node.names
    ]
    assert not {"gradio", "torch", "numpy", "scipy"} & set(imports)


def test_live2d_failed_callback_emits_failed_event_not_complete(
    tmp_path, monkeypatch, capsys,
):
    import json
    import sys

    request = tmp_path / "request.json"
    result = tmp_path / "result.json"
    request.write_text(json.dumps({"mode": "live2d",
                                   "args": ["/tmp/source.png", "corporation"]}))
    monkeypatch.setattr(sys, "argv", ["colab_generation_worker.py",
                                      str(request), str(result)])
    monkeypatch.setattr(worker, "run_request", lambda request: [
        "live2d: 제작 실패 (임시 그림 파일을 모델 완성으로 표시하지 않음)",
        "flux_worker.py: exit=-9; log=flux.result.log",
        None,
    ])
    assert worker.main() == 0
    assert result.is_file(), "Preserve callback details for notebook error"
    output = capsys.readouterr().out
    assert '"kind": "failed"' in output
    assert '"kind": "complete"' not in output
    assert "exit=-9" in output
