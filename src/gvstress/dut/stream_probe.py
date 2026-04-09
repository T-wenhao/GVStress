# pyright: reportMissingImports=false, reportMissingTypeStubs=false, reportExplicitAny=false, reportAny=false, reportUnannotatedClassAttribute=false, reportUnusedCallResult=false

from __future__ import annotations

import importlib
import threading
import time
from collections.abc import Callable, Iterator, Sequence
from dataclasses import asdict, dataclass
from typing import Any

from gvstress.config.models import FakeCameraConfig, StreamConfig


@dataclass(slots=True, frozen=True)
class StreamTarget:
    serial_number: str
    ip_address: str

    @classmethod
    def from_camera_config(cls, camera: FakeCameraConfig) -> StreamTarget:
        return cls(serial_number=camera.serial_number, ip_address=camera.ip_address)

    @classmethod
    def from_selector(cls, selector: str) -> StreamTarget:
        serial_number, separator, ip_address = selector.partition("@")
        if not separator or not serial_number.strip() or not ip_address.strip():
            raise ValueError("camera selectors must use SERIAL@IP format")
        return cls(serial_number=serial_number.strip(), ip_address=ip_address.strip())

    def label(self) -> str:
        return f"{self.serial_number}@{self.ip_address}"


@dataclass(slots=True)
class DiscoveredDevice:
    device_id: str
    serial_number: str | None
    ip_address: str | None
    vendor: str | None
    model: str | None
    protocol: str | None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class StreamPropertySnapshot:
    timestamp: float
    serial_number: str
    ip_address: str
    device_id: str
    packet_resend: bool
    socket_buffer: bool
    socket_buffer_size: int
    frame_retention: int
    initial_packet_timeout: int
    packet_timeout: int
    packet_request_ratio: float
    receiver_priority: int
    buffer_count: int
    record_type: str = "stream_property_snapshot"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class StreamSample:
    timestamp: float
    interval: float | None
    serial_number: str
    ip_address: str
    device_id: str
    n_completed_buffers: int
    n_failures: int
    n_underruns: int
    control_lost: bool
    error: str | None
    property_snapshot: StreamPropertySnapshot
    record_type: str = "stream_sample"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class _OpenedStream:
    target: StreamTarget
    device: DiscoveredDevice
    camera: Any
    stream: Any
    property_snapshot: StreamPropertySnapshot
    stop_event: threading.Event
    recycler: threading.Thread | None = None
    control_lost: bool = False
    error: str | None = None

    def to_sample(self, *, timestamp: float, interval: float | None) -> StreamSample:
        completed, failures, underruns = self.stream.get_statistics()
        return StreamSample(
            timestamp=timestamp,
            interval=interval,
            serial_number=self.target.serial_number,
            ip_address=self.target.ip_address,
            device_id=self.device.device_id,
            n_completed_buffers=int(completed),
            n_failures=int(failures),
            n_underruns=int(underruns),
            control_lost=self.control_lost,
            error=self.error,
            property_snapshot=self.property_snapshot,
        )


