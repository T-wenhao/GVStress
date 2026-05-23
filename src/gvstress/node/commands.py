"""Safe command execution for node service."""

import shutil
import subprocess
from pathlib import Path
from typing import Any


class CommandError(Exception):
    """Command execution error."""

    pass


class CommandExecutor:
    """Execute whitelisted commands safely."""

    # Whitelisted commands and their allowed arguments
    ALLOWED_COMMANDS: dict[str, dict[str, Any]] = {
        "ip": {
            "subcommands": ["link", "addr"],
            "args": ["show"],
        },
        "ethtool": {
            "subcommands": [],
            "args": ["-S"],
        },
        "cat": {
            "subcommands": [],
            "args": [],
            "paths": ["/proc/net/pktgen/*", "/sys/class/net/*"],
        },
    }

    def __init__(self) -> None:
        self._history: list[dict[str, Any]] = []

    def validate_command(self, cmd: list[str]) -> bool:
        """Validate command against whitelist."""
        if not cmd:
            return False

        executable = cmd[0]
        blocked_tokens = (";", "&&", "||", "|", "`", "$(", ">", "<")
        if any(token in arg for arg in cmd for token in blocked_tokens):
            return False

        # Check if command is in whitelist
        if executable not in self.ALLOWED_COMMANDS:
            return False

        config = self.ALLOWED_COMMANDS[executable]

        # Validate subcommands if specified
        if config.get("subcommands") and len(cmd) > 1:
            if cmd[1] not in config["subcommands"]:
                return False

        # Validate arguments
        allowed_literals = set(config.get("subcommands", [])) | set(config.get("args", []))
        for index, arg in enumerate(cmd[1:], start=1):
            if arg.startswith("-"):
                if config.get("args"):
                    if arg not in config["args"]:
                        return False
                else:
                    return False
            elif arg.startswith("/"):
                # Validate paths
                if config.get("paths"):
                    allowed = any(
                        Path(arg).match(pattern.replace("*", "**"))
                        for pattern in config["paths"]
                    )
                    if not allowed:
                        return False
                else:
                    return False
            elif executable == "ethtool" and index == 2 and cmd[1] == "-S":
                # Interface names are positional and host-specific.
                continue
            elif allowed_literals and arg not in allowed_literals:
                return False
            elif not allowed_literals:
                return False

        return True

    def execute(self, cmd: list[str], timeout: int = 30) -> dict[str, Any]:
        """Execute a validated command."""
        if not self.validate_command(cmd):
            raise CommandError(f"Command not allowed: {cmd}")

        if shutil.which(cmd[0]) is None:
            result = {
                "success": False,
                "stdout": "",
                "stderr": f"Command not found: {cmd[0]}",
                "returncode": 127,
            }
            self._history.append({
                "command": cmd,
                "returncode": result["returncode"],
                "success": result["success"],
            })
            return result

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )

            self._history.append({
                "command": cmd,
                "returncode": result.returncode,
                "success": result.returncode == 0,
            })

            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            raise CommandError(f"Command timed out after {timeout}s: {cmd}")
        except Exception as e:
            raise CommandError(f"Command failed: {e}")

    def get_history(self) -> list[dict[str, Any]]:
        """Get command execution history."""
        return self._history.copy()
