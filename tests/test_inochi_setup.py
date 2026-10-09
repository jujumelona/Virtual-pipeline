"""Native Inochi D SDK bootstrap regression tests, without apt/DUB or GPUs."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import subprocess

import pytest

from tools import setup_inochi_runtime as setup


def test_native_build_failure_exposes_entire_live_compiler_output(
    tmp_path, monkeypatch, capsys,
):
    import sys
    monkeypatch.setattr(setup, "CACHE", tmp_path)
    # A real child prints an error before 300 unrelated compiler lines.
    # That first error must appear both on screen and in the saved log.
    script = (
        "import sys; print('source/app.d(71): Error: FIRST missing symbol', flush=True);"
        " [print('compiler-line-%04d' % i) for i in range(300)];"
        " print('/usr/bin/cc failed with status: 1'); sys.exit(2)"
    )
    with pytest.raises(RuntimeError, match="exit=2"):
        setup._run([sys.executable, "-u", "-c", script], timeout=10, cwd=tmp_path)
    output = capsys.readouterr().out
    file = (tmp_path / "logs" / "native_build.log").read_text()
    assert "FIRST missing symbol" in output
    assert "/usr/bin/cc failed with status: 1" in output
    assert "compiler-line-0000" in output
    assert "compiler-line-0299" in output
    assert output.index("FIRST missing symbol") < output.index("compiler-line-0299")
    assert "FIRST missing symbol" in file
    assert "compiler-line-0299" in file


def test_native_log_second_command_does_not_reprint_previous_output(
    tmp_path, monkeypatch, capsys,
):
    import sys
    monkeypatch.setattr(setup, "CACHE", tmp_path)
    setup._run([sys.executable, "-c", "print('first-command-marker')"],
               timeout=10, cwd=tmp_path)
    first = capsys.readouterr().out
    setup._run([sys.executable, "-c", "print('second-command-marker')"],
               timeout=10, cwd=tmp_path)
    second = capsys.readouterr().out
    assert "first-command-marker" in first
    assert "first-command-marker" not in second
    assert "second-command-marker" in second
    log = (tmp_path / "logs" / "native_build.log").read_text()
    assert "first-command-marker" in log and "second-command-marker" in log


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


def test_linker_preflight_compiles_c_graphics_and_ldc_phobos(tmp_path, monkeypatch):
    monkeypatch.setattr(setup, "CACHE", tmp_path)
    called = []
    def fake_run(cmd, *, timeout, cwd):
        called.append(cmd)
        assert Path(cmd[1]).is_file()
        assert cwd == setup.PROJECT
    monkeypatch.setattr(setup, "_run", fake_run)
    setup._verify_native_linker()
    assert len(called) == 2
    assert called[0][0] == "cc"
    assert {"-lSDL2", "-lGL", "-lGLdispatch", "-lGLU", "-lz"}.issubset(set(called[0]))
    c_flags = called[0]
    assert c_flags.index("-lGL") < c_flags.index("-lGLdispatch")
    assert "glGetString(GL_VERSION)" in Path(called[0][1]).read_text()
    assert called[1][0] == "ldc2"
    assert "-v" in called[1]
    assert "-L-lGL" in called[1]
    assert "-L-lGLdispatch" in called[1]


def test_linker_preflight_failure_is_not_swallowed(tmp_path, monkeypatch):
    monkeypatch.setattr(setup, "CACHE", tmp_path)
    def broken_cc(cmd, **kwargs):
        raise RuntimeError("/usr/bin/ld: cannot find -lSDL2")
    monkeypatch.setattr(setup, "_run", broken_cc)
    with pytest.raises(RuntimeError, match="cannot find -lSDL2"):
        setup._verify_native_linker()


def test_real_native_build_follows_linker_preflight_before_verbose_dub():
    import inspect
    code = inspect.getsource(setup.ensure_inochi_native_runtime)
    assert code.index("_verify_native_linker()") < code.index('["dub", "build"')
    assert '"--force", "--verbose"' in code


def test_real_dub_link_contract_resolves_libgldispatch_symbol():
    path = setup.PROJECT / "dub.sdl"
    code = path.read_text(encoding="utf-8")
    assert '"-lGLdispatch"' in code
    assert code.index('"-lGL"') < code.index('"-lGLdispatch"')
    installer = (setup.ROOT / "tools/setup_inochi_runtime.py").read_text()
    assert '"libglvnd-dev"' in installer
