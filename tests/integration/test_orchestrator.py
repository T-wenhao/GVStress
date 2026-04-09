# pyright: reportMissingImports=false, reportMissingTypeStubs=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnannotatedClassAttribute=false, reportReturnType=false, reportIndexIssue=false, reportArgumentType=false, reportAny=false

from __future__ import annotations

import json
from collections import deque
from pathlib import Path

from gvstress.config.models import (
    DUTCollectOptions,
    DUTConfig,
    FakeCameraConfig,
    StreamConfig,
)
from gvstress.core.models import RunValidity, ScenarioType
from gvstress.core.orchestrator import RunOrchestrator
from gvstress.core.preflight import PreflightCheck, PreflightResult
from gvstress.dut.environment import EnvironmentSnapshot, InterfaceSnapshot


class ManualClock:
    def __init__(self) -> None:
        self.current = 0.0

    def __call__(self) -> float:
        return self.current

    def sleep(self, seconds: float) -> None:
        self.current += seconds


class FakeProbe:
    def __init__(self, prefix: str, clock: ManualClock) -> None:
        self._prefix = prefix
        self._clock = clock
        self._index = 0

    def collect(self) -> dict[str, object]:
        payload = {
            "record_type": f"{self._prefix}_sample",
            "timestamp": self._clock(),
            "index": self._index,
        }
        self._index += 1
        return payload


class FakeStreamProbe:
    def __init__(self, samples: list[list[dict[str, object]]]) -> None:
        self._samples = deque(samples)

    def collect(self) -> list[dict[str, object]]:
        if not self._samples:
            return []
        return self._samples.popleft()


class FakeManager:
    def __init__(self, statuses: list[int]) -> None:
        self._statuses = deque(statuses)
        self.started = 0
        self.stopped = 0

    def up(self) -> dict[str, object]:
        self.started += 1
        return {"running_count": self._statuses[0] if self._statuses else 0}

    def status(self) -> dict[str, object]:
        running_count = self._statuses.popleft() if self._statuses else 0
        return {"running_count": running_count}

    def down(self) -> dict[str, object]:
        self.stopped += 1
        return {"stopped_count": self.stopped}

    def archive_logs(self) -> list[str]:
        return []


class FakePrepare:
    def __init__(self) -> None:
        self.calls = 0

    def prepare(self) -> None:
        self.calls += 1


def _build_preflight_result() -> PreflightResult:
    snapshot = EnvironmentSnapshot(
        hostname="host",
        platform="linux",
        python_version="3.11.0",
        interfaces=[
            InterfaceSnapshot(
                name="eno1",
                ip_addresses=["192.168.10.11"],
                driver="igb",
                driver_version="1.0",
                firmware="1.0",
                mtu=9000,
                speed=1000,
                link_state="UP",
                link_up=True,
            )
        ],
        required_binaries={"python3": True, "ip": True, "ethtool": True},
        sudo_available=True,
        arv_fake_camera_present=True,
        pktgen_available=True,
        msix_detected=True,
        irqbalance_detected=True,
    )
    return PreflightResult(
        run_validity=RunValidity.VALID,
        reasons=[],
        checks=[
            PreflightCheck(name="ssh", passed=True, reasons=[]),
            PreflightCheck(name="binaries", passed=True, reasons=[]),
            PreflightCheck(name="privileges", passed=True, reasons=[]),
            PreflightCheck(name="interfaces", passed=True, reasons=[]),
            PreflightCheck(name="link_state", passed=True, reasons=[]),
        ],
        generator_environment=snapshot,
        dut_environment=snapshot,
    )


def _build_orchestrator(
    tmp_path: Path,
    *,
    clock: ManualClock,
    fakecam_statuses: list[int],
    stream_batches: list[list[dict[str, object]]],
    run_validity_evaluator=None,
) -> RunOrchestrator:
    return RunOrchestrator(
        scenario_type=ScenarioType.SMOKE,
        output_root=tmp_path,
        preflight_runner=_build_preflight_result,
        fakecam_manager=FakeManager(fakecam_statuses),
        dut_prepare=FakePrepare(),
        nic_probe=FakeProbe("nic", clock),
        system_probe=FakeProbe("system", clock),
        stream_probe=FakeStreamProbe(stream_batches),
        run_validity_evaluator=run_validity_evaluator,
        fake_camera_config=FakeCameraConfig(
            ip_address="192.168.10.11",
            interface_name="eno1",
            serial_number="CAM-001",
            genicam_filename="camera.xml",
            gvsp_lost_ratio=0.0,
        ),
        dut_config=DUTConfig(
            ifaces=["eno1"],
            sample_interval_ms=1000,
            collect=DUTCollectOptions(nic=True, stream=True, system=True),
        ),
        stream_config=StreamConfig(
            packet_resend=True,
            socket_buffer=True,
            socket_buffer_size=262144,
            frame_retention=30,
            initial_packet_timeout=500,
            packet_timeout=100,
            packet_request_ratio=0.1,
            receiver_priority=5,
        ),
        clock=clock,
        sleep=clock.sleep,
        run_id_factory=lambda: "run-001",
    )


