"""CPU reconstruction boundary tests.

Actual TripoSR inference remains a GPU E2E concern. These tests exercise every
fail-closed boundary that can be verified without loading the model.
"""

from __future__ import annotations

import pathlib
import types

import pytest


@pytest.mark.parametrize(
    ("profile", "model_format", "remove_background", "message"),
    [
        ("typo", "obj", True, "profile"),
        ("commercial", "fbx", True, "model_save_format"),
        ("commercial", "obj", "yes", "remove_background"),
    ],
)
def test_invalid_request_fails_before_runtime_resolution(
    tmp_path,
    monkeypatch,
    profile,
    model_format,
    remove_background,
    message,
):
    import vtuber_pipeline.avatar.reconstruction as module

    image = tmp_path / "input.png"
    image.write_bytes(b"image")

    monkeypatch.setattr(
        module,
        "find_triposr_installation",
        lambda: pytest.fail("TripoSR code lookup must not run"),
    )
    monkeypatch.setattr(
        module,
        "resolve_triposr_model",
        lambda: pytest.fail("model download must not run"),
    )

    with pytest.raises((ValueError, FileNotFoundError), match=message):
        module.reconstruct_avatar(
            str(image),
            str(tmp_path / "out"),
            profile=profile,
            model_save_format=model_format,
            remove_background=remove_background,
        )


@pytest.mark.parametrize("payload", [None, b""])
def test_missing_or_empty_input_fails_before_runtime_resolution(
    tmp_path,
    monkeypatch,
    payload,
):
    import vtuber_pipeline.avatar.reconstruction as module

    image = tmp_path / "input.png"
    if payload is not None:
        image.write_bytes(payload)

    monkeypatch.setattr(
        module,
        "find_triposr_installation",
        lambda: pytest.fail("TripoSR code lookup must not run"),
    )
    monkeypatch.setattr(
        module,
        "resolve_triposr_model",
        lambda: pytest.fail("model download must not run"),
    )

    with pytest.raises(FileNotFoundError, match="missing or empty"):
        module.reconstruct_avatar(
            str(image),
            str(tmp_path / "out"),
        )


def test_commercial_source_revision_mismatch_is_rejected(
    tmp_path,
    monkeypatch,
):
    import vtuber_pipeline.avatar.reconstruction as module

    run_script = tmp_path / "TripoSR" / "run.py"
    run_script.parent.mkdir()
    run_script.write_text("# fake", encoding="utf-8")

    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *args, **kwargs: types.SimpleNamespace(
            returncode=0,
            stdout="deadbeef\n",
            stderr="",
        ),
    )

    with pytest.raises(RuntimeError, match="revision mismatch"):
        module.verify_triposr_revision(
            str(run_script),
            "commercial",
        )


def test_development_profile_does_not_require_git_revision(
    tmp_path,
    monkeypatch,
):
    import vtuber_pipeline.avatar.reconstruction as module

    run_script = tmp_path / "run.py"
    run_script.write_text("# fake", encoding="utf-8")
    called = False

    def should_not_run(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("git revision lookup ran")

    monkeypatch.setattr(module.subprocess, "run", should_not_run)
    module.verify_triposr_revision(str(run_script), "development")
    assert called is False


def test_success_exit_without_expected_mesh_is_rejected(
    tmp_path,
    monkeypatch,
):
    import vtuber_pipeline.avatar.reconstruction as module

    image = tmp_path / "input.png"
    image.write_bytes(b"image")
    run_script = tmp_path / "TripoSR" / "run.py"
    run_script.parent.mkdir()
    run_script.write_text("# fake", encoding="utf-8")
    model_dir = tmp_path / "model"
    model_dir.mkdir()

    monkeypatch.setattr(
        module,
        "find_triposr_installation",
        lambda: str(run_script),
    )
    monkeypatch.setattr(
        module,
        "verify_triposr_revision",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        module,
        "resolve_triposr_model",
        lambda: str(model_dir),
    )
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *args, **kwargs: types.SimpleNamespace(
            returncode=0,
            stdout="",
            stderr="",
        ),
    )

    with pytest.raises(RuntimeError, match="not found or empty"):
        module.reconstruct_avatar(
            str(image),
            str(tmp_path / "out"),
        )


def test_accessory_batch_preserves_per_item_failure_contract(
    tmp_path,
    monkeypatch,
):
    import vtuber_pipeline.accessory.reconstruction as module

    images = [
        str(tmp_path / "ok.png"),
        str(tmp_path / "bad.png"),
    ]

    def fake_reconstruct(image_path, output_dir, **kwargs):
        if image_path.endswith("bad.png"):
            raise RuntimeError("synthetic failure")
        return str(pathlib.Path(output_dir) / "mesh.glb")

    monkeypatch.setattr(module, "reconstruct_avatar", fake_reconstruct)

    result = module.reconstruct_accessories(
        images,
        str(tmp_path / "out"),
    )

    assert len(result) == 2
    assert result[0]["status"] == "complete"
    assert result[0]["image"] == images[0]
    assert result[1]["status"] == "error"
    assert result[1]["image"] == images[1]
    assert result[1]["mesh"] is None
    assert "synthetic failure" in result[1]["error"]


