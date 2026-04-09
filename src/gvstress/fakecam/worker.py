from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from types import FrameType
from typing import Any, Protocol

from gvstress.config.models import FakeCameraConfig


class SupportsProcess(Protocol):
    pid: int

    def poll(self) -> int | None: ...

    def wait(self, timeout: float | None = None) -> int: ...

    def terminate(self) -> None: ...

    def kill(self) -> None: ...


@dataclass(slots=True)
class FakeCameraHealthSnapshot:
    serial_number: str
    ip_address: str
    interface_name: str
    genicam_filename: str
    gvsp_lost_ratio: float
    pid: int | None
    process_alive: bool
    running: bool
    started_at: float | None
    updated_at: float
    state_path: str
    log_path: str
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> FakeCameraHealthSnapshot:
        return cls(
            serial_number=str(payload["serial_number"]),
            ip_address=str(payload["ip_address"]),
            interface_name=str(payload["interface_name"]),
            genicam_filename=str(payload["genicam_filename"]),
            gvsp_lost_ratio=_coerce_float(payload.get("gvsp_lost_ratio"), default=0.0),
            pid=_coerce_optional_int(payload.get("pid")),
            process_alive=bool(payload.get("process_alive", False)),
            running=bool(payload.get("running", False)),
            started_at=_coerce_optional_float(payload.get("started_at")),
            updated_at=_coerce_float(payload.get("updated_at"), default=0.0),
            state_path=str(payload["state_path"]),
            log_path=str(payload["log_path"]),
            error=_coerce_optional_str(payload.get("error")),
        )


def _default_launcher(
    argv: list[str],
    *,
    stdout: Any,
    stderr: Any,
    env: dict[str, str] | None,
) -> SupportsProcess:
    return subprocess.Popen(argv, stdout=stdout, stderr=stderr, env=env)


