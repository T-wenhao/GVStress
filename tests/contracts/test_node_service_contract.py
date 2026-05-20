"""Contract tests for node service."""

import pytest

from gvstress.node.commands import CommandError, CommandExecutor
from gvstress.node.service import NodeCapabilities, NodeService, NodeStatus


class TestNodeServiceBasics:
    """Basic node service functionality."""

    def test_service_creation(self):
        """Service can be created."""
        service = NodeService()
        assert service is not None

    def test_health_returns_ok(self):
        """Health check returns ok status."""
        service = NodeService()
        health = service.health()
        assert health.status == "ok"
        assert health.pid > 0

    def test_health_returns_uptime(self):
        """Health includes uptime."""
        service = NodeService()
        health = service.health()
        assert health.uptime_seconds >= 0

    def test_capabilities_structure(self):
        """Capabilities has expected fields."""
        service = NodeService()
        caps = service.capabilities()
        assert hasattr(caps, "interfaces")
        assert hasattr(caps, "pktgen_available")
        assert hasattr(caps, "has_net_admin")
        assert hasattr(caps, "version")

    def test_capabilities_interfaces_is_list(self):
        """Interfaces is a list."""
        service = NodeService()
        caps = service.capabilities()
        assert isinstance(caps.interfaces, list)


class TestCommandExecutor:
    """Command executor security tests."""

    def test_executor_creation(self):
        """Executor can be created."""
        executor = CommandExecutor()
        assert executor is not None

    def test_validate_allowed_command(self):
        """Allowed commands pass validation."""
        executor = CommandExecutor()
        assert executor.validate_command(["ip", "link", "show"]) is True

    def test_validate_disallowed_command(self):
        """Disallowed commands fail validation."""
        executor = CommandExecutor()
        assert executor.validate_command(["rm", "-rf", "/"]) is False

    def test_validate_shell_injection_attempt(self):
        """Shell injection attempts are blocked."""
        executor = CommandExecutor()
        assert executor.validate_command(["ip", "link", "show", ";", "rm", "-rf", "/"]) is False

    def test_validate_empty_command(self):
        """Empty commands are rejected."""
        executor = CommandExecutor()
        assert executor.validate_command([]) is False

    def test_execute_raises_on_invalid(self):
        """Execute raises CommandError for invalid commands."""
        executor = CommandExecutor()
        with pytest.raises(CommandError):
            executor.execute(["rm", "-rf", "/"])

    def test_execute_allowed_command(self):
        """Execute runs allowed commands."""
        executor = CommandExecutor()
        result = executor.execute(["ip", "link", "show"])
        assert "success" in result
        assert "returncode" in result

    def test_history_tracks_executions(self):
        """History tracks command executions."""
        executor = CommandExecutor()
        executor.execute(["ip", "link", "show"])
        history = executor.get_history()
        assert len(history) == 1
        assert history[0]["command"] == ["ip", "link", "show"]


class TestNodeStatusModel:
    """NodeStatus model validation."""

    def test_default_status(self):
        """Default status is ok."""
        status = NodeStatus()
        assert status.status == "ok"

    def test_custom_status(self):
        """Status can be customized."""
        status = NodeStatus(status="degraded")
        assert status.status == "degraded"


class TestNodeCapabilitiesModel:
    """NodeCapabilities model validation."""

    def test_default_values(self):
        """Default values are sensible."""
        caps = NodeCapabilities()
        assert caps.interfaces == []
        assert caps.pktgen_available is False
        assert caps.has_net_admin is False
        assert caps.version == "0.1.0"

    def test_custom_values(self):
        """Values can be customized."""
        caps = NodeCapabilities(
            interfaces=["eth0", "eth1"],
            pktgen_available=True,
            has_net_admin=True,
        )
        assert caps.interfaces == ["eth0", "eth1"]
        assert caps.pktgen_available is True
        assert caps.has_net_admin is True
