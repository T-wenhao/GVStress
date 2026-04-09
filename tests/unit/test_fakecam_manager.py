# pyright: reportMissingImports=false

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gvstress.config.models import FakeCameraConfig
from gvstress.fakecam.manager import FakeCameraManager


class FakeProcess:
    def __init__(self, pid: int) -> None:
        self.pid = pid
        self._returncode: int | None = None

    def poll(self) -> int | None:
        return self._returncode

    def wait(self, timeout: float | None = None) -> int:
        _ = timeout
        self._returncode = 0
        return 0

    def terminate(self) -> None:
        self._returncode = 0

    def kill(self) -> None:
        self._returncode = -9


def test_duplicate_ip_binding_is_rejected(tmp_path: Path) -> None:
    cameras = [
        FakeCameraConfig(
            ip_address="192.168.10.11",
            interface_name="eno1",
            serial_number="GV-001",
            genicam_filename="camera-a.xml",
            gvsp_lost_ratio=0.0,
        ),
        FakeCameraConfig(
            ip_address="192.168.10.11",
            interface_name="eno2",
            serial_number="GV-002",
            genicam_filename="camera-b.xml",
            gvsp_lost_ratio=0.0,
        ),
    ]

    with pytest.raises(ValueError, match="duplicate fake camera ip binding"):
        _ = FakeCameraManager(cameras, runtime_dir=tmp_path)


def test_down_cleans_stale_pid_and_state_files(tmp_path: Path) -> None:
    camera = FakeCameraConfig(
        ip_address="192.168.10.11",
        interface_name="eno1",
        serial_number="GV-001",
        genicam_filename="camera-a.xml",
        gvsp_lost_ratio=0.0,
    )
    manager = FakeCameraManager(
        [camera], runtime_dir=tmp_path, launcher=lambda **_: FakeProcess(0)
    )
    worker = manager.workers[0]

    worker.pid_path.parent.mkdir(parents=True, exist_ok=True)
    worker.state_path.parent.mkdir(parents=True, exist_ok=True)
    worker.pid_path.write_text("999999\n", encoding="utf-8")
    worker.state_path.write_text(
        json.dumps(
            {
                "serial_number": camera.serial_number,
                "ip_address": camera.ip_address,
                "interface_name": camera.interface_name,
                "genicam_filename": camera.genicam_filename,
                "gvsp_lost_ratio": camera.gvsp_lost_ratio,
                "pid": 999999,
                "process_alive": True,
                "running": True,
                "started_at": 1.0,
                "updated_at": 1.0,
                "state_path": str(worker.state_path),
                "log_path": str(worker.log_path),
                "error": None,
            }
        ),
        encoding="utf-8",
    )

    payload = manager.down()

    assert payload["stopped_count"] == 1
    assert worker.pid_path.exists() is False
    assert worker.state_path.exists() is False
