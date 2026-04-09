# pyright: reportMissingImports=false, reportMissingTypeStubs=false, reportUnknownVariableType=false, reportUnknownMemberType=false

from __future__ import annotations

import pytest
from pydantic import ValidationError

from gvstress.config.models import StreamConfig
from gvstress.dut.stream_probe import (
    DiscoveredDevice,
    StreamProbe,
    StreamPropertySnapshot,
    StreamSample,
    StreamTarget,
)


def _stream_config(
    *,
    packet_resend: bool = True,
    socket_buffer: bool = True,
    socket_buffer_size: int = 1048576,
    frame_retention: int = 200000,
    initial_packet_timeout: int = 1000,
    packet_timeout: int = 2000,
    packet_request_ratio: float = 0.25,
    receiver_priority: int = 0,
    buffer_count: int = 16,
) -> StreamConfig:
    return StreamConfig(
        packet_resend=packet_resend,
        socket_buffer=socket_buffer,
        socket_buffer_size=socket_buffer_size,
        frame_retention=frame_retention,
        initial_packet_timeout=initial_packet_timeout,
        packet_timeout=packet_timeout,
        packet_request_ratio=packet_request_ratio,
        receiver_priority=receiver_priority,
        buffer_count=buffer_count,
    )


def test_stream_config_exposes_snapshot_and_applied_properties() -> None:
    config = _stream_config()

    assert config.property_snapshot() == {
        "packet_resend": True,
        "socket_buffer": True,
        "socket_buffer_size": 1048576,
        "frame_retention": 200000,
        "initial_packet_timeout": 1000,
        "packet_timeout": 2000,
        "packet_request_ratio": 0.25,
        "receiver_priority": 0,
        "buffer_count": 16,
    }
    assert config.applied_property_values() == {
        "packet-resend": 1,
        "socket-buffer": 1,
        "socket-buffer-size": 1048576,
        "frame-retention": 200000,
        "initial-packet-timeout": 1000,
        "packet-timeout": 2000,
        "packet-request-ratio": 0.25,
    }


def test_stream_config_rejects_invalid_probe_values() -> None:
    with pytest.raises(ValidationError, match="stream.invalid_packet_request_ratio"):
        _ = _stream_config(packet_request_ratio=2.5)

    with pytest.raises(ValidationError, match="stream.invalid_buffer_count"):
        _ = _stream_config(buffer_count=0)


def test_stream_probe_matches_targets_by_serial_and_ip() -> None:
    targets = [
        StreamTarget(serial_number="CAM-001", ip_address="192.168.10.11"),
        StreamTarget(serial_number="CAM-002", ip_address="192.168.10.12"),
    ]
    devices = [
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
            serial_number="CAM-002",
            ip_address="192.168.10.12",
            vendor="Aravis",
            model="FakeCam",
            protocol="GigEVision",
        ),
    ]

    matches = StreamProbe.match_targets(targets, devices)

    assert [(target.label(), device.device_id) for target, device in matches] == [
        ("CAM-001@192.168.10.11", "dev-a"),
        ("CAM-002@192.168.10.12", "dev-b"),
    ]


def test_stream_sample_serializes_nested_property_snapshot() -> None:
    snapshot = StreamPropertySnapshot(
        timestamp=1.25,
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
        buffer_count=16,
    )
    sample = StreamSample(
        timestamp=2.25,
        interval=1.0,
        serial_number="CAM-001",
        ip_address="192.168.10.11",
        device_id="dev-a",
        n_completed_buffers=10,
        n_failures=1,
        n_underruns=0,
        control_lost=False,
        error=None,
        property_snapshot=snapshot,
    )

    payload = sample.to_dict()

    assert payload["record_type"] == "stream_sample"
    assert payload["interval"] == 1.0
    assert payload["property_snapshot"]["record_type"] == "stream_property_snapshot"
    assert payload["property_snapshot"]["buffer_count"] == 16
    assert payload["n_failures"] == 1