def test_commercial_dirty_triposr_checkout_is_rejected(
    tmp_path,
    monkeypatch,
):
    import vtuber_pipeline.avatar.reconstruction as module

    run_script = tmp_path / "TripoSR" / "run.py"
    run_script.parent.mkdir()
    run_script.write_text("# fake", encoding="utf-8")

    def fake_run(cmd, **kwargs):
        if cmd[-2:] == ["rev-parse", "HEAD"]:
            return types.SimpleNamespace(
                returncode=0,
                stdout=module.TRIPOSR_PINNED_COMMIT + "\n",
                stderr="",
            )
        if "status" in cmd:
            return types.SimpleNamespace(
                returncode=0,
                stdout=" M run.py\n",
                stderr="",
            )
        raise AssertionError(cmd)

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="exact pinned TripoSR"):
        module.verify_triposr_revision(
            str(run_script),
            "commercial",
        )


def test_commercial_untracked_source_injection_is_rejected(
    tmp_path,
    monkeypatch,
):
    import vtuber_pipeline.avatar.reconstruction as module

    run_script = tmp_path / "TripoSR" / "run.py"
    run_script.parent.mkdir()
    run_script.write_text("# fake", encoding="utf-8")

    def fake_run(cmd, **kwargs):
        if cmd[-2:] == ["rev-parse", "HEAD"]:
            return types.SimpleNamespace(
                returncode=0,
                stdout=module.TRIPOSR_PINNED_COMMIT + "\n",
                stderr="",
            )
        if "status" in cmd:
            assert "--untracked-files=all" in cmd
            return types.SimpleNamespace(
                returncode=0,
                stdout="?? tsr/injected_backend.py\n",
                stderr="",
            )
        raise AssertionError(cmd)

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="untracked changes"):
        module.verify_triposr_revision(
            str(run_script),
            "commercial",
        )


def test_commercial_checkout_ignores_only_python_bytecode_cache(
    tmp_path,
    monkeypatch,
):
    import vtuber_pipeline.avatar.reconstruction as module

    run_script = tmp_path / "TripoSR" / "run.py"
    run_script.parent.mkdir()
    run_script.write_text("# fake", encoding="utf-8")

    def fake_run(cmd, **kwargs):
        if cmd[-2:] == ["rev-parse", "HEAD"]:
            return types.SimpleNamespace(
                returncode=0,
                stdout=module.TRIPOSR_PINNED_COMMIT + "\n",
                stderr="",
            )
        if "status" in cmd:
            return types.SimpleNamespace(
                returncode=0,
                stdout=(
                    "?? tsr/__pycache__/system.cpython-312.pyc\n"
                    "?? __pycache__/run.cpython-312.pyc\n"
                ),
                stderr="",
            )
        raise AssertionError(cmd)

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    module.verify_triposr_revision(
        str(run_script),
        "commercial",
    )


@pytest.mark.parametrize("remove_background", [True, False])
def test_relative_paths_are_absolute_for_triposr_subprocess(
    tmp_path, monkeypatch, remove_background,
):
    """Subprocess cwd is the third-party checkout, not the CLI caller's cwd."""
    import trimesh
    import vtuber_pipeline.avatar.reconstruction as module

    monkeypatch.chdir(tmp_path)
    image = tmp_path / "character.png"
    image.write_bytes(b"fake-image")
    run_script = tmp_path / "TripoSR" / "run.py"
    run_script.parent.mkdir()
    run_script.write_text("# fake runner", encoding="utf-8")

    monkeypatch.setattr(module, "find_triposr_installation", lambda: str(run_script))
    monkeypatch.setattr(
        module, "verify_triposr_revision", lambda *_args: None,
    )
    monkeypatch.setattr(
        module, "resolve_triposr_model", lambda: str(tmp_path / "model"),
    )
    monkeypatch.setattr(
        trimesh,
        "load",
        lambda *_args, **_kwargs: types.SimpleNamespace(
            vertices=list(range(16)), faces=list(range(8)),
            apply_transform=lambda _matrix: None,
            export=lambda path: pathlib.Path(path).write_bytes(b"canonical-mesh"),
        ),
    )

    def fake_run(cmd, *, cwd, **kwargs):
        assert pathlib.Path(cwd) == run_script.parent
        assert pathlib.Path(cmd[3]) == image
        output_dir = pathlib.Path(cmd[cmd.index("--output-dir") + 1])
        assert output_dir == tmp_path / "output"
        assert output_dir.is_absolute()
        assert ("--no-remove-bg" in cmd) is (not remove_background)
        mesh_path = output_dir / "0" / "mesh.obj"
        mesh_path.parent.mkdir(parents=True, exist_ok=True)
        mesh_path.write_bytes(b"mesh")
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    mesh = module.reconstruct_avatar(
        "character.png",
        "output",
        profile="development",
        remove_background=remove_background,
    )
    assert pathlib.Path(mesh) == tmp_path / "output" / "0" / "mesh_canonical.obj"
