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
