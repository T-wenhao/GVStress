"""JSON file-based job storage with crash recovery."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field


class JobStatus(str, Enum):
    """Job lifecycle states."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class JobRecord(BaseModel):
    """Persistent job record."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    name: str
    status: JobStatus = JobStatus.PENDING
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    result: dict[str, Any] | None = None
    error: str | None = None


class JobStore:
    """File-backed JSON store for job records."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self._file = data_dir / "jobs.json"
        self._jobs: dict[str, JobRecord] = {}
        self._load()

    def _load(self) -> None:
        """Load jobs from disk, creating file if missing."""
        if self._file.exists():
            raw = json.loads(self._file.read_text(encoding="utf-8"))
            self._jobs = {j["id"]: JobRecord(**j) for j in raw}
        else:
            self._data_dir = self.data_dir
            self.data_dir.mkdir(parents=True, exist_ok=True)
            self._persist()

    def _persist(self) -> None:
        """Write all jobs to disk atomically."""
        records = [j.model_dump() for j in self._jobs.values()]
        tmp = self._file.with_suffix(".tmp")
        tmp.write_text(json.dumps(records, indent=2), encoding="utf-8")
        tmp.replace(self._file)

    def create(self, name: str) -> JobRecord:
        """Create a new pending job."""
        job = JobRecord(name=name)
        self._jobs[job.id] = job
        self._persist()
        return job

    def get(self, job_id: str) -> JobRecord | None:
        """Get a job by ID."""
        return self._jobs.get(job_id)

    def list_all(self) -> list[JobRecord]:
        """Return all jobs."""
        return list(self._jobs.values())

    def update_status(self, job_id: str, status: JobStatus, *, result: dict[str, Any] | None = None, error: str | None = None) -> JobRecord | None:
        """Update job status and persist."""
        job = self._jobs.get(job_id)
        if job is None:
            return None
        job.status = status
        job.updated_at = datetime.now(timezone.utc).isoformat()
        if result is not None:
            job.result = result
        if error is not None:
            job.error = error
        self._persist()
        return job
