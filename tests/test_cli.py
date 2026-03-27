"""Tests for the LetsBuild Typer CLI interface."""

from __future__ import annotations

from typer.testing import CliRunner

from letsbuild.cli import app

runner = CliRunner()


class TestCLIHelp:
    """Test --help and --version flags."""

    def test_help_exits_zero_and_contains_letsbuild(self) -> None:
        """--help exits 0 and output contains 'LetsBuild'."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "LetsBuild" in result.output

    def test_version_shows_version_number(self) -> None:
        """--version prints the version string and exits 0."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "3.0.0-alpha" in result.output


class TestIngestCommand:
    """Test the 'ingest' CLI command."""

    def test_ingest_with_url_exits_zero(self) -> None:
        """ingest --url exits 0 and prints not-yet-implemented message."""
        result = runner.invoke(app, ["ingest", "--url", "https://example.com"])
        assert result.exit_code == 0
        assert "not yet implemented" in result.output

    def test_ingest_without_args_exits_nonzero(self) -> None:
        """ingest with no arguments exits with code 1."""
        result = runner.invoke(app, ["ingest"])
        assert result.exit_code == 1

    def test_ingest_with_text_exits_zero(self) -> None:
        """ingest --text exits 0."""
        result = runner.invoke(app, ["ingest", "--text", "Software Engineer at ACME"])
        assert result.exit_code == 0
        assert "not yet implemented" in result.output

    def test_ingest_with_file_exits_zero(self) -> None:
        """ingest --file exits 0."""
        result = runner.invoke(app, ["ingest", "--file", "some_jd.txt"])
        assert result.exit_code == 0
        assert "not yet implemented" in result.output


class TestRunCommand:
    """Test the 'run' CLI command."""

    def test_run_with_url_exits_zero(self) -> None:
        """run --url exits 0 and prints not-yet-implemented message."""
        result = runner.invoke(app, ["run", "--url", "https://example.com"])
        assert result.exit_code == 0
        assert "not yet implemented" in result.output

    def test_run_without_args_exits_nonzero(self) -> None:
        """run with no arguments exits with code 1."""
        result = runner.invoke(app, ["run"])
        assert result.exit_code == 1


class TestStatusCommand:
    """Test the 'status' CLI command."""

    def test_status_with_thread_id_exits_zero(self) -> None:
        """status --thread-id exits 0 and prints not-yet-implemented message."""
        result = runner.invoke(app, ["status", "--thread-id", "abc-123"])
        assert result.exit_code == 0
        assert "not yet implemented" in result.output


class TestResearchCommand:
    """Test the 'research' CLI command."""

    def test_research_with_company_exits_zero(self) -> None:
        """research --company exits 0 and prints not-yet-implemented message."""
        result = runner.invoke(app, ["research", "--company", "TestCo"])
        assert result.exit_code == 0
        assert "not yet implemented" in result.output


class TestStubCommands:
    """Test remaining stub commands print not-yet-implemented."""

    def test_match_prints_not_yet_implemented(self) -> None:
        result = runner.invoke(app, ["match", "--file", "jd.txt"])
        assert result.exit_code == 0
        assert "not yet implemented" in result.output

    def test_architect_prints_not_yet_implemented(self) -> None:
        result = runner.invoke(app, ["architect", "--skill", "fullstack", "--jd", "jd.txt"])
        assert result.exit_code == 0
        assert "not yet implemented" in result.output

    def test_forge_prints_not_yet_implemented(self) -> None:
        result = runner.invoke(app, ["forge", "--spec", "spec.json"])
        assert result.exit_code == 0
        assert "not yet implemented" in result.output

    def test_publish_prints_not_yet_implemented(self) -> None:
        result = runner.invoke(app, ["publish", "--repo-name", "my-repo"])
        assert result.exit_code == 0
        assert "not yet implemented" in result.output
