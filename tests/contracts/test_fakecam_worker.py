# pyright: reportMissingImports=false

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from gvstress.config.models import FakeCameraConfig
from gvstress.fakecam.manager import FakeCameraManager
from gvstress.fakecam.worker import FakeCameraWorker

ROOT = Path(__file__).resolve().parents[2]


def test_manager_starts_four_distinct_workers(tmp_path: Path) -> None:
    env = _worker_env(tmp_path)
    cameras = [
        FakeCameraConfig(
            ip_address=f"192.168.10.1{index}",
            interface_name=f"eno{index}",
            serial_number=f"GV-00{index}",
            genicam_filename=f"camera-{index}.xml",
            gvsp_lost_ratio=0.01 * index,
        )
        for index in range(1, 5)
    ]
    manager = FakeCameraManager(
        cameras,
        runtime_dir=tmp_path / "runtime",
        python_bin=sys.executable,
        env=env,
        health_interval=0.05,
        startup_timeout=5.0,
        stop_timeout=2.0,
    )

    payload = manager.up()

    assert payload["started"] == 4
    statuses = payload["cameras"]
    assert len(statuses) == 4
    assert all(status["running"] is True for status in statuses)
    assert len({status["state_path"] for status in statuses}) == 4
    assert len({status["pid"] for status in statuses}) == 4

    down_payload = manager.down()
    assert down_payload["stopped_count"] == 4
    for worker in manager.workers:
        assert worker.pid_path.exists() is False
        assert worker.state_path.exists() is False


def test_worker_records_health_snapshot_with_stub_aravis(tmp_path: Path) -> None:
    env = _worker_env(tmp_path)
    camera = FakeCameraConfig(
        ip_address="192.168.10.11",
        interface_name="eno1",
        serial_number="GV-001",
        genicam_filename="camera-a.xml",
        gvsp_lost_ratio=0.25,
    )
    worker = FakeCameraWorker(
        camera,
        runtime_dir=tmp_path / "runtime",
        python_bin=sys.executable,
        env=env,
        health_interval=0.05,
        startup_timeout=5.0,
        stop_timeout=2.0,
    )

    snapshot = worker.start()
    time.sleep(0.1)
    running_snapshot = worker.status()

    assert snapshot.running is True
    assert running_snapshot is not None
    assert running_snapshot.running is True
    assert running_snapshot.interface_name == "eno1"
    assert running_snapshot.gvsp_lost_ratio == 0.25

    worker.stop()
    assert worker.pid_path.exists() is False


def _worker_env(tmp_path: Path) -> dict[str, str]:
    stub_root = tmp_path / "stubsite"
    _write_stub_aravis(stub_root)
    env = os.environ.copy()
    src_path = str(ROOT / "src")
    stub_path = str(stub_root)
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        f"{stub_path}:{src_path}"
        if not existing
        else f"{stub_path}:{src_path}:{existing}"
    )
    return env


def _write_stub_aravis(root: Path) -> None:
    gi_dir = root / "gi" / "repository"
    gi_dir.mkdir(parents=True, exist_ok=True)
    (root / "gi" / "__init__.py").write_text(
        "def require_version(namespace, version):\n    return None\n",
        encoding="utf-8",
    )
    (gi_dir / "__init__.py").write_text("", encoding="utf-8")
    (gi_dir / "Arv.py").write_text(
        "class GvFakeCamera:\n"
        "    def __init__(self, interface_name, serial_number, genicam_filename):\n"
        "        self.interface_name = interface_name\n"
        "        self.serial_number = serial_number\n"
        "        self.genicam_filename = genicam_filename\n"
        "        self._properties = {}\n"
        "        self._running = True\n"
        "    @classmethod\n"
        "    def new_full(cls, interface_name, serial_number, genicam_filename):\n"
        "        return cls(interface_name, serial_number, genicam_filename)\n"
        "    def set_property(self, key, value):\n"
        "        self._properties[key] = value\n"
        "    def is_running(self):\n"
        "        return self._running\n"
        "    def shutdown(self):\n"
        "        self._running = False\n"
        "def shutdown():\n"
        "    return None\n",
        encoding="utf-8",
    )
