# pyright: reportPrivateUsage=false, reportImplicitOverride=false

from __future__ import annotations

import importlib
import threading
from collections.abc import Iterator, Sequence
from types import ModuleType
from typing import cast

import pytest

from gvstress.config.models import StreamConfig
from gvstress.dut.stream_probe import (
    DiscoveredDevice,
    StreamProbe,
    StreamPropertySnapshot,
    StreamSample,
    StreamTarget,
    _load_aravis,
    _OpenedStream,
)


def _stream_config(*, buffer_count: int = 2) -> StreamConfig:
    return StreamConfig(
        packet_resend=True,
        socket_buffer=True,
        socket_buffer_size=1048576,
        frame_retention=200000,
        initial_packet_timeout=1000,
        packet_timeout=2000,
        packet_request_ratio=0.25,
        receiver_priority=0,
        buffer_count=buffer_count,
    )


class FakeClock:
    def __init__(self, now: float = 100.0) -> None:
        self.now: float = now
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class FakeBuffer:
    def __init__(self, payload: int) -> None:
        self.payload: int = payload


class FakeBufferFactory:
    def __init__(self) -> None:
        self.allocated: list[int] = []

    def new_allocate(self, payload: int) -> FakeBuffer:
        self.allocated.append(payload)
        return FakeBuffer(payload)


class FakeStream:
    def __init__(
        self,
        *,
        statistics: tuple[int, int, int] = (4, 1, 0),
        pop_actions: list[FakeBuffer | None | Exception] | None = None,
        stop_event: threading.Event | None = None,
        stop_after_push: bool = False,
    ) -> None:
        self.statistics: tuple[int, int, int] = statistics
        self.pop_actions: list[FakeBuffer | None | Exception] = list(pop_actions or [])
        self.stop_event: threading.Event | None = stop_event
        self.stop_after_push: bool = stop_after_push
        self.properties: dict[str, int | float] = {}
        self.pushed: list[FakeBuffer] = []
        self.timeouts: list[int] = []

    def set_property(self, name: str, value: int | float) -> None:
        self.properties[name] = value

    def push_buffer(self, buffer: FakeBuffer) -> None:
        self.pushed.append(buffer)
        if self.stop_after_push and self.stop_event is not None:
            self.stop_event.set()

    def get_statistics(self) -> tuple[int, int, int]:
        return self.statistics

    def timeout_pop_buffer(self, timeout_us: int) -> FakeBuffer | None:
        self.timeouts.append(timeout_us)
        if not self.pop_actions:
            return None
        action = self.pop_actions.pop(0)
        if isinstance(action, Exception):
            raise action
        return action


class FakeCamera:
    def __init__(self, device_id: str, stream: FakeStream, payload: int = 512) -> None:
        self.device_id: str = device_id
        self.stream: FakeStream = stream
        self.payload: int = payload
        self.started: bool = False
        self.stopped: bool = False

    def create_stream(self, _callback: object, _user_data: object) -> FakeStream:
        return self.stream

    def get_payload(self) -> int:
        return self.payload

    def start_acquisition(self) -> None:
        self.started = True

    def stop_acquisition(self) -> None:
        self.stopped = True


class FakeCameraFactory:
    def __init__(self, cameras: dict[str, FakeCamera]) -> None:
        self.cameras: dict[str, FakeCamera] = cameras

    def new(self, device_id: str) -> FakeCamera | None:
        return self.cameras.get(device_id)