def test_partial_stream_failure_does_not_abort_before_reportable_evidence(
    tmp_path: Path,
) -> None:
    clock = ManualClock()
    total_samples = 75
    stream_batches = []
    for index in range(total_samples):
        batch = [
            {
                "record_type": "stream_sample",
                "serial_number": "CAM-001",
                "timestamp": float(index),
                "n_failures": 1 if index == 20 else 0,
                "error": "partial degradation" if index == 20 else None,
            },
            {
                "record_type": "stream_sample",
                "serial_number": "CAM-002",
                "timestamp": float(index),
                "n_failures": 0,
                "error": None,
            },
        ]
        stream_batches.append(batch)

    orchestrator = _build_orchestrator(
        tmp_path,
        clock=clock,
        fakecam_statuses=[2] * total_samples,
        stream_batches=stream_batches,
    )

    result = orchestrator.run()

    assert result.aborted is False
    assert result.run_validity is RunValidity.VALID
    assert result.sample_counts["nic"] == total_samples
    assert result.sample_counts["system"] == total_samples
    assert result.sample_counts["stream"] == total_samples * 2
    assert result.transitions == [
        "preflight",
        "fakecam_up",
        "dut_prepare",
        "warmup",
        "steady_state",
        "cooldown",
        "teardown",
        "reporting",
    ]

    stream_lines = _read_jsonl(result.artifacts.stream_path)
    assert any(
        line["payload"]["error"] == "partial degradation" for line in stream_lines
    )
    assert len(stream_lines) == total_samples * 2

    event_lines = _read_jsonl(result.artifacts.events_path)
    assert [
        line["to_state"]
        for line in event_lines
        if line["record_type"] == "state_transition"
    ] == result.transitions
    assert all(line["run_id"] == result.run_id for line in event_lines)
    assert [line["timestamp"] for line in event_lines] == sorted(
        line["timestamp"] for line in event_lines
    )


def test_all_fake_cameras_missing_for_more_than_two_intervals_aborts_run(
    tmp_path: Path,
) -> None:
    clock = ManualClock()
    orchestrator = _build_orchestrator(
        tmp_path,
        clock=clock,
        fakecam_statuses=[2] * 5 + [0, 0, 0] + [2] * 10,
        stream_batches=[
            [{"record_type": "stream_sample", "serial_number": "CAM-001"}]
            for _ in range(75)
        ],
    )

    result = orchestrator.run()

    assert result.aborted is True
    assert result.run_validity is RunValidity.INTERRUPTED
    assert result.abort_reason == "fakecam_disappeared"
    assert result.sample_counts["nic"] == 8
    assert result.transitions[-2:] == ["teardown", "reporting"]


def test_non_valid_run_validity_aborts_and_is_reflected_in_report(
    tmp_path: Path,
) -> None:
    clock = ManualClock()

    def evaluator(context: dict[str, object]) -> RunValidity:
        if context["phase"] == "steady_state" and context["sample_index"] == 3:
            return RunValidity.INVALID_TELEMETRY
        return RunValidity.VALID

    orchestrator = _build_orchestrator(
        tmp_path,
        clock=clock,
        fakecam_statuses=[2] * 75,
        stream_batches=[
            [{"record_type": "stream_sample", "serial_number": "CAM-001"}]
            for _ in range(75)
        ],
        run_validity_evaluator=evaluator,
    )

    result = orchestrator.run()
    run_report = json.loads(result.artifacts.run_json_path.read_text(encoding="utf-8"))

    assert result.aborted is True
    assert result.run_validity is RunValidity.INVALID_TELEMETRY
    assert run_report["run_validity"] == "invalid_telemetry"
    assert run_report["verdict"] == "not_applicable"
    assert run_report["primary_attribution"] == "environment"


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
