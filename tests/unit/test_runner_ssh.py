from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from gvstress.core.runner import SSHRunner


def test_ssh_runner_forms_explicit_host_user_and_port_options() -> None:
    runner = SSHRunner(host="dut-lab", user="operator", port=2222)

    argv = runner.build_ssh_argv(
        "python", ["-m", "gvstress", "dut-agent", "ping", "--json"]
    )

    assert argv == [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-p",
        "2222",
        "-l",
        "operator",
        "dut-lab",
        "--",
        "python",
        "-m",
        "gvstress",
        "dut-agent",
        "ping",
        "--json",
    ]


def test_ssh_runner_delegates_to_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(
        argv: list[str],
        *,
        capture_output: bool,
        text: bool,
        timeout: float | None,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        captured["argv"] = argv
        captured["capture_output"] = capture_output
        captured["text"] = text
        captured["timeout"] = timeout
        captured["check"] = check
        return subprocess.CompletedProcess(
            argv, 0, stdout='{"status":"ok"}\n', stderr=""
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    runner = SSHRunner(host="dut-lab", user="operator", port=2222)

    result = runner.run(
        "python", ["-m", "gvstress", "dut-agent", "ping", "--json"], timeout=3
    )

    assert captured["argv"] == [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-p",
        "2222",
        "-l",
        "operator",
        "dut-lab",
        "--",
        "python",
        "-m",
        "gvstress",
        "dut-agent",
        "ping",
        "--json",
    ]
    assert captured["capture_output"] is True
    assert captured["text"] is True
    assert captured["timeout"] == 3
    assert captured["check"] is False
    assert result.exit_code == 0
    assert result.stdout == '{"status":"ok"}\n'
    assert result.timed_out is False


def test_ssh_timeout_is_structured_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fake_run(
        argv: list[str],
        *,
        capture_output: bool,
        text: bool,
        timeout: float | None,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        _ = capture_output
        _ = text
        _ = check
        raise subprocess.TimeoutExpired(
            cmd=argv, timeout=timeout or 0.5, output="partial", stderr=""
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    runner = SSHRunner(
        host="dut-lab",
        user="operator",
        port=22,
        transcript_path=tmp_path / "ssh.jsonl",
    )

    result = runner.run(
        "python", ["-m", "gvstress", "dut-agent", "ping", "--json"], timeout=0.5
    )

    assert result.command == "ssh"
    assert result.exit_code == 124
    assert result.stdout == "partial"
    assert result.stderr == "Command timed out after 0.5 seconds"
    assert result.timed_out is True
    assert "Traceback" not in result.stderr
