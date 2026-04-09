from __future__ import annotations

import json
import sys
from pathlib import Path

from gvstress.core.runner import LocalRunner


def test_local_runner_returns_structured_result() -> None:
    runner = LocalRunner()

    result = runner.run(
        sys.executable,
        ["-c", "print('hello from local')"],
        timeout=5,
    )

    assert result.command == sys.executable
    assert result.argv == [sys.executable, "-c", "print('hello from local')"]
    assert result.exit_code == 0
    assert result.stdout == "hello from local\n"
    assert result.stderr == ""
    assert result.duration >= 0
    assert result.timed_out is False


def test_local_runner_records_jsonl_transcript(tmp_path: Path) -> None:
    transcript_path = tmp_path / "transcripts" / "commands.jsonl"
    runner = LocalRunner(transcript_path=transcript_path)

    result = runner.run(sys.executable, ["-c", "print('logged')"], timeout=5)

    lines = transcript_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["command"] == result.command
    assert payload["argv"] == result.argv
    assert payload["stdout"] == result.stdout
    assert payload["timed_out"] is False


def test_local_runner_timeout_returns_structured_failure() -> None:
    runner = LocalRunner()

    result = runner.run(
        sys.executable,
        ["-c", "import time; time.sleep(0.2)"],
        timeout=0.01,
    )

    assert result.exit_code == 124
    assert result.timed_out is True
    assert "timed out" in result.stderr.lower()
