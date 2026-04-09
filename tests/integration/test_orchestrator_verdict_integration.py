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
from gvstress.core.recommended_actions import (
    ENVIRONMENT_RECOMMENDED_ACTIONS,
    STREAM_RECOMMENDED_ACTIONS,
)
from gvstress.core.scenario_engine import ScenarioEngine, ScenarioPlan
from gvstress.dut.environment import EnvironmentSnapshot, InterfaceSnapshot
from gvstress.dut.nic_probe import CounterSample, NICInterfaceSample, NICSample
from gvstress.dut.stream_probe import StreamPropertySnapshot, StreamSample
from gvstress.dut.system_probe import (
    CPUCoreSample,
    InterfaceIRQSample,
    IRQLineSample,
    SystemSample,
)


class ManualClock:
    def __init__(self) -> None:
        self.current = 0.0

    def __call__(self) -> float:
        return self.current

    def sleep(self, seconds: float) -> None:
        self.current += seconds


class SequenceProbe:
    def __init__(self, samples: list[object]) -> None:
        self._samples = deque(samples)

    def collect(self) -> object:
        if not self._samples:
            raise AssertionError("probe exhausted")
        return self._samples.popleft()


class SequenceStreamProbe:
    def __init__(self, samples: list[list[StreamSample]]) -> None:
        self._samples = deque(samples)

    def collect(self) -> list[StreamSample]:
        if not self._samples:
            raise AssertionError("stream probe exhausted")
        return self._samples.popleft()


class FakeManager:
    def __init__(self, statuses: list[int]) -> None:
        self._statuses = deque(statuses)

    def up(self) -> dict[str, object]:
        running_count = self._statuses[0] if self._statuses else 0
        return {"camera_count": 1, "running_count": running_count}

    def status(self) -> dict[str, object]:
        running_count = self._statuses.popleft() if self._statuses else 0
        return {"camera_count": 1, "running_count": running_count}

    def down(self) -> dict[str, object]:
        return {"stopped_count": 1}

    def archive_logs(self) -> list[str]:
        return []


class FakePrepare:
    def prepare(self) -> None:
        return None


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


def _counter(value: int = 0) -> CounterSample:
    return CounterSample(absolute=value, delta=value, available=True)


def _nic_sample(*, timestamp: float) -> NICSample:
    counters = {
        "rx_errors": _counter(0),
        "rx_dropped": _counter(0),
        "rx_over_errors": _counter(0),
        "rx_fifo_errors": _counter(0),
        "rx_missed_errors": _counter(0),
        "tx_errors": _counter(0),
        "tx_dropped": _counter(0),
    }
    interface = NICInterfaceSample(
        name="eno1",
        standard_counters=counters,
        driver_counters={},
        aggregate_driver_counter=CounterSample(absolute=0, delta=0, available=True),
        driver_info={},
        features={},
        channels={},
        source={},
    )
    return NICSample(
        timestamp=timestamp,
        interval=1.0,
        interfaces={"eno1": interface},
        aggregate_standard_counters=counters,
        aggregate_driver_counters={},
    )


def _system_sample(*, timestamp: float) -> SystemSample:
    delta_counts = {"CPU0": 50, "CPU1": 50}
    interface = InterfaceIRQSample(
        interface="eno1",
        irqs=[
            IRQLineSample(
                irq="45",
                cpu_counts={"CPU0": 100, "CPU1": 100},
                delta_counts=delta_counts,
                description="eno1-TxRx-0",
            )
        ],
        total_counts={"CPU0": 100, "CPU1": 100},
        delta_counts=delta_counts,
        dominant_cpu="CPU0",
    )
    return SystemSample(
        timestamp=timestamp,
        interval=1.0,
        cpus={
            "cpu": CPUCoreSample(counters={}, deltas=None, usage_pct=None),
            "cpu0": CPUCoreSample(counters={}, deltas={}, usage_pct=40.0),
            "cpu1": CPUCoreSample(counters={}, deltas={}, usage_pct=40.0),
        },
        interfaces={"eno1": interface},
    )


def _stream_sample(*, timestamp: float, underruns: int = 0) -> StreamSample:
    snapshot = StreamPropertySnapshot(
        timestamp=timestamp,
        serial_number="CAM-001",
        ip_address="192.168.10.11",
        device_id="dev-CAM-001",
        packet_resend=True,
        socket_buffer=True,
        socket_buffer_size=262144,
        frame_retention=30,
        initial_packet_timeout=500,
        packet_timeout=100,
        packet_request_ratio=0.1,
        receiver_priority=5,
        buffer_count=16,
    )
    return StreamSample(
        timestamp=timestamp,
        interval=1.0,
        serial_number="CAM-001",
        ip_address="192.168.10.11",
        device_id=snapshot.device_id,
        n_completed_buffers=100,
        n_failures=0,
        n_underruns=underruns,
        control_lost=False,
        error=None,
        property_snapshot=snapshot,
    )


