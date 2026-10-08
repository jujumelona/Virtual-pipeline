"""3D matting must be runnable without installing the SAM/FLUX 2D stack."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools import install_2d_workers as installer


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "third_party.lock.json").write_text(json.dumps({
        "tools": {"anime_segmentation": {
            "source_url": "https://github.com/SkyTNT/anime-segmentation",
            "source_commit": "a" * 40,
        }}
    }))
    monkeypatch.setattr(installer, "ROOT", root)
    monkeypatch.setattr(installer, "WORK", tmp_path / "workers")
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(__version__="2.6.0+cu124"))
    monkeypatch.setitem(sys.modules, "torchvision", SimpleNamespace(__version__="0.21.0+cu124"))
    monkeypatch.setattr(installer.venv.EnvBuilder, "create",
                        lambda self, path: (Path(path) / "bin").mkdir(parents=True, exist_ok=True))
    return tmp_path


def test_only_anime_upstream_is_requested_and_alpha_cuda_is_pinned(isolated, monkeypatch):
    calls = []
    checkout_kinds = []
    def capture(args, **kwargs):
        calls.append(args)
    def checkout(kind, lock):
        checkout_kinds.append(kind)
        source = installer.WORK / "upstream" / kind
        source.mkdir(parents=True, exist_ok=True)
        (source / "train.py").write_text("class AnimeSegmentation: pass")
        return source
    monkeypatch.setattr(installer, "_exec", capture)
    monkeypatch.setattr(installer, "_checkout_source", checkout)
    result = installer.install_alpha_environment()
    assert checkout_kinds == ["anime"]
    assert result["anime_source"].endswith("/anime")
    assert (installer.WORK / "alpha.ready.json").is_file()
    assert (installer.WORK / "alpha_cuda_constraints.txt").read_text().splitlines() == [
        "torch==2.6.0", "torchvision==0.21.0",
    ]
    installs = [line for args in calls for line in args if isinstance(line, str)]
    assert "Flux2KleinPipeline" not in repr(installs)
    assert "sam2" not in repr(installs).lower()


def test_alpha_checkout_failure_never_reports_ready(isolated, monkeypatch):
    monkeypatch.setattr(installer, "_exec", lambda *args, **kwargs: None)
    def fail(_kind, _lock):
        raise RuntimeError("network-down")
    monkeypatch.setattr(installer, "_checkout_source", fail)
    with pytest.raises(RuntimeError, match="network-down"):
        installer.install_alpha_environment()
    assert not (installer.WORK / "alpha.ready.json").exists()


def test_alpha_activation_never_sets_flux_or_sam_executable(monkeypatch):
    monkeypatch.setattr(installer, "install_alpha_environment", lambda: {
        "python": "/alpha/venv/bin/python",
        "anime_source": "/repo/anime",
    })
    for name in ("VTUBER_WORKER_FLUX", "VTUBER_WORKER_SAM", "VTUBER_WORKER_FLORENCE"):
        monkeypatch.setenv(name, "unchanged")
    payload = installer.activate_alpha_environment()
    assert installer.os.environ["VTUBER_WORKER_ANIME_ALPHA"] == payload["python"]
    assert installer.os.environ["ANIME_SEGMENTATION_REPO"] == payload["anime_source"]
    for name in ("VTUBER_WORKER_FLUX", "VTUBER_WORKER_SAM", "VTUBER_WORKER_FLORENCE"):
        assert installer.os.environ[name] == "unchanged"