class StreamProbe:
    def __init__(
        self,
        targets: Sequence[StreamTarget],
        stream_config: StreamConfig,
        *,
        sample_interval_s: float = 1.0,
        recycle_timeout_us: int = 100_000,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        aravis: Any | None = None,
    ) -> None:
        if not targets:
            raise ValueError("at least one stream target is required")
        if sample_interval_s <= 0:
            raise ValueError("sample_interval_s must be positive")
        if recycle_timeout_us <= 0:
            raise ValueError("recycle_timeout_us must be positive")

        labels = [target.label() for target in targets]
        if len(set(labels)) != len(labels):
            raise ValueError("stream targets must be unique")

        self._targets = list(targets)
        self._stream_config = stream_config
        self._sample_interval_s = sample_interval_s
        self._recycle_timeout_us = recycle_timeout_us
        self._clock = clock
        self._sleep = sleep
        self._aravis = aravis
        self._previous_timestamp: float | None = None

    def run(
        self, *, duration: float | None = None
    ) -> Iterator[StreamPropertySnapshot | StreamSample]:
        if duration is not None and duration < 0:
            raise ValueError("duration must be non-negative when provided")

        aravis_module = self._aravis or _load_aravis()
        opened_streams: list[_OpenedStream] = []

        try:
            discovered_devices = self.discover_devices(aravis=aravis_module)
            matched_devices = self.match_targets(self._targets, discovered_devices)
            opened_streams = [
                self._open_stream(aravis_module, target, device)
                for target, device in matched_devices
            ]

            for opened_stream in opened_streams:
                yield opened_stream.property_snapshot

            self._start_streams(opened_streams)

            started_at = self._clock()
            deadline_at = None if duration is None else started_at + duration
            next_sample_at = started_at

            while True:
                now = self._clock()

                if now >= next_sample_at:
                    interval = (
                        None
                        if self._previous_timestamp is None
                        else now - self._previous_timestamp
                    )
                    for opened_stream in opened_streams:
                        yield opened_stream.to_sample(timestamp=now, interval=interval)
                    self._previous_timestamp = now
                    next_sample_at += self._sample_interval_s

                if deadline_at is not None and now >= deadline_at:
                    break

                sleep_seconds = _next_sleep_seconds(
                    now=now,
                    next_sample_at=next_sample_at,
                    deadline_at=deadline_at,
                )
                if sleep_seconds > 0:
                    self._sleep(sleep_seconds)
        finally:
            self._previous_timestamp = None
            self._stop_streams(opened_streams)
            _shutdown_aravis(aravis_module)

    def discover_devices(self, *, aravis: Any | None = None) -> list[DiscoveredDevice]:
        aravis_module = aravis or self._aravis or _load_aravis()
        aravis_module.update_device_list()

        devices: list[DiscoveredDevice] = []
        for index in range(int(aravis_module.get_n_devices())):
            devices.append(
                DiscoveredDevice(
                    device_id=_read_required_aravis_str(
                        aravis_module, "get_device_id", index
                    ),
                    serial_number=_read_optional_aravis_str(
                        aravis_module, "get_device_serial_nbr", index
                    ),
                    ip_address=_read_optional_aravis_str(
                        aravis_module, "get_device_address", index
                    ),
                    vendor=_read_optional_aravis_str(
                        aravis_module, "get_device_vendor", index
                    ),
                    model=_read_optional_aravis_str(
                        aravis_module, "get_device_model", index
                    ),
                    protocol=_read_optional_aravis_str(
                        aravis_module, "get_device_protocol", index
                    ),
                )
            )
        return devices

    @staticmethod
    def match_targets(
        targets: Sequence[StreamTarget], devices: Sequence[DiscoveredDevice]
    ) -> list[tuple[StreamTarget, DiscoveredDevice]]:
        remaining_devices = list(devices)
        matches: list[tuple[StreamTarget, DiscoveredDevice]] = []
        missing_targets: list[str] = []

        for target in targets:
            best_match: DiscoveredDevice | None = None
            best_score = -1

            for device in remaining_devices:
                score = _match_score(target, device)
                if score > best_score:
                    best_match = device
                    best_score = score

            if best_match is None or best_score < 0:
                missing_targets.append(target.label())
                continue

            matches.append((target, best_match))
            remaining_devices.remove(best_match)

        if missing_targets:
            raise RuntimeError(
                "unable to discover cameras for targets: "
                + ", ".join(sorted(missing_targets))
            )

        return matches

    def _open_stream(
        self,
        aravis_module: Any,
        target: StreamTarget,
        device: DiscoveredDevice,
    ) -> _OpenedStream:
        camera = aravis_module.Camera.new(device.device_id)
        if camera is None:
            raise RuntimeError(f"failed to open camera {device.device_id}")

        stream = camera.create_stream(None, None)
        if stream is None:
            raise RuntimeError(f"failed to create stream for {device.device_id}")

        self._apply_stream_properties(stream)

        payload = int(camera.get_payload())
        if payload <= 0:
            raise RuntimeError(
                f"invalid payload size for {device.device_id}: {payload}"
            )

        for _ in range(self._stream_config.buffer_count):
            stream.push_buffer(aravis_module.Buffer.new_allocate(payload))

        snapshot_payload = self._stream_config.property_snapshot()
        snapshot = StreamPropertySnapshot(
            timestamp=self._clock(),
            serial_number=target.serial_number,
            ip_address=target.ip_address,
            device_id=device.device_id,
            packet_resend=bool(snapshot_payload["packet_resend"]),
            socket_buffer=bool(snapshot_payload["socket_buffer"]),
            socket_buffer_size=int(snapshot_payload["socket_buffer_size"]),
            frame_retention=int(snapshot_payload["frame_retention"]),
            initial_packet_timeout=int(snapshot_payload["initial_packet_timeout"]),
            packet_timeout=int(snapshot_payload["packet_timeout"]),
            packet_request_ratio=float(snapshot_payload["packet_request_ratio"]),
            receiver_priority=int(snapshot_payload["receiver_priority"]),
            buffer_count=int(snapshot_payload["buffer_count"]),
        )

        return _OpenedStream(
            target=target,
            device=device,
            camera=camera,
            stream=stream,
            property_snapshot=snapshot,
            stop_event=threading.Event(),
        )

    def _apply_stream_properties(self, stream: Any) -> None:
        for (
            property_name,
            value,
        ) in self._stream_config.applied_property_values().items():
            stream.set_property(property_name, value)

    def _start_streams(self, opened_streams: Sequence[_OpenedStream]) -> None:
        for opened_stream in opened_streams:
            opened_stream.camera.start_acquisition()
            opened_stream.recycler = threading.Thread(
                target=self._recycle_buffers,
                args=(opened_stream,),
                name=f"stream-probe-{opened_stream.target.serial_number}",
                daemon=True,
            )
            opened_stream.recycler.start()

    def _stop_streams(self, opened_streams: Sequence[_OpenedStream]) -> None:
        for opened_stream in opened_streams:
            opened_stream.stop_event.set()

        for opened_stream in opened_streams:
            if opened_stream.recycler is not None:
                opened_stream.recycler.join(timeout=1.0)

        for opened_stream in opened_streams:
            try:
                opened_stream.camera.stop_acquisition()
            except Exception:
                continue

    def _recycle_buffers(self, opened_stream: _OpenedStream) -> None:
        while not opened_stream.stop_event.is_set():
            try:
                buffer = opened_stream.stream.timeout_pop_buffer(
                    self._recycle_timeout_us
                )
                if buffer is None:
                    continue
                opened_stream.stream.push_buffer(buffer)
            except Exception as exc:
                opened_stream.control_lost = True
                opened_stream.error = str(exc)
                return


