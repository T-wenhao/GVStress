# pyright: reportMissingImports=false, reportMissingTypeStubs=false

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class RunIndexEntry:
    """A single entry in the report index."""

    run_id: str
    timestamp: str
    verdict: str
    path: str


@dataclass
class RunIndexResult:
    """Paginated result from scanning run.json files."""

    entries: list[RunIndexEntry]
    total: int
    offset: int
    limit: int

    @property
    def has_more(self) -> bool:
        return self.offset + self.limit < self.total


def _parse_entry(data: dict[str, Any], file_path: Path) -> RunIndexEntry:
    """Extract index fields from a run.json payload."""
    return RunIndexEntry(
        run_id=str(data["run_id"]),
        timestamp=str(data["timestamp"]),
        verdict=str(data["verdict"]),
        path=str(file_path),
    )


def _is_valid_run_json(data: dict[str, Any]) -> bool:
    """Check that required index fields exist."""
    return all(key in data for key in ("run_id", "timestamp", "verdict"))


def scan_reports(
    artifacts_root: str | Path,
    *,
    offset: int = 0,
    limit: int = 50,
) -> RunIndexResult:
    """Scan artifacts/**/reports/run.json files and return a paginated index.

    Files are sorted by timestamp descending. Corrupted or invalid run.json
    files are silently skipped.

    Args:
        artifacts_root: Root directory containing scenario subdirectories.
        offset: Number of entries to skip (for pagination).
        limit: Maximum number of entries to return.

    Returns:
        RunIndexResult with entries, total count, and pagination info.
    """
    root = Path(artifacts_root)
    if not root.is_dir():
        return RunIndexResult(entries=[], total=0, offset=offset, limit=limit)

    all_entries: list[RunIndexEntry] = []

    for run_json in sorted(root.glob("**/reports/run.json")):
        try:
            text = run_json.read_text(encoding="utf-8")
            data = json.loads(text)
            if not isinstance(data, dict) or not _is_valid_run_json(data):
                continue
            all_entries.append(_parse_entry(data, run_json))
        except (json.JSONDecodeError, OSError, KeyError, TypeError):
            continue

    all_entries.sort(key=lambda e: e.timestamp, reverse=True)

    total = len(all_entries)
    page = all_entries[offset : offset + limit]

    return RunIndexResult(entries=page, total=total, offset=offset, limit=limit)