class FakeAravis:
    def __init__(
        self, devices: list[dict[str, str | None]], cameras: dict[str, FakeCamera]
    ) -> None:
        self._devices: list[dict[str, str | None]] = devices
        self.updated: bool = False
        self.shutdown_called: bool = False
        self.Buffer: FakeBufferFactory = FakeBufferFactory()
        self.Camera: FakeCameraFactory = FakeCameraFactory(cameras)

    def update_device_list(self) -> None:
        self.updated = True

    def get_n_devices(self) -> int:
        return len(self._devices)

    def get_device_id(self, index: int) -> str | None:
        return self._devices[index]["device_id"]

    def get_device_serial_nbr(self, index: int) -> str | None:
        return self._devices[index].get("serial_number")

    def get_device_address(self, index: int) -> str | None:
        return self._devices[index].get("ip_address")

    def get_device_vendor(self, index: int) -> str | None:
        return self._devices[index].get("vendor")

    def get_device_model(self, index: int) -> str | None:
        return self._devices[index].get("model")

    def get_device_protocol(self, index: int) -> str | None:
        return self._devices[index].get("protocol")

    def shutdown(self) -> None:
        self.shutdown_called = True


class DeterministicStreamProbe(StreamProbe):
    def _start_streams(self, opened_streams: Sequence[_OpenedStream]) -> None:
        for opened_stream in opened_streams:
            camera = cast(FakeCamera, opened_stream.camera)
            camera.start_acquisition()


def test_stream_probe_init_validates_required_inputs() -> None:
    target = StreamTarget(serial_number="CAM-001", ip_address="192.168.10.11")
    config = _stream_config()

    with pytest.raises(ValueError, match="at least one stream target"):
        _ = StreamProbe([], config)

    with pytest.raises(ValueError, match="sample_interval_s must be positive"):
        _ = StreamProbe([target], config, sample_interval_s=0)

    with pytest.raises(ValueError, match="recycle_timeout_us must be positive"):
        _ = StreamProbe([target], config, recycle_timeout_us=0)

    with pytest.raises(ValueError, match="stream targets must be unique"):
        _ = StreamProbe([target, target], config)


def test_stream_probe_discovers_devices_from_aravis() -> None:
    aravis = FakeAravis(
        devices=[
            {
                "device_id": " dev-a ",
                "serial_number": " CAM-001 ",
                "ip_address": " 192.168.10.11 ",
                "vendor": " Aravis ",
                "model": " FakeCam ",
                "protocol": " GigEVision ",
            },
            {
                "device_id": "dev-b",
                "serial_number": None,
                "ip_address": None,
                "vendor": None,
                "model": None,
                "protocol": None,
            },
        ],
        cameras={},
    )
    probe = StreamProbe(
        [StreamTarget(serial_number="CAM-001", ip_address="192.168.10.11")],
        _stream_config(),
        aravis=aravis,
    )

    devices = probe.discover_devices()

    assert aravis.updated is True
    assert devices == [
        DiscoveredDevice(
            device_id="dev-a",
            serial_number="CAM-001",
            ip_address="192.168.10.11",
            vendor="Aravis",
            model="FakeCam",
            protocol="GigEVision",
        ),
        DiscoveredDevice(
            device_id="dev-b",
            serial_number=None,
            ip_address=None,
            vendor=None,
            model=None,
            protocol=None,
        ),
    ]


def test_stream_probe_run_yields_snapshots_and_samples() -> None:
    clock = FakeClock()
    target = StreamTarget(serial_number="CAM-001", ip_address="192.168.10.11")
    stream = FakeStream(statistics=(7, 1, 2))
    camera = FakeCamera("dev-a", stream)
    aravis = FakeAravis(
        devices=[
            {
                "device_id": "dev-a",
                "serial_number": "CAM-001",
                "ip_address": "192.168.10.11",
                "vendor": "Aravis",
                "model": "FakeCam",
                "protocol": "GigEVision",
            }
        ],
        cameras={"dev-a": camera},
    )
    probe = DeterministicStreamProbe(
        [target],
        _stream_config(buffer_count=3),
        sample_interval_s=1.0,
        clock=clock,
        sleep=clock.sleep,
        aravis=aravis,
    )

    records = list(probe.run(duration=2.0))

    assert isinstance(records[0], StreamPropertySnapshot)
    samples = [record for record in records[1:] if isinstance(record, StreamSample)]
    assert [sample.interval for sample in samples] == [None, 1.0, 1.0]
    assert all(sample.n_completed_buffers == 7 for sample in samples)
    assert stream.properties == _stream_config(buffer_count=3).applied_property_values()
    assert len(aravis.Buffer.allocated) == 3
    assert camera.started is True
    assert camera.stopped is True
    assert aravis.shutdown_called is True
    assert probe._previous_timestamp is None
    assert clock.sleeps == [1.0, 1.0]


