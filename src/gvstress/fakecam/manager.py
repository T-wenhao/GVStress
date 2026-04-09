from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gvstress.config.models import FakeCameraConfig, GeneratorConfig

from .worker import FakeCameraHealthSnapshot, FakeCameraWorker


class FakeCameraManager:
    def __init__(
        self,
        cameras: list[FakeCameraConfig],
        *,
        runtime_dir: str | Path,
        python_bin: str = "python3",
        health_interval: float = 1.0,
        startup_timeout: float = 5.0,
        stop_timeout: float = 5.0,
        env: dict[str, str] | None = None,
        launcher: Any | None = None,
    ) -> None:
        self.cameras = cameras
        self.runtime_dir = Path(runtime_dir)
        self.python_bin = python_bin
        self.health_interval = health_interval
        self.startup_timeout = startup_timeout
        self.stop_timeout = stop_timeout
        self.env = env
        self.launcher = launcher
        self._validate_unique_ips()
        self.workers = [self._build_worker(camera) for camera in cameras]

    @classmethod
    def from_generator_config(
        cls,
        generator: GeneratorConfig,
        *,
        runtime_dir: str | Path,
        python_bin: str = "python3",
        health_interval: float = 1.0,
        startup_timeout: float = 5.0,
        stop_timeout: float = 5.0,
        env: dict[str, str] | None = None,
        launcher: Any | None = None,
    ) -> FakeCameraManager:
        return cls(
            generator.cameras,
            runtime_dir=runtime_dir,
            python_bin=python_bin,
            health_interval=health_interval,
            startup_timeout=startup_timeout,
            stop_timeout=stop_timeout,
            env=env,
            launcher=launcher,
        )

    def up(self) -> dict[str, object]:
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.cleanup_orphans()
        started: list[FakeCameraHealthSnapshot] = []
        try:
            for worker in self.workers:
                started.append(worker.start())
        except Exception:
            _ = self.down()
            raise
        payload = self.status()
        payload["started"] = len(started)
        return payload

    def status(self) -> dict[str, object]:
        self.cleanup_orphans()
        snapshots = [
            worker.status() or worker._stopped_snapshot(pid=None)
            for worker in self.workers
        ]
        return {
            "runtime_dir": str(self.runtime_dir),
            "camera_count": len(snapshots),
            "running_count": sum(1 for snapshot in snapshots if snapshot.running),
            "cameras": [snapshot.to_dict() for snapshot in snapshots],
        }

    def down(self) -> dict[str, object]:
        snapshots: list[FakeCameraHealthSnapshot] = []
        for worker in self.workers:
            snapshots.append(worker.stop())
        self.cleanup_orphans()
        self._remove_empty_runtime_dirs()
        return {
            "runtime_dir": str(self.runtime_dir),
            "camera_count": len(snapshots),
            "stopped_count": len(snapshots),
            "cameras": [snapshot.to_dict() for snapshot in snapshots],
        }

    def cleanup_orphans(self) -> None:
        for worker in self.workers:
            worker.cleanup_orphaned_artifacts()
        state_dir = self.runtime_dir / "state"
        pid_dir = self.runtime_dir / "pids"
        live_state_paths = {worker.state_path for worker in self.workers}
        live_pid_paths = {worker.pid_path for worker in self.workers}
        for directory, live_paths in (
            (state_dir, live_state_paths),
            (pid_dir, live_pid_paths),
        ):
            if not directory.exists():
                continue
            for path in directory.iterdir():
                if path in live_paths:
                    continue
                path.unlink()

    def archive_logs(self) -> list[str]:
        archived_paths: list[str] = []
        for worker in self.workers:
            before = (
                set(worker.archive_dir.glob("*.log"))
                if worker.archive_dir.exists()
                else set()
            )
            worker._archive_log()
            after = (
                set(worker.archive_dir.glob("*.log"))
                if worker.archive_dir.exists()
                else set()
            )
            archived_paths.extend(str(path) for path in sorted(after - before))
        return archived_paths

    def write_status(self) -> Path:
        status_path = self.runtime_dir / "status.json"
        status_path.parent.mkdir(parents=True, exist_ok=True)
        status_path.write_text(
            json.dumps(self.status(), indent=2, sort_keys=True), encoding="utf-8"
        )
        return status_path

    def _build_worker(self, camera: FakeCameraConfig) -> FakeCameraWorker:
        return FakeCameraWorker(
            camera,
            runtime_dir=self.runtime_dir,
            python_bin=self.python_bin,
            health_interval=self.health_interval,
            startup_timeout=self.startup_timeout,
            stop_timeout=self.stop_timeout,
            env=self.env,
            launcher=self.launcher,
        )

    def _validate_unique_ips(self) -> None:
        seen_ips: set[str] = set()
        for camera in self.cameras:
            if camera.ip_address in seen_ips:
                raise ValueError(
                    f"duplicate fake camera ip binding: {camera.ip_address}"
                )
            seen_ips.add(camera.ip_address)

    def _remove_empty_runtime_dirs(self) -> None:
        for relative in ("state", "pids"):
            directory = self.runtime_dir / relative
            if directory.exists() and not any(directory.iterdir()):
                directory.rmdir()


def default_runtime_dir(base_dir: str | Path) -> Path:
    return Path(base_dir)
