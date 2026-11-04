"""Tests for bcb-microdados-fetcher Typer plugin."""

from typer.testing import CliRunner

from bcb_microdados_fetcher.catalog import list_datasets
from bcb_microdados_fetcher.plugin import app


def test_cli_list() -> None:
    """Test quantilica bcb-microdados list."""
    runner = CliRunner()
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "scr" in result.output
    assert f"{len(list_datasets())} dataset(s)" in result.output


def test_cli_convert_help() -> None:
    """Test quantilica bcb-microdados convert --help."""
    runner = CliRunner()
    result = runner.invoke(app, ["convert", "--help"])
    assert result.exit_code == 0
    assert "--lake" in result.output
