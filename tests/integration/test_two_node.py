"""Tests for two-node orchestration."""

import pytest

from gvstress.controller.two_node import (
    TwoNodeJob,
    TwoNodeOrchestrator,
    TwoNodeStatus,
)
from gvstress.web.domain import NodeEndpoint, NodeHealthStatus, NodeRole, TestTopology, TopologyMode


class TestTwoNodeOrchestrator:
    """Test two-node orchestration."""

    def test_create_job(self):
        """Can create a two-node job."""
        orch = TwoNodeOrchestrator()
        sender = NodeEndpoint(
            id="sender",
            role=NodeRole.SENDER,
            url="http://sender:8080",
            health_status=NodeHealthStatus.OK,
            created_at="2026-01-01T00:00:00Z",
            last_seen_at="2026-01-01T00:00:00Z",
        )
        receiver = NodeEndpoint(
            id="receiver",
            role=NodeRole.RECEIVER,
            url="http://receiver:8080",
            health_status=NodeHealthStatus.OK,
            created_at="2026-01-01T00:00:00Z",
            last_seen_at="2026-01-01T00:00:00Z",
        )
        topology = TestTopology(
            mode=TopologyMode.TWO_NODE,
            sender=sender,
            receiver=receiver,
        )
        job = orch.create_job(topology)
        assert job.id is not None
        assert job.status == TwoNodeStatus.PENDING

    def test_validate_topology_valid(self):
        """Validation passes with both nodes."""
        orch = TwoNodeOrchestrator()
        sender = NodeEndpoint(
            id="sender",
            role=NodeRole.SENDER,
            url="http://sender:8080",
            health_status=NodeHealthStatus.OK,
            created_at="2026-01-01T00:00:00Z",
            last_seen_at="2026-01-01T00:00:00Z",
        )
        receiver = NodeEndpoint(
            id="receiver",
            role=NodeRole.RECEIVER,
            url="http://receiver:8080",
            health_status=NodeHealthStatus.OK,
            created_at="2026-01-01T00:00:00Z",
            last_seen_at="2026-01-01T00:00:00Z",
        )
        topology = TestTopology(
            mode=TopologyMode.TWO_NODE,
            sender=sender,
            receiver=receiver,
        )
        valid, error = orch.validate_topology(topology)
        assert valid
        assert error == ""

    def test_list_jobs(self):
        """Can list all jobs."""
        orch = TwoNodeOrchestrator()
        sender = NodeEndpoint(
            id="sender",
            role=NodeRole.SENDER,
            url="http://sender:8080",
            health_status=NodeHealthStatus.OK,
            created_at="2026-01-01T00:00:00Z",
            last_seen_at="2026-01-01T00:00:00Z",
        )
        receiver = NodeEndpoint(
            id="receiver",
            role=NodeRole.RECEIVER,
            url="http://receiver:8080",
            health_status=NodeHealthStatus.OK,
            created_at="2026-01-01T00:00:00Z",
            last_seen_at="2026-01-01T00:00:00Z",
        )
        topology = TestTopology(
            mode=TopologyMode.TWO_NODE,
            sender=sender,
            receiver=receiver,
        )
        job = orch.create_job(topology)
        jobs = orch.list_jobs()
        assert len(jobs) == 1
        assert jobs[0].id == job.id

    def test_get_job(self):
        """Can get job by ID."""
        orch = TwoNodeOrchestrator()
        sender = NodeEndpoint(
            id="sender",
            role=NodeRole.SENDER,
            url="http://sender:8080",
            health_status=NodeHealthStatus.OK,
            created_at="2026-01-01T00:00:00Z",
            last_seen_at="2026-01-01T00:00:00Z",
        )
        receiver = NodeEndpoint(
            id="receiver",
            role=NodeRole.RECEIVER,
            url="http://receiver:8080",
            health_status=NodeHealthStatus.OK,
            created_at="2026-01-01T00:00:00Z",
            last_seen_at="2026-01-01T00:00:00Z",
        )
        topology = TestTopology(
            mode=TopologyMode.TWO_NODE,
            sender=sender,
            receiver=receiver,
        )
        job = orch.create_job(topology)
        retrieved = orch.get_job(job.id)
        assert retrieved is not None
        assert retrieved.id == job.id

    def test_complete_job(self):
        """Can mark job as completed."""
        orch = TwoNodeOrchestrator()
        sender = NodeEndpoint(
            id="sender",
            role=NodeRole.SENDER,
            url="http://sender:8080",
            health_status=NodeHealthStatus.OK,
            created_at="2026-01-01T00:00:00Z",
            last_seen_at="2026-01-01T00:00:00Z",
        )
        receiver = NodeEndpoint(
            id="receiver",
            role=NodeRole.RECEIVER,
            url="http://receiver:8080",
            health_status=NodeHealthStatus.OK,
            created_at="2026-01-01T00:00:00Z",
            last_seen_at="2026-01-01T00:00:00Z",
        )
        topology = TestTopology(
            mode=TopologyMode.TWO_NODE,
            sender=sender,
            receiver=receiver,
        )
        job = orch.create_job(topology)
        orch.complete_job(job.id)
        assert job.status == TwoNodeStatus.COMPLETED

    def test_fail_job(self):
        """Can mark job as failed."""
        orch = TwoNodeOrchestrator()
        sender = NodeEndpoint(
            id="sender",
            role=NodeRole.SENDER,
            url="http://sender:8080",
            health_status=NodeHealthStatus.OK,
            created_at="2026-01-01T00:00:00Z",
            last_seen_at="2026-01-01T00:00:00Z",
        )
        receiver = NodeEndpoint(
            id="receiver",
            role=NodeRole.RECEIVER,
            url="http://receiver:8080",
            health_status=NodeHealthStatus.OK,
            created_at="2026-01-01T00:00:00Z",
            last_seen_at="2026-01-01T00:00:00Z",
        )
        topology = TestTopology(
            mode=TopologyMode.TWO_NODE,
            sender=sender,
            receiver=receiver,
        )
        job = orch.create_job(topology)
        orch.fail_job(job.id, "Test error")
        assert job.status == TwoNodeStatus.FAILED
        assert job.error_message == "Test error"
