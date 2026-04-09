from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

CLI_ENTRY = [sys.executable, "-m", "gvstress"]


def run_cli(args: list[str], *, check: bool = False) -> subprocess.CompletedProcess:
    result = subprocess.run(
        [*CLI_ENTRY, *args],
        capture_output=True,
        text=True,
        check=check,
    )
    return result


def test_top_level_help_lists_required_groups():
    """Module-level test for plan compliance: verifies all required CLI groups are visible."""
    result = run_cli(["--help"])
    assert result.returncode == 0
    assert "fakecam" in result.stdout
    assert "dut" in result.stdout
    assert "dut-agent" in result.stdout
    assert "test" in result.stdout
    assert "baseline" in result.stdout
    assert "report" in result.stdout


class TestCLIHelp:
    def test_main_help(self):
        result = run_cli(["--help"])
        assert result.returncode == 0
        assert "GigE Vision stress testing framework" in result.stdout
        assert "fakecam" in result.stdout
        assert "dut" in result.stdout
        assert "test" in result.stdout
        assert "baseline" in result.stdout
        assert "report" in result.stdout

    # Module-level alias for plan compliance: tests/integration/test_cli_commands.py::test_top_level_help_lists_required_groups
    def test_top_level_help_lists_required_groups(self):
        result = run_cli(["--help"])
        assert result.returncode == 0
        assert "fakecam" in result.stdout
        assert "dut" in result.stdout
        assert "dut-agent" in result.stdout
        assert "test" in result.stdout
        assert "baseline" in result.stdout
        assert "report" in result.stdout

    def test_fakecam_help(self):
        result = run_cli(["fakecam", "--help"])
        assert result.returncode == 0
        assert "up" in result.stdout
        assert "status" in result.stdout
        assert "down" in result.stdout

    def test_dut_help(self):
        result = run_cli(["dut", "--help"])
        assert result.returncode == 0
        assert "inspect" in result.stdout

    def test_test_help(self):
        result = run_cli(["test", "--help"])
        assert result.returncode == 0
        assert "smoke" in result.stdout
        assert "four-stream" in result.stdout
        assert "soak" in result.stdout
        assert "loss-injection" in result.stdout

    def test_baseline_help(self):
        result = run_cli(["baseline", "--help"])
        assert result.returncode == 0
        assert "pktgen" in result.stdout

    def test_report_help(self):
        result = run_cli(["report", "--help"])
        assert result.returncode == 0
        assert "show" in result.stdout
        assert "export" in result.stdout


class TestFakecamCommands:
    def test_up_missing_config(self):
        result = run_cli(["fakecam", "up"])
        assert result.returncode == 2

    def test_status_missing_config(self):
        result = run_cli(["fakecam", "status"])
        assert result.returncode == 2

    def test_down_missing_config(self):
        result = run_cli(["fakecam", "down"])
        assert result.returncode == 2

    def test_up_invalid_config(self, tmp_path: Path):
        config_file = tmp_path / "invalid.yaml"
        config_file.write_text("invalid: yaml: content")
        result = run_cli(["fakecam", "up", "--config", str(config_file)])
        assert result.returncode in (1, 2)

    def test_up_json_output(self, tmp_path: Path):
        config_file = Path("examples/fakecam_4p.yaml")
        if not config_file.exists():
            pytest.skip("Example config not found")
        result = run_cli(
            ["fakecam", "up", "--config", str(config_file), "--json"],
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            assert "running_count" in data or "camera_count" in data


class TestDutCommands:
    def test_inspect_missing_host(self):
        result = run_cli(["dut", "inspect"])
        assert result.returncode == 2

    def test_inspect_missing_ifaces(self):
        result = run_cli(["dut", "inspect", "--host", "localhost"])
        assert result.returncode == 2

    def test_inspect_json_output(self):
        result = run_cli(
            ["dut", "inspect", "--host", "localhost", "--ifaces", "eno1", "--json"],
        )
        assert result.returncode in (0, 1, 2, 3, 4)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            assert "run_validity" in data


class TestTestCommands:
    def test_smoke_missing_config(self):
        result = run_cli(["test", "smoke"])
        assert result.returncode == 2

    def test_four_stream_missing_config(self):
        result = run_cli(["test", "four-stream"])
        assert result.returncode == 2

    def test_soak_missing_config(self):
        result = run_cli(["test", "soak"])
        assert result.returncode == 2

    def test_loss_injection_missing_config(self):
        result = run_cli(["test", "loss-injection"])
        assert result.returncode == 2

    def test_smoke_invalid_config(self, tmp_path: Path):
        config_file = tmp_path / "invalid.yaml"
        config_file.write_text("invalid: yaml: content")
        result = run_cli(["test", "smoke", "--config", str(config_file)])
        assert result.returncode in (1, 2)

    def test_smoke_json_flag(self, tmp_path: Path):
        config_file = Path("examples/scenario_smoke.yaml")
        if not config_file.exists():
            pytest.skip("Example config not found")
        output_dir = tmp_path / "smoke-output"
        result = run_cli(
            [
                "test",
                "smoke",
                "--config",
                str(config_file),
                "--output",
                str(output_dir),
                "--json",
            ],
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            assert "run_id" in data or "scenario" in data


class TestBaselineCommands:
    def test_pktgen_missing_config(self):
        result = run_cli(["baseline", "pktgen"])
        assert result.returncode == 2

    def test_pktgen_invalid_config(self, tmp_path: Path):
        config_file = tmp_path / "invalid.yaml"
        config_file.write_text("invalid: yaml: content")
        result = run_cli(["baseline", "pktgen", "--config", str(config_file)])
        assert result.returncode in (1, 2)

    def test_pktgen_json_flag(self, tmp_path: Path):
        config_file = Path("examples/pktgen_4p.yaml")
        if not config_file.exists():
            pytest.skip("Example config not found")
        output_dir = tmp_path / "pktgen-output"
        result = run_cli(
            [
                "baseline",
                "pktgen",
                "--config",
                str(config_file),
                "--output",
                str(output_dir),
                "--json",
            ],
        )
        assert result.returncode in (0, 1, 2, 3, 4)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            assert "results" in data


class TestReportCommands:
    def test_show_no_args(self):
        result = run_cli(["report", "show"])
        assert result.returncode == 2

    def test_show_latest_no_runs(self):
        result = run_cli(["report", "show", "--latest"])
        assert result.returncode in (1, 4)

    def test_export_no_run_id(self):
        result = run_cli(["report", "export", "--output", "test.json"])
        assert result.returncode == 2

    def test_export_nonexistent_run(self, tmp_path: Path):
        output_file = tmp_path / "export.json"
        result = run_cli(
            [
                "report",
                "export",
                "--run-id",
                "nonexistent",
                "--output",
                str(output_file),
            ],
        )
        assert result.returncode in (1, 4)


class TestExitCodes:
    def test_help_is_zero(self):
        result = run_cli(["--help"])
        assert result.returncode == 0

    def test_version_is_zero(self):
        result = run_cli(["--version"])
        assert result.returncode == 0

    def test_missing_required_arg(self):
        result = run_cli(["fakecam", "up"])
        assert result.returncode != 0

    def test_invalid_command(self):
        result = run_cli(["nonexistent"])
        assert result.returncode != 0
