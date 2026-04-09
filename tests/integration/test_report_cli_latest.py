from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import cast

CLI_ENTRY = [sys.executable, "-m", "gvstress"]


def run_cli(
    args: list[str], *, check: bool = False
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*CLI_ENTRY, *args],
        capture_output=True,
        text=True,
        check=check,
    )


def _write_run_artifact(root: Path, run_id: str, *, verdict: str) -> Path:
    run_root = root / run_id
    reports_dir = run_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": run_id,
        "verdict": verdict,
        "scenario": {"name": "smoke"},
    }
    _ = (reports_dir / "run.json").write_text(json.dumps(payload), encoding="utf-8")
    _ = (reports_dir / "summary.md").write_text(
        f"# Summary for {run_id}\n", encoding="utf-8"
    )
    return run_root


def test_show_latest_reads_actual_run_root(tmp_path: Path) -> None:
    artifacts_root = tmp_path / "artifacts"
    older_run = _write_run_artifact(artifacts_root, "run-001", verdict="warn")
    latest_run = _write_run_artifact(artifacts_root, "run-002", verdict="pass")

    older_mtime = older_run.stat().st_mtime - 10
    latest_mtime = latest_run.stat().st_mtime
    os.utime(older_run, (older_mtime, older_mtime))
    os.utime(latest_run, (latest_mtime + 10, latest_mtime + 10))

    result = run_cli(
        ["report", "show", "--latest", "--json", "--source", str(artifacts_root)]
    )

    assert result.returncode == 0, result.stderr
    payload = cast(dict[str, object], json.loads(result.stdout))
    assert payload["run_id"] == "run-002"
    assert payload["verdict"] == "pass"


def test_export_reads_actual_run_root(tmp_path: Path) -> None:
    artifacts_root = tmp_path / "artifacts"
    _ = _write_run_artifact(artifacts_root, "run-123", verdict="fail")
    export_path = tmp_path / "exports" / "run-123.json"

    result = run_cli(
        [
            "report",
            "export",
            "--run-id",
            "run-123",
            "--source",
            str(artifacts_root),
            "--output",
            str(export_path),
        ]
    )

    assert result.returncode == 0, result.stderr
    assert export_path.exists()
    payload = cast(
        dict[str, object], json.loads(export_path.read_text(encoding="utf-8"))
    )
    assert payload["run_id"] == "run-123"
    assert payload["verdict"] == "fail"
