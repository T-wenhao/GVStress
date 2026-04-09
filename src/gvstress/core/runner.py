from __future__ import annotations

import json
import subprocess
import time
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

TIMEOUT_EXIT_CODE = 124


@dataclass(slots=True)
class CommandResult:
    command: str
    argv: list[str]
    exit_code: int
    stdout: str
    stderr: str
    duration: float
    timed_out: bool

    def to_json_line(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)


class CommandRunner(ABC):
    def __init__(self, transcript_path: str | Path | None = None) -> None:
        self._transcript_path: Path | None = (
            Path(transcript_path) if transcript_path else None
        )

    @abstractmethod
    def run(
        self,
        command: str,
        argv: Sequence[str] | None = None,
        *,
        timeout: float | None = None,
    ) -> CommandResult:
        raise NotImplementedError

    def _record_transcript(self, result: CommandResult) -> None:
        if self._transcript_path is None:
            return

        self._transcript_path.parent.mkdir(parents=True, exist_ok=True)
        with self._transcript_path.open("a", encoding="utf-8") as transcript_file:
            transcript_file.write(f"{result.to_json_line()}\n")

    def _run_subprocess(
        self, argv: Sequence[str], *, timeout: float | None = None
    ) -> CommandResult:
        start = time.monotonic()
        try:
            completed = subprocess.run(
                list(argv),
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            duration = time.monotonic() - start
            stdout = _normalize_output(exc.stdout)
            stderr = _normalize_output(exc.stderr)
            result = CommandResult(
                command=argv[0],
                argv=list(argv),
                exit_code=TIMEOUT_EXIT_CODE,
                stdout=stdout,
                stderr=stderr or f"Command timed out after {timeout} seconds",
                duration=duration,
                timed_out=True,
            )
            self._record_transcript(result)
            return result

        duration = time.monotonic() - start
        result = CommandResult(
            command=argv[0],
            argv=list(argv),
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            duration=duration,
            timed_out=False,
        )
        self._record_transcript(result)
        return result


class LocalRunner(CommandRunner):
    def run(
        self,
        command: str,
        argv: Sequence[str] | None = None,
        *,
        timeout: float | None = None,
    ) -> CommandResult:
        full_argv = [command, *(list(argv) if argv is not None else [])]
        return self._run_subprocess(full_argv, timeout=timeout)


class SSHRunner(CommandRunner):
    def __init__(
        self,
        host: str,
        *,
        user: str,
        port: int = 22,
        transcript_path: str | Path | None = None,
        ssh_bin: str = "ssh",
    ) -> None:
        super().__init__(transcript_path=transcript_path)
        self.host: str = host
        self.user: str = user
        self.port: int = port
        self.ssh_bin: str = ssh_bin

    def build_ssh_argv(
        self, command: str, argv: Sequence[str] | None = None
    ) -> list[str]:
        remote_argv = [command, *(list(argv) if argv is not None else [])]
        return [
            self.ssh_bin,
            "-o",
            "BatchMode=yes",
            "-p",
            str(self.port),
            "-l",
            self.user,
            self.host,
            "--",
            *remote_argv,
        ]

    def run(
        self,
        command: str,
        argv: Sequence[str] | None = None,
        *,
        timeout: float | None = None,
    ) -> CommandResult:
        return self._run_subprocess(self.build_ssh_argv(command, argv), timeout=timeout)


def _normalize_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode()
    return value
