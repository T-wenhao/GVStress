"""Unit tests for CLI report commands - targeting 85%+ coverage."""

import json
from pathlib import Path
from typing import cast

import pytest
from typer.testing import CliRunner

from gvstress.cli.main import app
from gvstress.report.models import (
    RunArtifact,
    Verdict,
    RunValidity,
    PrimaryAttribution,
    SecondaryAttribution,
)


runner = CliRunner()


def _write_minimal_run_json(dir_path: Path, **overrides) -> Path:
    """Write a minimal valid run.json for testing."""
    data = {
        "run_id": "test-run-abc123",
        "scenario": {"name": "smoke", "duration": 60},
        "verdict": Verdict.PASS.value,
        "run_validity": RunValidity.VALID.value,
        "primary_attribution": PrimaryAttribution.UNKNOWN.value,
        "secondary_attribution": SecondaryAttribution.UNKNOWN.value,
    }
    data.update(overrides)

    dir_path.mkdir(parents=True, exist_ok=True)
    run_json_path = dir_path / "reports" / "run.json"
    run_json_path.parent.mkdir(parents=True, exist_ok=True)
    with run_json_path.open("w", encoding="utf-8") as f:
        json.dump(data, f)
    return run_json_path


def _write_summary_md(dir_path: Path, content: str = "# Test Summary") -> Path:
    """Write a summary.md file."""
    summary_path = dir_path / "reports" / "summary.md"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(content, encoding="utf-8")
    return summary_path


class TestShowCommandValidation:
    """Tests for show_command validation and error paths."""

    def test_show_no_args_raises_bad_parameter(self) -> None:
        """Line 42-43: Must specify --latest or --run-id."""
        result = runner.invoke(app, ["report", "show"])
        assert result.exit_code == 2  # typer.BadParameter
        assert "Must specify --latest or --run-id" in result.output

    def test_show_latest_nonexistent_source(self, tmp_path: Path) -> None:
        """Lines 48-50: --latest with --source that doesn't exist."""
        nonexistent = tmp_path / "does_not_exist"
        result = runner.invoke(
            app, ["report", "show", "--latest", "--source", str(nonexistent)]
        )
        assert result.exit_code == 1
        assert f"No artifact root found at {nonexistent}" in result.output

    def test_show_latest_empty_artifact_root(self, tmp_path: Path) -> None:
        """Lines 57-59: --latest with artifact root but no run dirs."""
        empty_root = tmp_path / "empty_artifacts"
        empty_root.mkdir(parents=True, exist_ok=True)

        result = runner.invoke(
            app, ["report", "show", "--latest", "--source", str(empty_root)]
        )
        assert result.exit_code == 1
        assert "No runs found" in result.output

    def test_show_run_id_nonexistent_run_json(self, tmp_path: Path) -> None:
        """Lines 67-69: --run-id with missing run.json."""
        src_dir = tmp_path / "artifacts"
        src_dir.mkdir(parents=True, exist_ok=True)

        result = runner.invoke(
            app, ["report", "show", "--run-id", "nonexistent", "--source", str(src_dir)]
        )
        assert result.exit_code == 1
        assert "No run.json found" in result.output


class TestShowCommandSuccessPaths:
    """Tests for show_command normal execution paths."""

    def test_show_run_id_success(self, tmp_path: Path) -> None:
        """Lines 61-62, 71-73: --run-id success with --json."""
        src_dir = tmp_path / "artifacts"
        run_dir = src_dir / "my-run-123"
        _write_minimal_run_json(run_dir)

        result = runner.invoke(
            app,
            [
                "report",
                "show",
                "--run-id",
                "my-run-123",
                "--source",
                str(src_dir),
                "--json",
            ],
        )
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["run_id"] == "test-run-abc123"
        assert output["verdict"] == "pass"

    def test_show_latest_without_json_with_summary_md(self, tmp_path: Path) -> None:
        """Lines 75-77: --latest without --json, summary.md exists."""
        src_dir = tmp_path / "artifacts"
        run_dir = src_dir / "latest-run"
        _write_minimal_run_json(run_dir)
        summary_content = "# Summary Report\n\nVerdict: PASS"
        _write_summary_md(run_dir, summary_content)

        result = runner.invoke(
            app, ["report", "show", "--latest", "--source", str(src_dir)]
        )
        assert result.exit_code == 0
        assert summary_content in result.stdout

    def test_show_latest_without_json_without_summary_md(self, tmp_path: Path) -> None:
        """Lines 78-88: --latest without --json, no summary.md fallback."""
        src_dir = tmp_path / "artifacts"
        run_dir = src_dir / "latest-run"
        _write_minimal_run_json(run_dir)

        result = runner.invoke(
            app, ["report", "show", "--latest", "--source", str(src_dir)]
        )
        assert result.exit_code == 0
        assert "run_id=test-run-abc123" in result.stdout
        assert "verdict=pass" in result.stdout
        assert "scenario=smoke" in result.stdout

    def test_show_with_non_dict_scenario(self, tmp_path: Path) -> None:
        """Lines 83-84: scenario field is not a dict."""
        src_dir = tmp_path / "artifacts"
        run_dir = src_dir / "test-run"
        _write_minimal_run_json(run_dir, scenario="not_a_dict")

        result = runner.invoke(
            app, ["report", "show", "--run-id", "test-run", "--source", str(src_dir)]
        )
        assert result.exit_code == 0
        assert "scenario=unknown" in result.stdout

    def test_show_with_missing_keys_in_json(self, tmp_path: Path) -> None:
        """Lines 86-88: Missing run_id, verdict keys."""
        src_dir = tmp_path / "artifacts"
        run_dir = src_dir / "test-run"
        # Use empty dict for scenario to avoid JSON serialization of None
        _write_minimal_run_json(run_dir, run_id="", verdict="")

        result = runner.invoke(
            app, ["report", "show", "--run-id", "test-run", "--source", str(src_dir)]
        )
        assert result.exit_code == 0
        # Empty strings serialize as empty, .get() returns them as-is
        assert "run_id=" in result.stdout
        assert "verdict=" in result.stdout
        assert "scenario=smoke" in result.stdout


