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
    assert any(cmd[:2] == ["apt-get", "update"] for cmd in checked)
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
