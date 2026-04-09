# pyright: reportMissingImports=false, reportMissingTypeStubs=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false, reportUnannotatedClassAttribute=false

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from gvstress.core.models import (
    PrimaryAttribution,
    RunValidity,
    ScenarioType,
    SecondaryAttribution,
    Verdict,
)
from gvstress.core.recommended_actions import recommended_actions_for
from gvstress.dut.nic_probe import NICSample
from gvstress.dut.stream_probe import StreamSample
from gvstress.dut.system_probe import SystemSample

CRITICAL_NIC_COUNTERS: tuple[str, ...] = (
    "rx_errors",
    "rx_dropped",
    "rx_over_errors",
    "rx_fifo_errors",
    "rx_missed_errors",
    "tx_errors",
    "tx_dropped",
)

SECONDARY_ATTRIBUTION_BY_PRIMARY: dict[PrimaryAttribution, SecondaryAttribution] = {
    PrimaryAttribution.NIC: SecondaryAttribution.NIC_DRIVER_CONFIGURATION,
    PrimaryAttribution.STREAM: SecondaryAttribution.STREAM_CONFIGURATION,
    PrimaryAttribution.MIXED: SecondaryAttribution.SCENARIO_ORCHESTRATION,
    PrimaryAttribution.ENVIRONMENT: SecondaryAttribution.ENVIRONMENT,
    PrimaryAttribution.UNKNOWN: SecondaryAttribution.SCENARIO_ORCHESTRATION,
}

LIKELY_FAULT_DOMAIN_BY_SECONDARY: dict[SecondaryAttribution, str] = {
    SecondaryAttribution.UNKNOWN: "Unknown",
    SecondaryAttribution.ENVIRONMENT: "Environment",
    SecondaryAttribution.SCENARIO_ORCHESTRATION: "Scenario orchestration",
    SecondaryAttribution.PKTGEN_BASELINE: "Pktgen baseline context",
    SecondaryAttribution.NIC_DRIVER_CONFIGURATION: "NIC driver configuration",
    SecondaryAttribution.STREAM_CONFIGURATION: "Stream configuration",
}


@dataclass(frozen=True, slots=True)
class VerdictThresholds:
    warn_underrun_min: int = 1
    warn_underrun_max: int = 3
    irq_dominance_pct: float = 70.0
    sample_ratio_threshold: float = 0.20
    core_utilization_pct: float = 85.0


@dataclass(frozen=True, slots=True)
class VerdictRule:
    name: str
    priority: int
    description: str


@dataclass(frozen=True, slots=True)
class VerdictContext:
    scenario_type: ScenarioType
    run_validity: RunValidity = RunValidity.VALID
    fake_cameras_survived: bool = True
    all_streams_established_within_warmup: bool = True
    expected_stream_count: int = 0
    warmup_stream_samples: Sequence[StreamSample] = field(default_factory=tuple)
    steady_state_stream_samples: Sequence[StreamSample] = field(default_factory=tuple)
    steady_state_nic_samples: Sequence[NICSample] = field(default_factory=tuple)
    steady_state_system_samples: Sequence[SystemSample] = field(default_factory=tuple)
    targeted_stream: str | None = None


@dataclass(frozen=True, slots=True)
class VerdictDecision:
    verdict: Verdict
    primary_attribution: PrimaryAttribution
    secondary_attribution: SecondaryAttribution
    recommended_actions: tuple[str, ...]
    reasons: tuple[str, ...] = ()


def secondary_attribution_for(
    attribution: PrimaryAttribution,
) -> SecondaryAttribution:
    return SECONDARY_ATTRIBUTION_BY_PRIMARY.get(
        attribution, SecondaryAttribution.UNKNOWN
    )


def likely_fault_domain_for(secondary_attribution: SecondaryAttribution) -> str:
    return LIKELY_FAULT_DOMAIN_BY_SECONDARY.get(secondary_attribution, "Unknown")


@dataclass(frozen=True, slots=True)
class _StreamDelta:
    stream_key: str
    failures_delta: int
    underruns_delta: int
    degraded: bool


@dataclass(frozen=True, slots=True)
class _Evidence:
    critical_nic_counters_zero: bool
    failures_zero: bool
    fake_cameras_survived: bool
    all_streams_established_within_warmup: bool
    stream_deltas: tuple[_StreamDelta, ...]
    nic_signal: bool
    stream_signal: bool
    irq_imbalance_present: bool
    hot_cpu_core_present: bool
    targeted_stream_degraded: bool
    untargeted_streams_clean: bool