class TestExportCommand:
    """Tests for export_command."""

    def test_export_nonexistent_run(self, tmp_path: Path) -> None:
        """Lines 117-119: Export with non-existent run-id."""
        src_dir = tmp_path / "artifacts"
        src_dir.mkdir(parents=True, exist_ok=True)

        result = runner.invoke(
            app,
            [
                "report",
                "export",
                "--run-id",
                "nonexistent",
                "--source",
                str(src_dir),
                "--output",
                str(tmp_path / "out.json"),
            ],
        )
        assert result.exit_code == 1
        assert "No run.json found" in result.output

    def test_export_unsupported_format(self, tmp_path: Path) -> None:
        """Lines 121-123: Unsupported format."""
        src_dir = tmp_path / "artifacts"
        run_dir = src_dir / "test-run"
        _write_minimal_run_json(run_dir)

        result = runner.invoke(
            app,
            [
                "report",
                "export",
                "--run-id",
                "test-run",
                "--source",
                str(src_dir),
                "--output",
                str(tmp_path / "out.xml"),
                "--format",
                "xml",
            ],
        )
        assert result.exit_code == 1
        assert "Unsupported format 'xml'" in result.output

    def test_export_creates_parent_directories(self, tmp_path: Path) -> None:
        """Line 127: Creates parent directories for output."""
        src_dir = tmp_path / "artifacts"
        run_dir = src_dir / "test-run"
        _write_minimal_run_json(run_dir)

        output_path = tmp_path / "deep" / "nested" / "path" / "out.json"

        result = runner.invoke(
            app,
            [
                "report",
                "export",
                "--run-id",
                "test-run",
                "--source",
                str(src_dir),
                "--output",
                str(output_path),
            ],
        )
        assert result.exit_code == 0
        assert output_path.exists()
        assert "Exported test-run to" in result.stdout

    def test_export_success_json(self, tmp_path: Path) -> None:
        """Lines 125-131: Successful export."""
        src_dir = tmp_path / "artifacts"
        run_dir = src_dir / "test-run"
        _write_minimal_run_json(run_dir)

        output_path = tmp_path / "exported.json"

        result = runner.invoke(
            app,
            [
                "report",
                "export",
                "--run-id",
                "test-run",
                "--source",
                str(src_dir),
                "--output",
                str(output_path),
            ],
        )
        assert result.exit_code == 0

        with output_path.open(encoding="utf-8") as f:
            exported = json.load(f)
        assert exported["run_id"] == "test-run-abc123"


class TestLoadReportJsonHelper:
    """Tests for _load_report_json helper."""

    def test_load_valid_json(self, tmp_path: Path) -> None:
        """Lines 12-14: Load valid JSON."""
        run_json = tmp_path / "run.json"
        with run_json.open("w", encoding="utf-8") as f:
            json.dump({"key": "value"}, f)

        from gvstress.cli.report import _load_report_json

        data = _load_report_json(run_json)
        assert data["key"] == "value"


class TestShowLatestMultipleRuns:
    """Test that --latest selects newest by mtime."""

    def test_show_latest_selects_newest_run(self, tmp_path: Path) -> None:
        """Lines 52-60: Multiple runs, newest selected."""
        import time

        src_dir = tmp_path / "artifacts"
        src_dir.mkdir(parents=True, exist_ok=True)

        # Create older run first
        older = src_dir / "older-run"
        _write_minimal_run_json(older, run_id="older")
        older.stat().st_mtime  # Touch to set mtime

        # Create newer run
        newer = src_dir / "newer-run"
        _write_minimal_run_json(newer, run_id="newer")

        # Ensure newer has later mtime
        time.sleep(0.1)
        newer.touch()

        result = runner.invoke(
            app, ["report", "show", "--latest", "--source", str(src_dir), "--json"]
        )
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["run_id"] == "newer"
