# pyright: reportMissingImports=false, reportMissingTypeStubs=false

from __future__ import annotations

import json
from pathlib import Path

from gvstress.report.indexer import scan_reports


def _write_run_json(directory: Path, run_id: str, timestamp: str, verdict: str) -> None:
    reports_dir = directory / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / "run.json"
    path.write_text(
        json.dumps({"run_id": run_id, "timestamp": timestamp, "verdict": verdict}),
        encoding="utf-8",
    )


class TestScanReports:
    def test_empty_directory(self, tmp_path: Path) -> None:
        result = scan_reports(tmp_path)
        assert result.entries == []
        assert result.total == 0
        assert result.has_more is False

    def test_nonexistent_directory(self) -> None:
        result = scan_reports("/nonexistent/path/that/does/not/exist")
        assert result.entries == []
        assert result.total == 0

    def test_single_run_json(self, tmp_path: Path) -> None:
        scenario_dir = tmp_path / "smoke" / "runs" / "abc123"
        _write_run_json(scenario_dir, "abc123", "2025-01-01T00:00:00Z", "pass")

        result = scan_reports(tmp_path)
        assert result.total == 1
        assert len(result.entries) == 1
        assert result.entries[0].run_id == "abc123"
        assert result.entries[0].verdict == "pass"

    def test_multiple_runs_sorted_by_timestamp_desc(self, tmp_path: Path) -> None:
        _write_run_json(
            tmp_path / "smoke" / "runs" / "run1",
            "run1", "2025-01-01T00:00:00Z", "pass",
        )
        _write_run_json(
            tmp_path / "soak" / "runs" / "run2",
            "run2", "2025-06-01T00:00:00Z", "warn",
        )
        _write_run_json(
            tmp_path / "loss" / "runs" / "run3",
            "run3", "2025-03-01T00:00:00Z", "fail",
        )

        result = scan_reports(tmp_path)
        assert result.total == 3
        ids = [e.run_id for e in result.entries]
        assert ids == ["run2", "run3", "run1"]

    def test_corrupted_json_is_skipped(self, tmp_path: Path) -> None:
        _write_run_json(
            tmp_path / "smoke" / "runs" / "good",
            "good", "2025-01-01T00:00:00Z", "pass",
        )
        bad_dir = tmp_path / "bad" / "runs" / "corrupt" / "reports"
        bad_dir.mkdir(parents=True, exist_ok=True)
        (bad_dir / "run.json").write_text("not valid json{{{", encoding="utf-8")

        result = scan_reports(tmp_path)
        assert result.total == 1
        assert result.entries[0].run_id == "good"

    def test_missing_fields_is_skipped(self, tmp_path: Path) -> None:
        _write_run_json(
            tmp_path / "smoke" / "runs" / "good",
            "good", "2025-01-01T00:00:00Z", "pass",
        )
        bad_dir = tmp_path / "bad" / "runs" / "partial" / "reports"
        bad_dir.mkdir(parents=True, exist_ok=True)
        (bad_dir / "run.json").write_text(
            json.dumps({"run_id": "partial", "timestamp": "2025-01-01T00:00:00Z"}),
            encoding="utf-8",
        )

        result = scan_reports(tmp_path)
        assert result.total == 1

    def test_pagination_offset(self, tmp_path: Path) -> None:
        for i in range(5):
            _write_run_json(
                tmp_path / f"scenario_{i}" / "runs" / f"run_{i}",
                f"run_{i}", f"2025-01-{i+1:02d}T00:00:00Z", "pass",
            )

        result = scan_reports(tmp_path, offset=2)
        assert result.total == 5
        assert len(result.entries) == 3
        assert result.entries[0].run_id == "run_2"

    def test_pagination_limit(self, tmp_path: Path) -> None:
        for i in range(10):
            _write_run_json(
                tmp_path / f"s_{i}" / "runs" / f"r_{i}",
                f"r_{i}", f"2025-01-{i+1:02d}T00:00:00Z", "pass",
            )

        result = scan_reports(tmp_path, limit=3)
        assert result.total == 10
        assert len(result.entries) == 3
        assert result.has_more is True

    def test_pagination_offset_and_limit(self, tmp_path: Path) -> None:
        for i in range(10):
            _write_run_json(
                tmp_path / f"s_{i}" / "runs" / f"r_{i}",
                f"r_{i}", f"2025-01-{i+1:02d}T00:00:00Z", "pass",
            )

        result = scan_reports(tmp_path, offset=5, limit=2)
        assert result.total == 10
        assert len(result.entries) == 2
        assert result.entries[0].run_id == "r_4"
        assert result.entries[1].run_id == "r_3"
        assert result.has_more is True

    def test_has_more_false_when_all_returned(self, tmp_path: Path) -> None:
        _write_run_json(
            tmp_path / "s" / "runs" / "r",
            "r", "2025-01-01T00:00:00Z", "pass",
        )
        result = scan_reports(tmp_path, limit=10)
        assert result.has_more is False

    def test_entry_contains_path(self, tmp_path: Path) -> None:
        scenario_dir = tmp_path / "smoke" / "runs" / "abc"
        _write_run_json(scenario_dir, "abc", "2025-01-01T00:00:00Z", "pass")
        expected_path = str(scenario_dir / "reports" / "run.json")

        result = scan_reports(tmp_path)
        assert result.entries[0].path == expected_path
