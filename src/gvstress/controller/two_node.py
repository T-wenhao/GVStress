"""Two-node orchestration for GVStress."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import requests

from gvstress.web.domain import NodeEndpoint, NodeRole, TestTopology


class TwoNodeStatus(Enum):
    """Status of two-node orchestration."""

    PENDING = "pending"
    HEALTH_CHECKING = "health_checking"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TwoNodeJob:
    """Two-node test job."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sender: NodeEndpoint | None = None
    receiver: NodeEndpoint | None = None
    status: TwoNodeStatus = TwoNodeStatus.PENDING
    sender_health: dict[str, Any] = field(default_factory=dict)
    receiver_health: dict[str, Any] = field(default_factory=dict)
    error_message: str = ""


class TwoNodeOrchestrator:
    """Orchestrate tests across two nodes."""

    def __init__(self) -> None:
        self.jobs: dict[str, TwoNodeJob] = {}

    def create_job(self, topology: TestTopology) -> TwoNodeJob:
        """Create a new two-node job."""
        job = TwoNodeJob()

        # Extract sender and receiver from topology
        if topology.sender:
            job.sender = topology.sender
        if topology.receiver:
            job.receiver = topology.receiver

        self.jobs[job.id] = job
        return job

    def check_node_health(self, node: NodeEndpoint) -> dict[str, Any]:
        """Check health of a node."""
        try:
            response = requests.get(
                f"{node.url}/health",
                timeout=5,
            )
            response.raise_for_status()
            return {"healthy": True, "data": response.json()}
        except Exception as e:
            return {"healthy": False, "error": str(e)}

    def validate_topology(self, topology: TestTopology) -> tuple[bool, str]:
        """Validate topology has required nodes."""
        if topology.mode.value == "single_node":
            if topology.sender is None:
                return False, "Topology missing sender node"
            return True, ""

        # Two node mode
        if topology.sender is None:
            return False, "Topology missing sender node"
        if topology.receiver is None:
            return False, "Topology missing receiver node"

        return True, ""

    def start_job(self, job_id: str) -> TwoNodeJob:
        """Start a two-node job."""
        job = self.jobs.get(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        job.status = TwoNodeStatus.HEALTH_CHECKING

        # Check sender health
        if job.sender:
            job.sender_health = self.check_node_health(job.sender)
            if not job.sender_health.get("healthy"):
                job.status = TwoNodeStatus.FAILED
                job.error_message = f"Sender health check failed: {job.sender_health.get('error')}"
                return job

        # Check receiver health
        if job.receiver:
            job.receiver_health = self.check_node_health(job.receiver)
            if not job.receiver_health.get("healthy"):
                job.status = TwoNodeStatus.FAILED
                job.error_message = f"Receiver health check failed: {job.receiver_health.get('error')}"
                return job

        job.status = TwoNodeStatus.RUNNING
        return job

    def get_job(self, job_id: str) -> TwoNodeJob | None:
        """Get job by ID."""
        return self.jobs.get(job_id)

    def list_jobs(self) -> list[TwoNodeJob]:
        """List all jobs."""
        return list(self.jobs.values())

    def complete_job(self, job_id: str) -> TwoNodeJob:
        """Mark job as completed."""
        job = self.jobs.get(job_id)
        if job:
            job.status = TwoNodeStatus.COMPLETED
        return job

    def fail_job(self, job_id: str, error: str) -> TwoNodeJob:
        """Mark job as failed."""
        job = self.jobs.get(job_id)
        if job:
            job.status = TwoNodeStatus.FAILED
            job.error_message = error
        return job
