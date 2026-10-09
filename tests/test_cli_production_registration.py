"""Ensure every production command is registered before __main__ executes."""
from click.testing import CliRunner
from vtuber_pipeline.cli import cli


def test_production_subcommands_are_registered():
    commands = set(cli.commands)
    assert {
        "inochi2d", "live2d", "live2d-import-export", "avatar", "accessory",
        "inochi2d-prep", "live2d-prep",
    }.issubset(commands)


def test_help_parses_all_modes_without_model_downloads():
    runner = CliRunner()
    for name in ("inochi2d", "live2d", "live2d-import-export", "avatar"):
        result = runner.invoke(cli, [name, "--help"])
        assert result.exit_code == 0, (name, result.output)
    assert "--left-image" in runner.invoke(cli, ["avatar", "--help"]).output
    assert "--right-image" in runner.invoke(cli, ["avatar", "--help"]).output


def test_cli_reports_all_actual_3d_stages_in_production_order(tmp_path, monkeypatch):
    from pathlib import Path
    import vtuber_pipeline.avatar.build as avatar_builder

    source = tmp_path / "character.png"
    source.write_bytes(b"image")
    names = [
        ("reference_quality", {"status": "complete"}),
        ("licensed_multiview", {"status": "complete"}),
        ("blender_vrm_export", {"status": "complete"}),
        ("future_stage", {"status": "error", "error": "stage-boundary-mismatch"}),
    ]

    def fake_build(image, output, config):
        assert image == str(source)
        return {
            "status": "failed",
            "failed_reason": "stage-boundary-mismatch",
            "stages": dict(names),
        }

    monkeypatch.setattr(avatar_builder, "build_avatar", fake_build)
    result = CliRunner().invoke(cli, [
        "avatar", "--image", str(source), "--output", str(tmp_path / "output"),
    ])
    assert result.exit_code != 0
    assert "observed TripoSR multi-view reconstruction" in result.output
    assert "Blender native VRM 1.0 export" in result.output
    assert "future_stage: stage-boundary-mismatch" in result.output
    assert result.output.index("observed TripoSR") < result.output.index("Blender native")
