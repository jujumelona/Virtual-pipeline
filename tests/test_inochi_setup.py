"""Native Inochi D SDK bootstrap regression tests, without apt/DUB or GPUs."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import subprocess

import pytest

from tools import setup_inochi_runtime as setup


def test_native_build_failure_exposes_real_compiler_errors(tmp_path, monkeypatch):
    monkeypatch.setattr(setup, "CACHE", tmp_path)
    def fail(cmd, *, timeout, cwd, stdout, stderr, check):
        stdout.write("source/app.d(71): Error: missing symbol in official SDK\n")
        stdout.flush()
        return SimpleNamespace(returncode=2)
    monkeypatch.setattr(setup.subprocess, "run", fail)
    with pytest.raises(RuntimeError, match="missing symbol in official SDK") as error:
        setup._run(["dub", "build", "--compiler=ldc2"], timeout=10, cwd=tmp_path)
    assert "Full compiler output:" in str(error.value)
    assert (tmp_path / "logs" / "native_build.log").is_file()
    assert "Error: missing symbol" in (tmp_path / "logs" / "native_build.log").read_text()


def test_native_setup_does_not_skip_missing_graphics_development_headers(monkeypatch):
    """Having ldc2/dub/xvfb is not proof that SDL2/GL/GLU/zlib can link."""
    monkeypatch.setattr(setup.shutil, "which", lambda name: "/usr/bin/" + name)
    checked = []
    monkeypatch.setattr(setup, "_link_dependencies_ready", lambda: len(checked) > 0)
    monkeypatch.setattr(setup, "_run", lambda cmd, **kwargs: checked.append(cmd))
    setup._install_compiler()
    assert any("apt-get" in cmd and "update" in cmd for cmd in checked)
    installs = [cmd for cmd in checked if "install" in cmd]
    assert len(installs) == 1
    for package in ("libsdl2-dev", "libgl1-mesa-dev", "libglu1-mesa-dev",
                    "zlib1g-dev", "ldc", "dub", "xvfb"):
        assert package in installs[0]


def test_native_setup_skips_apt_when_all_link_libraries_are_present(monkeypatch):
    monkeypatch.setattr(setup.shutil, "which", lambda name: "/usr/bin/" + name)
    monkeypatch.setattr(setup, "_link_dependencies_ready", lambda: True)
    monkeypatch.setattr(setup, "_run", lambda *a, **kw: pytest.fail("apt unnecessary"))
    setup._install_compiler()


def test_link_dependencies_fail_closed_without_pkg_config(monkeypatch):
    monkeypatch.setattr(setup.shutil, "which", lambda name: None)
    assert not setup._link_dependencies_ready()


def test_existing_sdk_check_requires_native_binary_not_just_a_marker(tmp_path, monkeypatch):
    monkeypatch.setattr(setup, "CACHE", tmp_path)
    assert not (tmp_path / "ready.json").exists()


def test_dub_dependency_lock_matches_known_good_native_build():
    import json
    versions = json.loads((setup.PROJECT / "dub.selections.json").read_text())["versions"]
    assert versions == {
        "bindbc-loader": "1.0.3",
        "fghj": "1.0.2",
        "i2d-opengl": "1.0.0",
        "imagefmt": "2.1.2",
        "inmath": "1.3.2",
        "inochi2d": "0.8.7",
        "mir-algorithm": "3.22.4",
        "mir-core": "1.7.4",
        "numem": "0.20.1",
        "silly": "1.1.1",
    }


def test_native_runtime_hash_includes_dependency_lock():
    import inspect
    assert "dependency_lock.read_bytes()" in inspect.getsource(
        setup.ensure_inochi_native_runtime)