class FakeCameraWorker:
    def __init__(
        self,
        camera: FakeCameraConfig,
        *,
        runtime_dir: str | Path,
        python_bin: str = sys.executable,
        health_interval: float = 1.0,
        startup_timeout: float = 5.0,
        stop_timeout: float = 5.0,
        env: dict[str, str] | None = None,
        launcher: Any | None = None,
    ) -> None:
        self.camera = camera
        self.runtime_dir = Path(runtime_dir)
        self.python_bin = python_bin
        self.health_interval = health_interval
        self.startup_timeout = startup_timeout
        self.stop_timeout = stop_timeout
        self.env = env
        self.launcher = launcher or _default_launcher
        self.process: SupportsProcess | None = None

    @property
    def worker_name(self) -> str:
        return _slugify(self.camera.serial_number)

    @property
    def state_path(self) -> Path:
        return self.runtime_dir / "state" / f"{self.worker_name}.json"

    @property
    def pid_path(self) -> Path:
        return self.runtime_dir / "pids" / f"{self.worker_name}.pid"

    @property
    def log_path(self) -> Path:
        return self.runtime_dir / "logs" / f"{self.worker_name}.log"

    @property
    def archive_dir(self) -> Path:
        return self.runtime_dir / "logs" / "archive"

    def start(self) -> FakeCameraHealthSnapshot:
        self._ensure_runtime_dirs()
        if self.pid_path.exists() and self.is_process_alive():
            snapshot = self.status()
            if snapshot is not None:
                return snapshot

        with self.log_path.open("a", encoding="utf-8") as log_file:
            argv = self.build_argv()
            process = self.launcher(
                argv,
                stdout=log_file,
                stderr=log_file,
                env=self.env,
            )
        self.process = process
        self.pid_path.write_text(f"{process.pid}\n", encoding="utf-8")

        deadline = time.monotonic() + self.startup_timeout
        while time.monotonic() < deadline:
            snapshot = self.status()
            if snapshot is not None and snapshot.running and snapshot.process_alive:
                return snapshot
            process = self.process
            if process is not None and process.poll() is not None:
                break
            time.sleep(min(self.health_interval, 0.1))

        self.stop(remove_state=False)
        raise RuntimeError(
            f"fake camera worker failed to start for {self.camera.serial_number}"
        )

    def stop(self, *, remove_state: bool = True) -> FakeCameraHealthSnapshot:
        pid = self._current_pid()
        if pid is not None:
            self._terminate_pid(pid)
        snapshot = self.status() or self._stopped_snapshot(pid=pid)
        if remove_state and self.state_path.exists():
            self.state_path.unlink()
        if self.pid_path.exists():
            self.pid_path.unlink()
        self._archive_log()
        return snapshot

    def status(self) -> FakeCameraHealthSnapshot | None:
        snapshot = self._read_snapshot()
        pid = self._current_pid(snapshot.pid if snapshot is not None else None)
        process_alive = pid is not None and _pid_exists(pid)
        if snapshot is None:
            if pid is None:
                return None
            return self._stopped_snapshot(pid=pid, process_alive=process_alive)
        snapshot.pid = pid
        snapshot.process_alive = process_alive
        snapshot.running = snapshot.running and process_alive
        snapshot.updated_at = time.time() if process_alive else snapshot.updated_at
        return snapshot

    def is_process_alive(self) -> bool:
        pid = self._current_pid()
        return pid is not None and _pid_exists(pid)

    def cleanup_orphaned_artifacts(self) -> None:
        pid = self._current_pid()
        if pid is not None and _pid_exists(pid):
            return
        if self.pid_path.exists():
            self.pid_path.unlink()
        if self.state_path.exists():
            self.state_path.unlink()

    def build_argv(self) -> list[str]:
        return [
            self.python_bin,
            "-m",
            "gvstress.fakecam.worker",
            "run",
            "--ip-address",
            self.camera.ip_address,
            "--interface-name",
            self.camera.interface_name,
            "--serial-number",
            self.camera.serial_number,
            "--genicam-filename",
            self.camera.genicam_filename,
            "--gvsp-lost-ratio",
            str(self.camera.gvsp_lost_ratio),
            "--state-path",
            str(self.state_path),
            "--log-path",
            str(self.log_path),
            "--health-interval",
            str(self.health_interval),
        ]

    def _ensure_runtime_dirs(self) -> None:
        for path in (
            self.state_path.parent,
            self.pid_path.parent,
            self.log_path.parent,
            self.archive_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def _read_snapshot(self) -> FakeCameraHealthSnapshot | None:
        if not self.state_path.exists():
            return None
        payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return None
        return FakeCameraHealthSnapshot.from_dict(payload)

    def _current_pid(self, fallback: int | None = None) -> int | None:
        if self.process is not None:
            return self.process.pid
        if self.pid_path.exists():
            return _coerce_optional_int(
                self.pid_path.read_text(encoding="utf-8").strip()
            )
        return fallback

    def _terminate_pid(self, pid: int) -> None:
        process = self.process
        if process is not None and process.pid == pid:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=self.stop_timeout)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=self.stop_timeout)
            self.process = None
            return

        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        deadline = time.monotonic() + self.stop_timeout
        while time.monotonic() < deadline:
            if not _pid_exists(pid):
                return
            time.sleep(0.05)
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            return

    def _archive_log(self) -> None:
        if not self.log_path.exists():
            return
        archived_path = self.archive_dir / f"{self.worker_name}-{int(time.time())}.log"
        archived_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.replace(archived_path)

    def _stopped_snapshot(
        self,
        *,
        pid: int | None,
        process_alive: bool = False,
    ) -> FakeCameraHealthSnapshot:
        return FakeCameraHealthSnapshot(
            serial_number=self.camera.serial_number,
            ip_address=self.camera.ip_address,
            interface_name=self.camera.interface_name,
            genicam_filename=self.camera.genicam_filename,
            gvsp_lost_ratio=self.camera.gvsp_lost_ratio,
            pid=pid,
            process_alive=process_alive,
            running=False,
            started_at=None,
            updated_at=time.time(),
            state_path=str(self.state_path),
            log_path=str(self.log_path),
            error=None,
        )


