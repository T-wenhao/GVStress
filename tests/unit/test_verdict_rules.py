# pyright: reportMissingImports=false, reportMissingTypeStubs=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false

from __future__ import annotations

from gvstress.core.models import PrimaryAttribution, RunValidity, ScenarioType, Verdict
from gvstress.core.verdict import VerdictContext, VerdictEngine
from gvstress.dut.nic_probe import CounterSample, NICInterfaceSample, NICSample
from gvstress.dut.stream_probe import StreamPropertySnapshot, StreamSample
from gvstress.dut.system_probe import (
    CPUCoreSample,
    InterfaceIRQSample,
    IRQLineSample,
    SystemSample,
)


def _stream_sample(
    serial_number: str,
    ip_address: str,
    *,
    failures: int = 0,
    underruns: int = 0,
    control_lost: bool = False,
    error: str | None = None,
    timestamp: float = 1.0,
) -> StreamSample:
    snapshot = StreamPropertySnapshot(
        timestamp=timestamp,
        serial_number=serial_number,
        ip_address=ip_address,
        device_id=f"dev-{serial_number}",
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
    return StreamSample(
        timestamp=timestamp,
        interval=1.0,
        serial_number=serial_number,
        ip_address=ip_address,
        device_id=snapshot.device_id,
        n_completed_buffers=100,
        n_failures=failures,
        n_underruns=underruns,
        control_lost=control_lost,
        error=error,
        property_snapshot=snapshot,
    )


def _counter(value: int = 0) -> CounterSample:
    return CounterSample(absolute=value, delta=value, available=True)


def _nic_sample(*, critical_counter_value: int = 0) -> NICSample:
    counters = {
        "rx_errors": _counter(critical_counter_value),
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
        timestamp=1.0,
        interval=1.0,
        interfaces={"eno1": interface},
        aggregate_standard_counters=counters,
        aggregate_driver_counters={},
    )


def _system_sample(
    *,
    dominant_cpu_delta: int = 30,
    other_cpu_delta: int = 30,
    cpu0_usage_pct: float = 40.0,
    cpu1_usage_pct: float = 40.0,
) -> SystemSample:
    delta_counts = {"CPU0": dominant_cpu_delta, "CPU1": other_cpu_delta}
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
        timestamp=1.0,
        interval=1.0,
        cpus={
            "cpu": CPUCoreSample(counters={}, deltas=None, usage_pct=None),
            "cpu0": CPUCoreSample(counters={}, deltas={}, usage_pct=cpu0_usage_pct),
            "cpu1": CPUCoreSample(counters={}, deltas={}, usage_pct=cpu1_usage_pct),
        },
        interfaces={"eno1": interface},
    )


def test_valid_clean_four_stream_run_is_pass() -> None:
    engine = VerdictEngine()
    decision = engine.evaluate(
        VerdictContext(
            scenario_type=ScenarioType.FOUR_STREAM,
            run_validity=RunValidity.VALID,
            fake_cameras_survived=True,
            all_streams_established_within_warmup=True,
            expected_stream_count=4,
            steady_state_stream_samples=[
                _stream_sample("CAM-001", "192.168.10.11"),
                _stream_sample("CAM-002", "192.168.10.12"),
                _stream_sample("CAM-003", "192.168.10.13"),
                _stream_sample("CAM-004", "192.168.10.14"),
            ],
            steady_state_nic_samples=[_nic_sample()],
            steady_state_system_samples=[_system_sample()],
        )
    )

    assert decision.verdict is Verdict.PASS
    assert decision.primary_attribution is PrimaryAttribution.UNKNOWN
    assert decision.recommended_actions == ()