def _load_aravis() -> Any:
    try:
        gi = importlib.import_module("gi")
    except ImportError as exc:
        raise RuntimeError(
            "PyGObject with Aravis bindings is required for stream probing"
        ) from exc

    gi.require_version("Aravis", "0.10")
    repository = importlib.import_module("gi.repository")
    return repository.Aravis


def _shutdown_aravis(aravis_module: Any) -> None:
    shutdown = getattr(aravis_module, "shutdown", None)
    if callable(shutdown):
        shutdown()


def _read_optional_aravis_str(
    aravis_module: Any, attribute_name: str, index: int
) -> str | None:
    reader = getattr(aravis_module, attribute_name, None)
    if reader is None:
        return None
    value = reader(index)
    if value is None:
        return None
    rendered = str(value).strip()
    return rendered or None


def _read_required_aravis_str(
    aravis_module: Any, attribute_name: str, index: int
) -> str:
    value = _read_optional_aravis_str(aravis_module, attribute_name, index)
    if value is None:
        raise RuntimeError(f"Aravis is missing required attribute {attribute_name}")
    return value


def _match_score(target: StreamTarget, device: DiscoveredDevice) -> int:
    if (
        device.serial_number is not None
        and target.serial_number
        and device.serial_number != target.serial_number
    ):
        return -1
    if (
        device.ip_address is not None
        and target.ip_address
        and device.ip_address != target.ip_address
    ):
        return -1

    score = 0
    if target.serial_number and device.serial_number == target.serial_number:
        score += 2
    if target.ip_address and device.ip_address == target.ip_address:
        score += 1
    return score if score > 0 else -1


def _next_sleep_seconds(
    *, now: float, next_sample_at: float, deadline_at: float | None
) -> float:
    candidates = [max(0.0, next_sample_at - now)]
    if deadline_at is not None:
        candidates.append(max(0.0, deadline_at - now))
    return min(candidates)
