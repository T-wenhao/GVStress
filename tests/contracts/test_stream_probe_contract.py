# pyright: reportMissingImports=false, reportMissingTypeStubs=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false

from __future__ import annotations

import json
from typing import cast

import pytest
from typer.testing import CliRunner

from gvstress.cli.main import app as main_app
from gvstress.config.models import StreamConfig
from gvstress.dut.stream_probe import (
    StreamPropertySnapshot,
    StreamSample,
    StreamTarget,
)


def test_stream_runner_emits_json_records(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeProbe:
        def __init__(
            self,
            targets: list[StreamTarget],
            stream_config: StreamConfig,
            *,
            sample_interval_s: float,
            **kwargs: object,
        ) -> None:
            _ = kwargs
            assert [target.label() for target in targets] == ["CAM-001@192.168.10.11"]
            assert stream_config.buffer_count == 16
            assert stream_config.packet_resend is True
            assert sample_interval_s == 1.0

        def run(self, *, duration: float | None = None):
            assert duration == 0.0
            snapshot = StreamPropertySnapshot(
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
                buffer_count=16,
            )
            yield snapshot
            yield StreamSample(
                timestamp=2.0,
                interval=1.0,
                serial_number="CAM-001",
                ip_address="192.168.10.11",
                device_id="dev-a",
                n_completed_buffers=4,
                n_failures=0,
                n_underruns=0,
                control_lost=False,
                error=None,
                property_snapshot=snapshot,
            )

    monkeypatch.setattr("gvstress.cli.dut_agent.StreamProbe", FakeProbe)

    result = CliRunner().invoke(
        main_app,
        [
            "dut-agent",
            "stream-runner",
            "--camera",
            "CAM-001@192.168.10.11",
            "--duration",
            "0",
            "--json",
        ],
    )

    assert result.exit_code == 0
    payloads = [
        cast(dict[str, object], json.loads(line))
        for line in result.stdout.splitlines()
        if line.strip()
    ]
    sample_payload = payloads[1]
    property_snapshot = cast(dict[str, object], sample_payload["property_snapshot"])
    assert [payload["record_type"] for payload in payloads] == [
        "stream_property_snapshot",
        "stream_sample",
    ]
    assert property_snapshot["packet_timeout"] == 2000
    assert sample_payload["n_completed_buffers"] == 4


def test_stream_runner_rejects_invalid_camera_selector() -> None:
    result = CliRunner().invoke(
        main_app,
        ["dut-agent", "stream-runner", "--camera", "invalid-selector", "--json"],
    )

    assert result.exit_code != 0
    assert "SERIAL@IP" in result.output
