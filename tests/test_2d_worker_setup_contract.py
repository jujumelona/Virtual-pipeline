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


def test_pinned_diffusers_uses_isolated_hub_and_transformers_compatible_api():
    """Pinned Diffusers imports resolve_revision (not exported by Hub 0.36.2)."""
    assert "huggingface-hub==1.33.0" in installer.FLUX_PYTHON_PACKAGES
    assert "transformers==5.0.0" in installer.FLUX_PYTHON_PACKAGES
    assert "resolve_revision" in installer.FLUX_SMOKE
    assert "Qwen3ForCausalLM" in installer.FLUX_SMOKE
    assert "Flux2KleinPipeline" in installer.FLUX_SMOKE
    assert "torchao==0.16.0" in installer.FLUX_PYTHON_PACKAGES
    assert "FqnToConfig" in installer.FLUX_SMOKE
    assert not any("huggingface-hub" in name or "transformers" in name
                   for name in installer.PYTHON_PACKAGES)
    # The smoke is a valid Python statement, not an inert comment.
    compile(installer.FLUX_SMOKE, "<flux-import-check>", "exec")


def test_2d_installer_pins_flux_hub_without_modifying_shared_cuda(patched_root, monkeypatch):
    """Regress the exact broken Colab install sequence with mocked external I/O."""
    from types import SimpleNamespace
    import sys
    _, work, _ = patched_root
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(__version__="2.11.0+cu130"))
    monkeypatch.setitem(sys.modules, "torchvision", SimpleNamespace(__version__="0.26.0+cu130"))
    calls = []
    monkeypatch.setattr(installer, "_prepare_venv",
                        lambda folder: work / folder / "bin" / "python")

    def checkout(kind, lock):
        path = work / "upstream" / kind
        path.mkdir(parents=True, exist_ok=True)
        if kind == "anime":
            (path / "train.py").write_text("class AnimeSegmentation: pass")
        return path

    monkeypatch.setattr(installer, "_checkout_source", checkout)
    monkeypatch.setattr(installer, "_smoke", lambda *a, **kw: None)
    monkeypatch.setattr(installer, "_exec",
                        lambda args, **kw: calls.append((args, kw)))
    result = installer.install_2d_environment()
    assert result["flux_python"].endswith("/venv_flux/bin/python")
    assert (work / "environment.ready.json").is_file()
    flux_pip = [
        args for args, _kw in calls
        if args[:5] == [
            str(work / "venv_flux" / "bin" / "python"),
            "-m", "pip", "install", "--prefer-binary",
        ]
    ]
    assert len(flux_pip) == 1
    assert "huggingface-hub==1.33.0" in flux_pip[0]
    assert "transformers==5.0.0" in flux_pip[0]
    assert "torchao==0.16.0" in flux_pip[0]
    assert not any(
        value.startswith(("torch==", "torch>=", "torchvision==", "torchvision>="))
        for value in flux_pip[0]
    )
    assert (work / "cuda_constraints.txt").read_text().splitlines() == [
        "torch==2.11.0", "torchvision==0.26.0",
    ]
    assert any(
        args == [str(work / "venv_flux" / "bin" / "python"),
                 "-c", installer.FLUX_SMOKE]
        for args, _kw in calls
    )
    saved = json.loads((work / "environment.ready.json").read_text())
    assert saved["fingerprint"] == result["fingerprint"]


def test_pinned_sam2_upstream_runtime_requirements_not_skipped():
    """Official SAM2 setup.py requires iopath; --no-deps is permitted only
    when the pipeline explicitly supplies that runtime dependency.
    """
    assert "iopath==0.1.10" in installer.SAM2_RUNTIME_PACKAGES
    assert "portalocker==2.10.1" in installer.PYTHON_PACKAGES
    smoke = installer.SAM2_CONSTRUCTION_SMOKE
    assert "from iopath.common.file_io import g_pathmgr" in smoke
    assert "from sam2.modeling.backbones.hieradet import Hiera" in smoke
    assert "build_sam2('configs/sam2.1/sam2.1_hiera_t.yaml'" in smoke
    assert "ckpt_path=None" in smoke
    assert "device='cpu'" in smoke
    assert "SAM2ImagePredictor(model)" in smoke
    compile(smoke, "<sam2-actual-hydra-smoke>", "exec")


def test_sam2_constructed_in_both_fresh_and_cached_worker_checks(monkeypatch):
    """The setup and cached ready-marker path both call a real construction,
    not a function import. The latter catches already-corrupt worker venvs.
    """
    import inspect
    code = inspect.getsource(installer._smoke)
    assert "SAM2_CONSTRUCTION_SMOKE" in code
    assert 'timeout=240' in code
    code = inspect.getsource(installer.install_2d_environment)
    assert '"sam2_construction_smoke": SAM2_CONSTRUCTION_SMOKE' in code
    assert "_smoke(python, source, torch_version, vision_version)" in code
    assert '_smoke(python, sources["anime"], torch_version, vision_version)' in code


def test_sam2_iopath_sdist_installed_separately_from_binary_only_python_wheels(
    patched_root, monkeypatch,
):
    import sys
    from types import SimpleNamespace
    _, work, _ = patched_root
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(__version__="2.11.0+cu130"))
    monkeypatch.setitem(sys.modules, "torchvision", SimpleNamespace(__version__="0.26.0+cu130"))
    seen = []
    monkeypatch.setattr(installer, "_prepare_venv",
                        lambda folder: work / folder / "bin" / "python")
    def checkout(kind, lock):
        path = work / "upstream" / kind
        path.mkdir(parents=True, exist_ok=True)
        if kind == "anime":
            (path / "train.py").write_text("pass")
        return path
    monkeypatch.setattr(installer, "_checkout_source", checkout)
    monkeypatch.setattr(installer, "_smoke", lambda *a, **k: None)
    monkeypatch.setattr(installer, "_exec", lambda args, **k: seen.append(args))
    installer.install_2d_environment()
    sam_install = [args for args in seen if "iopath==0.1.10" in args]
    assert len(sam_install) == 1
    assert "--no-deps" in sam_install[0]
    assert "--no-build-isolation" not in sam_install[0]  # PEP517 needs clean setuptools
    assert "--only-binary=:all:" not in sam_install[0]
    deps = [args for args in seen if "portalocker==2.10.1" in args]
    assert len(deps) == 1
    assert "--prefer-binary" in deps[0]
    assert "--only-binary=:all:" not in deps[0]  # Hydra requires ANTLR 4.9.3 sdist
    assert seen.index(deps[0]) < seen.index(sam_install[0])


def test_cache_fingerprint_contains_sam2_build_contract(patched_root, monkeypatch):
    import sys
    from types import SimpleNamespace
    _, work, _ = patched_root
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(__version__="2.11.0+cu130"))
    monkeypatch.setitem(sys.modules, "torchvision", SimpleNamespace(__version__="0.26.0+cu130"))
    monkeypatch.setattr(installer, "_prepare_venv",
                        lambda folder: work / folder / "bin" / "python")
    def checkout(kind, lock):
        folder = work / "upstream" / kind
        folder.mkdir(parents=True, exist_ok=True)
        if kind == "anime":
            (folder / "train.py").write_text("pass")
        return folder
    monkeypatch.setattr(installer, "_checkout_source", checkout)
    monkeypatch.setattr(installer, "_smoke", lambda *a, **k: None)
    monkeypatch.setattr(installer, "_exec", lambda *a, **k: None)
    result = installer.install_2d_environment()
    import hashlib
    assert len(result["fingerprint"]) == 64
    assert (work / "environment.ready.json").exists()
