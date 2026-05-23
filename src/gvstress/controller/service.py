"""Controller service for job lifecycle management."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .store import JobRecord, JobStatus, JobStore


class ControllerService:
    """High-level service orchestrating job creation and status queries."""

    def __init__(self, data_dir: Path) -> None:
        self.store = JobStore(data_dir)

    def create_job(self, name: str) -> JobRecord:
        """Create a new job in pending state."""
        return self.store.create(name=name)

    def get_job(self, job_id: str) -> JobRecord | None:
        """Query a job by ID."""
        return self.store.get(job_id)

    def list_jobs(self) -> list[JobRecord]:
        """List all jobs."""
        return self.store.list_all()

    def start_job(self, job_id: str) -> JobRecord | None:
        """Transition a job to running."""
        return self.store.update_status(job_id, JobStatus.RUNNING)

    def complete_job(self, job_id: str, result: dict[str, Any]) -> JobRecord | None:
        """Transition a job to completed with result."""
        return self.store.update_status(job_id, JobStatus.COMPLETED, result=result)

    def fail_job(self, job_id: str, error: str) -> JobRecord | None:
        """Transition a job to failed with error message."""
        return self.store.update_status(job_id, JobStatus.FAILED, error=error)
