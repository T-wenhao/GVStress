# pyright: reportMissingImports=false, reportMissingTypeStubs=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnannotatedClassAttribute=false, reportReturnType=false, reportIndexIssue=false, reportArgumentType=false, reportAny=false

from __future__ import annotations

import json
from pathlib import Path

from gvstress.controller.service import ControllerService
from gvstress.controller.store import JobStatus


def test_create_job_returns_pending(tmp_path: Path) -> None:
    service = ControllerService(tmp_path)
    job = service.create_job("test-job")

    assert job.name == "test-job"
    assert job.status == JobStatus.PENDING
    assert job.id is not None
    assert job.result is None
    assert job.error is None


def test_get_job_by_id(tmp_path: Path) -> None:
    service = ControllerService(tmp_path)
    created = service.create_job("lookup-job")

    found = service.get_job(created.id)
    assert found is not None
    assert found.id == created.id
    assert found.name == "lookup-job"


def test_get_job_missing_returns_none(tmp_path: Path) -> None:
    service = ControllerService(tmp_path)
    assert service.get_job("nonexistent") is None


def test_list_jobs(tmp_path: Path) -> None:
    service = ControllerService(tmp_path)
    service.create_job("job-a")
    service.create_job("job-b")

    jobs = service.list_jobs()
    assert len(jobs) == 2
    names = {j.name for j in jobs}
    assert names == {"job-a", "job-b"}


def test_job_lifecycle_transitions(tmp_path: Path) -> None:
    service = ControllerService(tmp_path)
    job = service.create_job("lifecycle-job")

    running = service.start_job(job.id)
    assert running is not None
    assert running.status == JobStatus.RUNNING

    completed = service.complete_job(job.id, {"output": "done"})
    assert completed is not None
    assert completed.status == JobStatus.COMPLETED
    assert completed.result == {"output": "done"}


def test_fail_job(tmp_path: Path) -> None:
    service = ControllerService(tmp_path)
    job = service.create_job("fail-job")

    service.start_job(job.id)
    failed = service.fail_job(job.id, "something broke")

    assert failed is not None
    assert failed.status == JobStatus.FAILED
    assert failed.error == "something broke"


def test_persistence_survives_reinit(tmp_path: Path) -> None:
    service = ControllerService(tmp_path)
    job = service.create_job("persistent-job")
    service.start_job(job.id)

    service2 = ControllerService(tmp_path)
    restored = service2.get_job(job.id)

    assert restored is not None
    assert restored.id == job.id
    assert restored.status == JobStatus.RUNNING


def test_persistence_file_format(tmp_path: Path) -> None:
    service = ControllerService(tmp_path)
    service.create_job("format-job")

    jobs_file = tmp_path / "jobs.json"
    assert jobs_file.exists()

    raw = json.loads(jobs_file.read_text(encoding="utf-8"))
    assert isinstance(raw, list)
    assert len(raw) == 1
    assert raw[0]["name"] == "format-job"
    assert raw[0]["status"] == "pending"


def test_update_nonexistent_job_returns_none(tmp_path: Path) -> None:
    service = ControllerService(tmp_path)
    assert service.start_job("ghost-id") is None
    assert service.complete_job("ghost-id", {}) is None
    assert service.fail_job("ghost-id", "err") is None
