"""Installation boundaries: 2D workers do not replace the Colab CUDA ABI."""
import json
from pathlib import Path

import pytest

from tools import install_2d_workers as installer


@pytest.fixture
def patched_root(tmp_path, monkeypatch):
    root=tmp_path/"project"
    root.mkdir()
    lock={"tools": {
        "anime_segmentation": {
            "source_url": "https://github.com/SkyTNT/anime-segmentation",
            "source_commit": "a"*40,
        },
        "sam2_1_hiera_tiny": {
            "source_url": "https://github.com/facebookresearch/sam2",
            "source_commit": "b"*40,
        },
        "flux2_klein_4b": {
            "source_url": "https://github.com/huggingface/diffusers",
            "source_commit": "c"*40,
        },
    }}
    (root/"third_party.lock.json").write_text(json.dumps(lock))
    monkeypatch.setattr(installer, "ROOT", root)
    monkeypatch.setattr(installer, "WORK", tmp_path/"workers")
    return root, tmp_path/"workers", lock


def test_rejects_unpinned_or_non_github_sources():
    with pytest.raises(ValueError, match="immutable"):
        installer._pinned_source("sam", {"tools":{
            "sam2_1_hiera_tiny": {
                "source_url":"https://untrusted.example.invalid/download",
                "source_commit":"main",
            }
        }})


def test_failed_upstream_checkout_never_writes_ready_marker(patched_root, monkeypatch):
    root, work, lock=patched_root
    import sys
    from types import SimpleNamespace
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(__version__="2.6.0+cu124"))
    monkeypatch.setitem(sys.modules, "torchvision", SimpleNamespace(__version__="0.21.0+cu124"))
    monkeypatch.setattr(installer.venv.EnvBuilder, "create", lambda self, path: (Path(path)/"bin").mkdir(parents=True, exist_ok=True))
    def fail_checkout(kind, lock):
        raise RuntimeError("deliberate offline checkout failure")
    monkeypatch.setattr(installer, "_checkout_source", fail_checkout)
    monkeypatch.setattr(installer, "_exec", lambda *args, **kwargs: None)
    with pytest.raises(RuntimeError, match="offline checkout failure"):
        installer.install_2d_environment()
    assert not (work/"environment.ready.json").exists()
    assert (work/"cuda_constraints.txt").read_text().splitlines() == [
        "torch==2.6.0", "torchvision==0.21.0"
    ]


def test_worker_activation_uses_distinct_flux_executable(monkeypatch):
    payload = {
        "python": "/isolated/sam/bin/python",
        "flux_python": "/isolated/flux/bin/python",
        "anime_source": "/isolated/anime",
    }
    monkeypatch.setattr(installer, "install_2d_environment", lambda: payload)
    for key in ("VTUBER_WORKER_ANIME_ALPHA", "VTUBER_WORKER_FLORENCE",
                "VTUBER_WORKER_SAM", "VTUBER_WORKER_FLUX",
                "ANIME_SEGMENTATION_REPO"):
        monkeypatch.setenv(key, "previous-value")
    result=installer.activate_2d_environment()
    assert result is payload
    assert installer.os.environ["VTUBER_WORKER_ANIME_ALPHA"] == payload["python"]
    assert installer.os.environ["VTUBER_WORKER_FLORENCE"] == payload["python"]
    assert installer.os.environ["VTUBER_WORKER_SAM"] == payload["python"]
    assert installer.os.environ["VTUBER_WORKER_FLUX"] == payload["flux_python"]
    assert installer.os.environ["ANIME_SEGMENTATION_REPO"] == payload["anime_source"]


def test_venv_bootstrap_never_invokes_ensurepip(patched_root, monkeypatch):
    """Colab worker venvs inherit pip and CUDA packages without ensurepip."""
    _, work, _ = patched_root
    created = []
    invoked = []

    class Builder:
        def __init__(self, **settings):
            created.append(settings)

        def create(self, path):
            (Path(path) / "bin").mkdir(parents=True)

    monkeypatch.setattr(installer.venv, "EnvBuilder", Builder)
    monkeypatch.setattr(
        installer, "_exec", lambda args, **kwargs: invoked.append(args),
    )
    for name in ("venv", "venv_flux", "venv_alpha"):
        interpreter = installer._prepare_venv(name)
        assert interpreter == work / name / "bin" / "python"
    assert len(created) == 3
    assert all(option == {"with_pip": False, "system_site_packages": True}
               for option in created)
    assert all(command[-3:] == ["-m", "pip", "--version"] for command in invoked)


def test_worker_dependency_failure_contains_actual_pip_stderr(
    patched_root, capsys,
):
    """Do not collapse resolver errors to a CalledProcessError command."""
    import sys
    _, work, _ = patched_root
    with pytest.raises(RuntimeError, match="No matching distribution found") as error:
        installer._exec([
            sys.executable, "-c",
            "import sys; print('No matching distribution found: test-wheel', "
            "file=sys.stderr); sys.exit(19)",
        ], timeout=15)
    assert "exit=19" in str(error.value)
    assert "dependency_setup.log" in str(error.value)
    logfile = work / "logs" / "dependency_setup.log"
    assert logfile.is_file()
    assert "No matching distribution found" in logfile.read_text(encoding="utf-8")
    assert "No matching distribution found" in capsys.readouterr().out
