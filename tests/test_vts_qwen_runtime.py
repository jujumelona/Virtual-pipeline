"""Execute the inference wrapper with a CPU worker; no GPU quality claim."""
from pathlib import Path
import sys
import types
from PIL import Image
import pytest

from tools import vts_qwen_refine as qwen


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repo = tmp_path / "third/Stable-Layers"
    repo.mkdir(parents=True)
    (repo / "decompose.py").write_text("pinned source checked separately")
    snapshot = tmp_path / "snapshot"
    (snapshot / "model").mkdir(parents=True)
    (snapshot / "model/adapter_model.safetensors").write_bytes(b"fixture")
    monkeypatch.setitem(sys.modules, "huggingface_hub", types.SimpleNamespace(
        snapshot_download=lambda *a, **kw: str(snapshot)))
    Image.new("RGBA", (64, 96), (50, 60, 70, 255)).save("input.png")
    return repo


def worker_source(write_layers=True, size=(432, 640)):
    return '''import argparse
from pathlib import Path
from PIL import Image
p=argparse.ArgumentParser()
p.add_argument('--input'); p.add_argument('--output'); p.add_argument('--num-layers', type=int)
a, _=p.parse_known_args()
folder=Path(a.output)/Path(a.input).stem
folder.mkdir(parents=True, exist_ok=True)
print('CPU wrapper fixture completed')
''' + (f'''for i in range(a.num_layers):
    Image.new('RGBA', {size!r}, (50,60,70,255)).save(folder/f'layer_{{i}}.png')
''' if write_layers else "")


def test_relative_runtime_paths_survive_worker_cwd(runtime, monkeypatch):
    monkeypatch.setattr(qwen, "_patch_pinned_official", lambda *a, **kw: worker_source())
    result = qwen.infer(Path("input.png"), Path("output"), third_party=Path("third"),
                        layer_count=3, timeout=20)
    assert result["layer_count"] == 3
    assert all(Path(p).is_absolute() and Path(p).is_file() for p in result["layers"])
    assert Path(result["log"]).read_text().strip() == "CPU wrapper fixture completed"


def test_successful_worker_cannot_reuse_stale_candidate_pngs(runtime, monkeypatch):
    monkeypatch.setattr(qwen, "_patch_pinned_official", lambda *a, **kw: worker_source(False))
    output = Path("output").resolve()
    stale = output / "qwen_layers/input"
    stale.mkdir(parents=True)
    for i in range(3):
        Image.new("RGBA", (64, 96)).save(stale / f"layer_{i}.png")
    with pytest.raises(RuntimeError, match="didn't provide"):
        qwen.infer(Path("input.png").resolve(), output, third_party=runtime.parent,
                   layer_count=3, timeout=20)


def test_successful_worker_must_emit_official_resized_dimensions(runtime, monkeypatch):
    monkeypatch.setattr(qwen, "_patch_pinned_official",
                        lambda *a, **kw: worker_source(size=(64, 96)))
    with pytest.raises(ValueError, match="dimensions"):
        qwen.infer(Path("input.png"), Path("output"), third_party=runtime.parent,
                   timeout=20)