class VerdictEngine:
    RULES: tuple[VerdictRule, ...] = (
        VerdictRule(
            name="invalid_run_is_not_applicable",
            priority=1,
            description="Non-valid runs are not applicable and attributed to environment.",
        ),
        VerdictRule(
            name="clean_standard_run_is_pass",
            priority=2,
            description="Smoke, four-stream, and soak pass only when all clean conditions hold.",
        ),
        VerdictRule(
            name="non_injection_minor_degradation_is_warn",
            priority=3,
            description="Minor underruns, IRQ skew, or hot cores warn only without failures or NIC errors.",
        ),
        VerdictRule(
            name="loss_injection_targeted_only_is_warn",
            priority=4,
            description="Loss injection warns only when degradation is limited to the targeted stream.",
        ),
        VerdictRule(
            name="fallback_is_fail",
            priority=5,
            description="Any remaining valid run is a fail.",
        ),
    )

    def __init__(self, *, thresholds: VerdictThresholds | None = None) -> None:
        self._thresholds = thresholds or VerdictThresholds()

    def evaluate(self, context: VerdictContext) -> VerdictDecision:
        if context.run_validity is not RunValidity.VALID:
            return self._decision(
                Verdict.NOT_APPLICABLE,
                PrimaryAttribution.ENVIRONMENT,
                reasons=(f"run_validity:{context.run_validity.value}",),
            )

        evidence = self._collect_evidence(context)

        if context.scenario_type is ScenarioType.LOSS_INJECTION:
            if evidence.targeted_stream_degraded and evidence.untargeted_streams_clean:
                return self._decision(
                    Verdict.WARN,
                    self._detect_attribution(evidence),
                    reasons=("loss_injection:targeted_stream_only",),
                )
            return self._decision(
                Verdict.FAIL,
                self._detect_attribution(evidence),
                reasons=("loss_injection:unexpected_degradation_pattern",),
            )

        if (
            context.scenario_type
            in {ScenarioType.SMOKE, ScenarioType.FOUR_STREAM, ScenarioType.SOAK}
            and evidence.fake_cameras_survived
            and evidence.all_streams_established_within_warmup
            and evidence.failures_zero
            and evidence.critical_nic_counters_zero
            and not evidence.irq_imbalance_present
            and not evidence.hot_cpu_core_present
            and all(delta.underruns_delta == 0 for delta in evidence.stream_deltas)
        ):
            return self._decision(
                Verdict.PASS,
                PrimaryAttribution.UNKNOWN,
                reasons=("standard_run:clean",),
            )

        if (
            context.scenario_type
            in {ScenarioType.SMOKE, ScenarioType.FOUR_STREAM, ScenarioType.SOAK}
            and evidence.critical_nic_counters_zero
            and evidence.failures_zero
            and (
                self._has_minor_underruns_only(evidence.stream_deltas)
                or evidence.irq_imbalance_present
                or evidence.hot_cpu_core_present
            )
        ):
            return self._decision(
                Verdict.WARN,
                self._detect_attribution(evidence),
                reasons=("standard_run:minor_degradation",),
            )

        return self._decision(
            Verdict.FAIL,
            self._detect_attribution(evidence),
            reasons=("standard_run:failure",),
        )

    def _decision(
        self,
        verdict: Verdict,
        attribution: PrimaryAttribution,
        *,
        reasons: tuple[str, ...],
    ) -> VerdictDecision:
        return VerdictDecision(
            verdict=verdict,
            primary_attribution=attribution,
            secondary_attribution=secondary_attribution_for(attribution),
            recommended_actions=recommended_actions_for(attribution),
            reasons=reasons,
        )

    def _collect_evidence(self, context: VerdictContext) -> _Evidence:
        stream_deltas = self._stream_deltas(
            context.steady_state_stream_samples,
            expected_stream_count=context.expected_stream_count,
        )
        irq_imbalance_present = self._irq_imbalance_present(
            context.steady_state_system_samples
        )
        hot_cpu_core_present = self._hot_cpu_core_present(
            context.steady_state_system_samples
        )
        critical_nic_counters_zero = self._critical_nic_counters_zero(
            context.steady_state_nic_samples
        )
        failures_zero = all(delta.failures_delta == 0 for delta in stream_deltas)
        targeted_stream_degraded, untargeted_streams_clean = self._loss_injection_state(
            stream_deltas,
            targeted_stream=context.targeted_stream,
        )

        stream_signal = (
            not context.fake_cameras_survived
            or not context.all_streams_established_within_warmup
            or hot_cpu_core_present
            or any(delta.degraded for delta in stream_deltas)
        )
        nic_signal = (not critical_nic_counters_zero) or irq_imbalance_present
        return _Evidence(
            critical_nic_counters_zero=critical_nic_counters_zero,
            failures_zero=failures_zero,
            fake_cameras_survived=context.fake_cameras_survived,
            all_streams_established_within_warmup=context.all_streams_established_within_warmup,
            stream_deltas=stream_deltas,
            nic_signal=nic_signal,
            stream_signal=stream_signal,
            irq_imbalance_present=irq_imbalance_present,
            hot_cpu_core_present=hot_cpu_core_present,
            targeted_stream_degraded=targeted_stream_degraded,
            untargeted_streams_clean=untargeted_streams_clean,
        )

    def _detect_attribution(self, evidence: _Evidence) -> PrimaryAttribution:
        if evidence.nic_signal and evidence.stream_signal:
            return PrimaryAttribution.MIXED
        if evidence.nic_signal:
            return PrimaryAttribution.NIC
        if evidence.stream_signal:
            return PrimaryAttribution.STREAM
        return PrimaryAttribution.UNKNOWN

    def _stream_deltas(
        self,
        samples: Sequence[StreamSample],
        *,
        expected_stream_count: int,
    ) -> tuple[_StreamDelta, ...]:
        grouped: dict[str, list[StreamSample]] = defaultdict(list)
        for sample in samples:
            grouped[_stream_key(sample)].append(sample)

        if expected_stream_count and len(grouped) != expected_stream_count:
            missing_count = max(0, expected_stream_count - len(grouped))
            for index in range(missing_count):
                grouped[f"missing:{index}"] = []

        deltas: list[_StreamDelta] = []
        for stream_key, stream_samples in sorted(grouped.items()):
            if not stream_samples:
                deltas.append(
                    _StreamDelta(
                        stream_key=stream_key,
                        failures_delta=0,
                        underruns_delta=0,
                        degraded=True,
                    )
                )
                continue
            first = stream_samples[0]
            last = stream_samples[-1]
            failures_delta = max(0, last.n_failures - first.n_failures)
            underruns_delta = max(0, last.n_underruns - first.n_underruns)
            if len(stream_samples) == 1:
                failures_delta = max(0, last.n_failures)
                underruns_delta = max(0, last.n_underruns)
            degraded = (
                failures_delta > 0
                or underruns_delta > 0
                or any(sample.control_lost or sample.error for sample in stream_samples)
            )
            deltas.append(
                _StreamDelta(
                    stream_key=stream_key,
                    failures_delta=failures_delta,
                    underruns_delta=underruns_delta,
                    degraded=degraded,
                )
            )
        return tuple(deltas)

    def _critical_nic_counters_zero(self, samples: Sequence[NICSample]) -> bool:
        for sample in samples:
            for interface_sample in sample.interfaces.values():
                for counter_name in CRITICAL_NIC_COUNTERS:
                    counter = interface_sample.standard_counters.get(counter_name)
                    if counter is None:
                        continue
                    delta = counter.delta if counter.delta is not None else 0
                    absolute = counter.absolute if counter.absolute is not None else 0
                    if delta > 0 or absolute > 0:
                        return False
        return True

    def _irq_imbalance_present(self, samples: Sequence[SystemSample]) -> bool:
        flagged = 0
        total = 0
        for sample in samples:
            for interface in sample.interfaces.values():
                if not interface.delta_counts:
                    continue
                total += 1
                total_delta = sum(interface.delta_counts.values())
                if total_delta <= 0 or interface.dominant_cpu is None:
                    continue
                dominant_delta = interface.delta_counts.get(interface.dominant_cpu, 0)
                if (
                    dominant_delta / total_delta * 100.0
                    >= self._thresholds.irq_dominance_pct
                ):
                    flagged += 1
        return _meets_sample_ratio(
            flagged, total, self._thresholds.sample_ratio_threshold
        )

    def _hot_cpu_core_present(self, samples: Sequence[SystemSample]) -> bool:
        flagged = 0
        total = 0
        for sample in samples:
            core_usages = [
                cpu.usage_pct
                for cpu_name, cpu in sample.cpus.items()
                if cpu_name != "cpu"
            ]
            valid_usages = [usage for usage in core_usages if usage is not None]
            if not valid_usages:
                continue
            total += 1
            if max(valid_usages) >= self._thresholds.core_utilization_pct:
                flagged += 1
        return _meets_sample_ratio(
            flagged, total, self._thresholds.sample_ratio_threshold
        )

    def _loss_injection_state(
        self,
        stream_deltas: Sequence[_StreamDelta],
        *,
        targeted_stream: str | None,
    ) -> tuple[bool, bool]:
        if targeted_stream is None:
            return False, False
        targeted = None
        untargeted: list[_StreamDelta] = []
        for delta in stream_deltas:
            if delta.stream_key == targeted_stream:
                targeted = delta
            else:
                untargeted.append(delta)
        if targeted is None:
            return False, False
        return targeted.degraded, all(not delta.degraded for delta in untargeted)

    def _has_minor_underruns_only(self, stream_deltas: Iterable[_StreamDelta]) -> bool:
        deltas = tuple(stream_deltas)
        if not deltas:
            return False
        return any(
            self._thresholds.warn_underrun_min
            <= delta.underruns_delta
            <= self._thresholds.warn_underrun_max
            for delta in deltas
        ) and all(delta.failures_delta == 0 for delta in deltas)


def _stream_key(sample: StreamSample) -> str:
    return f"{sample.serial_number}@{sample.ip_address}"


def _meets_sample_ratio(flagged: int, total: int, threshold: float) -> bool:
    if total <= 0:
        return False
    return flagged / total >= threshold