def test_loss_injection_detected_is_warn() -> None:
    engine = VerdictEngine()
    decision = engine.evaluate(
        VerdictContext(
            scenario_type=ScenarioType.LOSS_INJECTION,
            targeted_stream="CAM-001@192.168.10.11",
            expected_stream_count=2,
            steady_state_stream_samples=[
                _stream_sample("CAM-001", "192.168.10.11", underruns=2),
                _stream_sample("CAM-002", "192.168.10.12", underruns=0),
            ],
            steady_state_nic_samples=[_nic_sample()],
        )
    )

    assert decision.verdict is Verdict.WARN
    assert decision.primary_attribution is PrimaryAttribution.STREAM


def test_invalid_telemetry_run_is_not_applicable() -> None:
    engine = VerdictEngine()
    decision = engine.evaluate(
        VerdictContext(
            scenario_type=ScenarioType.SOAK,
            run_validity=RunValidity.INVALID_TELEMETRY,
        )
    )

    assert decision.verdict is Verdict.NOT_APPLICABLE
    assert decision.primary_attribution is PrimaryAttribution.ENVIRONMENT


def test_non_injection_minor_stream_degradation_is_warn() -> None:
    engine = VerdictEngine()
    decision = engine.evaluate(
        VerdictContext(
            scenario_type=ScenarioType.SMOKE,
            expected_stream_count=1,
            steady_state_stream_samples=[
                _stream_sample("CAM-001", "192.168.10.11", underruns=2),
            ],
            steady_state_nic_samples=[_nic_sample()],
        )
    )

    assert decision.verdict is Verdict.WARN
    assert decision.primary_attribution is PrimaryAttribution.STREAM


def test_irq_imbalance_warns_and_attributes_nic() -> None:
    engine = VerdictEngine()
    decision = engine.evaluate(
        VerdictContext(
            scenario_type=ScenarioType.SOAK,
            expected_stream_count=1,
            steady_state_stream_samples=[_stream_sample("CAM-001", "192.168.10.11")],
            steady_state_nic_samples=[_nic_sample()],
            steady_state_system_samples=[
                _system_sample(dominant_cpu_delta=80, other_cpu_delta=20),
                _system_sample(dominant_cpu_delta=80, other_cpu_delta=20),
                _system_sample(dominant_cpu_delta=50, other_cpu_delta=50),
                _system_sample(dominant_cpu_delta=50, other_cpu_delta=50),
                _system_sample(dominant_cpu_delta=50, other_cpu_delta=50),
            ],
        )
    )

    assert decision.verdict is Verdict.WARN
    assert decision.primary_attribution is PrimaryAttribution.NIC


def test_hot_cpu_warns_and_attributes_stream() -> None:
    engine = VerdictEngine()
    decision = engine.evaluate(
        VerdictContext(
            scenario_type=ScenarioType.SMOKE,
            expected_stream_count=1,
            steady_state_stream_samples=[_stream_sample("CAM-001", "192.168.10.11")],
            steady_state_nic_samples=[_nic_sample()],
            steady_state_system_samples=[
                _system_sample(cpu0_usage_pct=90.0),
                _system_sample(cpu0_usage_pct=90.0),
                _system_sample(cpu0_usage_pct=40.0),
                _system_sample(cpu0_usage_pct=40.0),
                _system_sample(cpu0_usage_pct=40.0),
            ],
        )
    )

    assert decision.verdict is Verdict.WARN
    assert decision.primary_attribution is PrimaryAttribution.STREAM


def test_non_clean_run_falls_back_to_mixed_fail() -> None:
    engine = VerdictEngine()
    decision = engine.evaluate(
        VerdictContext(
            scenario_type=ScenarioType.FOUR_STREAM,
            fake_cameras_survived=False,
            expected_stream_count=1,
            steady_state_stream_samples=[
                _stream_sample("CAM-001", "192.168.10.11", failures=5),
            ],
            steady_state_nic_samples=[_nic_sample(critical_counter_value=1)],
        )
    )

    assert decision.verdict is Verdict.FAIL
    assert decision.primary_attribution is PrimaryAttribution.MIXED
