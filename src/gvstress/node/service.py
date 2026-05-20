"""Node service core logic."""

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class NodeCapabilities(BaseModel):
    """Node capabilities report."""

    interfaces: list[str] = Field(default_factory=list)
    pktgen_available: bool = False
    has_net_admin: bool = False
    version: str = "0.1.0"


class NodeStatus(BaseModel):
    """Node health status."""

    status: str = "ok"
    pid: int = Field(default_factory=os.getpid)
    uptime_seconds: float = 0.0


class NodeService:
    """Local node service for test control and monitoring."""

    def __init__(self, config_path: Path | None = None) -> None:
        self.config_path = config_path
        self._start_time = __import__("time").time()

    def health(self) -> NodeStatus:
        """Return node health status."""
        import time

        return NodeStatus(
            status="ok",
            uptime_seconds=time.time() - self._start_time,
        )

    def capabilities(self) -> NodeCapabilities:
        """Detect and return node capabilities."""
        caps = NodeCapabilities()

        # Detect network interfaces
        try:
            result = subprocess.run(
                ["ip", "link", "show"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                caps.interfaces = [
                    line.split(":")[1].strip()
                    for line in result.stdout.split("\n")
                    if ":" in line and "lo:" not in line
                ][:10]  # Limit to first 10 non-loopback interfaces
        except Exception:
            pass

        # Check pktgen availability
        caps.pktgen_available = Path("/proc/net/pktgen").exists()

        # Check for CAP_NET_ADMIN (simplified check)
        caps.has_net_admin = os.geteuid() == 0

        return caps

    def get_status(self) -> dict[str, Any]:
        """Get full node status."""
        return {
            "health": self.health().dict(),
            "capabilities": self.capabilities().dict(),
        }