def test_stream_probe_run_rejects_negative_duration() -> None:
    probe = StreamProbe(
        [StreamTarget(serial_number="CAM-001", ip_address="192.168.10.11")],
        _stream_config(),
    )

    iterator: Iterator[StreamPropertySnapshot | StreamSample] = probe.run(duration=-0.1)
    with pytest.raises(ValueError, match="duration must be non-negative"):
        _ = next(iterator)


def test_stream_probe_recycle_buffers_requeues_until_stopped() -> None:
    stop_event = threading.Event()
    buffer = FakeBuffer(512)
    stream = FakeStream(
        pop_actions=[None, buffer],
        stop_event=stop_event,
        stop_after_push=True,
    )
    opened_stream = _OpenedStream(
        target=StreamTarget(serial_number="CAM-001", ip_address="192.168.10.11"),
        device=DiscoveredDevice(
            device_id="dev-a",
            serial_number="CAM-001",
            ip_address="192.168.10.11",
            vendor="Aravis",
            model="FakeCam",
            protocol="GigEVision",
        ),
        camera=FakeCamera("dev-a", stream),
        stream=stream,
        property_snapshot=StreamPropertySnapshot(
            timestamp=1.0,
            serial_number="CAM-001",
            ip_address="192.168.10.11",
            device_id="dev-a",
            packet_resend=True,
            socket_buffer=True,
            socket_buffer_size=1048576,
            frame_retention=200000,
            initial_packet_timeout=1000,
            packet_timeout=2000,
            packet_request_ratio=0.25,
            receiver_priority=0,
            buffer_count=2,
        ),
        stop_event=stop_event,
    )
    probe = StreamProbe([opened_stream.target], _stream_config())

    probe._recycle_buffers(opened_stream)

    assert stream.timeouts == [100000, 100000]
    assert stream.pushed == [buffer]
    assert opened_stream.control_lost is False
    assert opened_stream.error is None


def test_stream_probe_recycle_buffers_records_control_loss() -> None:
    stop_event = threading.Event()
    stream = FakeStream(pop_actions=[RuntimeError("stream disconnected")])
    opened_stream = _OpenedStream(
        target=StreamTarget(serial_number="CAM-001", ip_address="192.168.10.11"),
        device=DiscoveredDevice(
            device_id="dev-a",
            serial_number="CAM-001",
            ip_address="192.168.10.11",
            vendor="Aravis",
            model="FakeCam",
            protocol="GigEVision",
        ),
        camera=FakeCamera("dev-a", stream),
        stream=stream,
        property_snapshot=StreamPropertySnapshot(
            timestamp=1.0,
            serial_number="CAM-001",
            ip_address="192.168.10.11",
            device_id="dev-a",
            packet_resend=True,
            socket_buffer=True,
            socket_buffer_size=1048576,
            frame_retention=200000,
            initial_packet_timeout=1000,
            packet_timeout=2000,
            packet_request_ratio=0.25,
            receiver_priority=0,
            buffer_count=2,
        ),
        stop_event=stop_event,
    )
    probe = StreamProbe([opened_stream.target], _stream_config())

    probe._recycle_buffers(opened_stream)

    assert opened_stream.control_lost is True
    assert opened_stream.error == "stream disconnected"


def test_load_aravis_wraps_import_error(monkeypatch: pytest.MonkeyPatch) -> None:
    original_import_module = importlib.import_module

    def fake_import_module(name: str) -> ModuleType:
        if name == "gi":
            raise ImportError("missing gi")
        return original_import_module(name)

    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    with pytest.raises(RuntimeError, match="PyGObject with Aravis bindings"):
        _load_aravis()