def run_worker(
    *,
    ip_address: str,
    interface_name: str,
    serial_number: str,
    genicam_filename: str,
    gvsp_lost_ratio: float,
    state_path: str | Path,
    log_path: str | Path,
    health_interval: float,
) -> int:
    state_file = Path(state_path)
    state_file.parent.mkdir(parents=True, exist_ok=True)
    stop_requested = False
    started_at = time.time()

    def handle_signal(signum: int, frame: FrameType | None) -> None:
        nonlocal stop_requested
        _ = signum
        _ = frame
        stop_requested = True

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    snapshot = FakeCameraHealthSnapshot(
        serial_number=serial_number,
        ip_address=ip_address,
        interface_name=interface_name,
        genicam_filename=genicam_filename,
        gvsp_lost_ratio=gvsp_lost_ratio,
        pid=os.getpid(),
        process_alive=True,
        running=False,
        started_at=started_at,
        updated_at=started_at,
        state_path=str(state_file),
        log_path=str(log_path),
        error=None,
    )

    camera: Any = None
    arv_module: Any = None
    try:
        arv_module = _load_aravis_module()
        camera = _create_fake_camera(
            arv_module,
            interface_name=interface_name,
            serial_number=serial_number,
            genicam_filename=genicam_filename,
        )
        _set_gvsp_lost_ratio(camera, gvsp_lost_ratio)
        snapshot.running = bool(_camera_is_running(camera))
        _write_snapshot(state_file, snapshot)

        while not stop_requested:
            snapshot.running = bool(_camera_is_running(camera))
            snapshot.updated_at = time.time()
            _write_snapshot(state_file, snapshot)
            time.sleep(health_interval)
    except Exception as exc:
        snapshot.error = str(exc)
        snapshot.running = False
        snapshot.updated_at = time.time()
        _write_snapshot(state_file, snapshot)
        return 1
    finally:
        snapshot.process_alive = False
        snapshot.running = False
        snapshot.updated_at = time.time()
        _write_snapshot(state_file, snapshot)
        if camera is not None:
            _cleanup_camera(camera)
        if arv_module is not None and hasattr(arv_module, "shutdown"):
            arv_module.shutdown()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gvstress.fakecam.worker")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--ip-address", required=True)
    run_parser.add_argument("--interface-name", required=True)
    run_parser.add_argument("--serial-number", required=True)
    run_parser.add_argument("--genicam-filename", required=True)
    run_parser.add_argument("--gvsp-lost-ratio", type=float, required=True)
    run_parser.add_argument("--state-path", required=True)
    run_parser.add_argument("--log-path", required=True)
    run_parser.add_argument("--health-interval", type=float, default=1.0)
    args = parser.parse_args(argv)

    return run_worker(
        ip_address=args.ip_address,
        interface_name=args.interface_name,
        serial_number=args.serial_number,
        genicam_filename=args.genicam_filename,
        gvsp_lost_ratio=args.gvsp_lost_ratio,
        state_path=args.state_path,
        log_path=args.log_path,
        health_interval=args.health_interval,
    )


def _load_aravis_module() -> Any:
    import gi  # type: ignore[import-untyped]

    for namespace in ("Aravis", "Arv"):
        try:
            gi.require_version(namespace, "0.10")
            module = __import__("gi.repository", fromlist=[namespace])
            return getattr(module, namespace)
        except (ImportError, ValueError, AttributeError):
            continue
    raise RuntimeError("Unable to import Aravis PyGObject bindings")


def _create_fake_camera(
    module: Any,
    *,
    interface_name: str,
    serial_number: str,
    genicam_filename: str,
) -> Any:
    camera_class = getattr(module, "GvFakeCamera", None) or getattr(
        module, "ArvGvFakeCamera", None
    )
    if camera_class is None:
        raise RuntimeError("Aravis bindings do not expose GvFakeCamera")
    if hasattr(camera_class, "new_full"):
        return camera_class.new_full(interface_name, serial_number, genicam_filename)
    if hasattr(camera_class, "new"):
        return camera_class.new(interface_name, serial_number)
    return camera_class(interface_name, serial_number, genicam_filename)


def _set_gvsp_lost_ratio(camera: Any, ratio: float) -> None:
    if hasattr(camera, "set_property"):
        camera.set_property("gvsp-lost-ratio", ratio)
        return
    props = getattr(camera, "props", None)
    if props is not None and hasattr(props, "gvsp_lost_ratio"):
        props.gvsp_lost_ratio = ratio
        return
    camera.gvsp_lost_ratio = ratio


def _camera_is_running(camera: Any) -> bool:
    if hasattr(camera, "is_running"):
        return bool(camera.is_running())
    if hasattr(camera, "get_is_running"):
        return bool(camera.get_is_running())
    return True


def _cleanup_camera(camera: Any) -> None:
    if hasattr(camera, "shutdown"):
        camera.shutdown()
    if hasattr(camera, "stop"):
        camera.stop()


def _write_snapshot(path: Path, snapshot: FakeCameraHealthSnapshot) -> None:
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(
        json.dumps(snapshot.to_dict(), indent=2, sort_keys=True), encoding="utf-8"
    )
    temp_path.replace(path)


def _slugify(value: str) -> str:
    return "".join(
        character.lower() if character.isalnum() else "-" for character in value
    )


def _pid_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _coerce_optional_int(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _coerce_optional_float(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _coerce_optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _coerce_float(value: object, *, default: float) -> float:
    coerced = _coerce_optional_float(value)
    return default if coerced is None else coerced


if __name__ == "__main__":
    raise SystemExit(main())