def _build_stream_batches(
    plan: ScenarioPlan, *, steady_state_underruns: int = 0
) -> list[list[StreamSample]]:
    batches: list[list[StreamSample]] = []
    timestamp = 0.0
    for phase in plan.timed_phases:
        for sample_index in range(phase.sample_count):
            underruns = 0
            if phase.name == "steady_state" and sample_index > 0:
                underruns = steady_state_underruns
            batches.append([_stream_sample(timestamp=timestamp, underruns=underruns)])
            timestamp += 1.0
    return batches


def _build_orchestrator(
    tmp_path: Path,
    *,
    clock: ManualClock,
    scenario_engine: ScenarioEngine,
    fakecam_statuses: list[int],
    stream_batches: list[list[StreamSample]],
    run_validity_evaluator=None,
) -> RunOrchestrator:
    plan = scenario_engine.build_plan(ScenarioType.SMOKE)
    timestamps = [float(index) for index in range(plan.total_sample_count)]
    return RunOrchestrator(
        scenario_type=ScenarioType.SMOKE,
        output_root=tmp_path,
        preflight_runner=_build_preflight_result,
        scenario_engine=scenario_engine,
        fakecam_manager=FakeManager(fakecam_statuses),
        dut_prepare=FakePrepare(),
        nic_probe=SequenceProbe([_nic_sample(timestamp=value) for value in timestamps]),
        system_probe=SequenceProbe(
            [_system_sample(timestamp=value) for value in timestamps]
        ),
        stream_probe=SequenceStreamProbe(stream_batches),
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


def test_orchestrator_uses_verdict_engine_for_valid_run(tmp_path: Path) -> None:
    clock = ManualClock()
    scenario_engine = ScenarioEngine()
    plan = scenario_engine.build_plan(ScenarioType.SMOKE)
    orchestrator = _build_orchestrator(
        tmp_path,
        clock=clock,
        scenario_engine=scenario_engine,
        fakecam_statuses=[1] * plan.total_sample_count,
        stream_batches=_build_stream_batches(plan, steady_state_underruns=2),
    )

    result = orchestrator.run()
    run_report = json.loads(result.artifacts.run_json_path.read_text(encoding="utf-8"))
    summary = result.artifacts.summary_md_path.read_text(encoding="utf-8")

    assert result.aborted is False
    assert result.run_validity is RunValidity.VALID
    assert run_report["verdict"] == "warn"
    assert run_report["verdict"] != "pass"
    assert run_report["primary_attribution"] == "stream"
    assert run_report["secondary_attribution"] == "stream_configuration"
    assert run_report["recommended_actions"] == list(STREAM_RECOMMENDED_ACTIONS)
    assert "**Result:** ⚠️ WARN" in summary
    assert "**Primary Attribution:** stream" in summary
    assert "**Secondary Attribution:** stream_configuration" in summary
    assert "Tune stream socket buffer sizing on the receiver." in summary


def test_invalid_run_maps_to_not_applicable_via_engine_contract(
    tmp_path: Path,
) -> None:
    clock = ManualClock()
    scenario_engine = ScenarioEngine()
    plan = scenario_engine.build_plan(ScenarioType.SMOKE)

    def evaluator(context: dict[str, object]) -> RunValidity:
        if context["phase"] == "steady_state" and context["sample_index"] == 3:
            return RunValidity.INVALID_TELEMETRY
        return RunValidity.VALID

    orchestrator = _build_orchestrator(
        tmp_path,
        clock=clock,
        scenario_engine=scenario_engine,
        fakecam_statuses=[1] * plan.total_sample_count,
        stream_batches=_build_stream_batches(plan),
        run_validity_evaluator=evaluator,
    )

    result = orchestrator.run()
    run_report = json.loads(result.artifacts.run_json_path.read_text(encoding="utf-8"))
    summary = result.artifacts.summary_md_path.read_text(encoding="utf-8")

    assert result.aborted is True
    assert result.run_validity is RunValidity.INVALID_TELEMETRY
    assert run_report["verdict"] == "not_applicable"
    assert run_report["primary_attribution"] == "environment"
    assert run_report["secondary_attribution"] == "environment"
    assert run_report["recommended_actions"] == list(ENVIRONMENT_RECOMMENDED_ACTIONS)
    assert "**Result:** ➖ NOT_APPLICABLE" in summary
    assert "**Primary Attribution:** environment" in summary
    assert "**Secondary Attribution:** environment" in summary
    assert "Run preflight remediation before rerunning the scenario." in summary
