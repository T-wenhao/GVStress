# pyright: reportMissingTypeStubs=false, reportUnannotatedClassAttribute=false

from __future__ import annotations

from dataclasses import dataclass

from gvstress.core.models import ScenarioType


@dataclass(frozen=True, slots=True)
class ScenarioPhase:
    name: str
    duration_seconds: int
    sample_count: int


@dataclass(frozen=True, slots=True)
class ScenarioPlan:
    scenario_type: ScenarioType
    startup_phase: str
    sample_interval_ms: int
    warmup_seconds: int
    steady_state_seconds: int
    cooldown_seconds: int
    phases: tuple[ScenarioPhase, ...]

    @property
    def lifecycle(self) -> tuple[str, ...]:
        return tuple(phase.name for phase in self.phases)

    @property
    def total_collection_seconds(self) -> int:
        return self.warmup_seconds + self.steady_state_seconds + self.cooldown_seconds

    @property
    def total_sample_count(self) -> int:
        return sum(phase.sample_count for phase in self.timed_phases)

    @property
    def timed_phases(self) -> tuple[ScenarioPhase, ...]:
        return tuple(
            phase
            for phase in self.phases
            if phase.name in {"warmup", "steady_state", "cooldown"}
        )


class ScenarioEngine:
    DEFAULT_SAMPLE_INTERVAL_MS = 1000
    DEFAULT_WARMUP_SECONDS = 10
    DEFAULT_COOLDOWN_SECONDS = 5
    STEADY_STATE_DURATIONS: dict[ScenarioType, int] = {
        ScenarioType.SMOKE: 60,
        ScenarioType.FOUR_STREAM: 300,
        ScenarioType.SOAK: 1800,
        ScenarioType.LOSS_INJECTION: 300,
        ScenarioType.PKTGEN_BASELINE: 300,
    }

    def __init__(
        self,
        *,
        sample_interval_ms: int = DEFAULT_SAMPLE_INTERVAL_MS,
        warmup_seconds: int = DEFAULT_WARMUP_SECONDS,
        cooldown_seconds: int = DEFAULT_COOLDOWN_SECONDS,
    ) -> None:
        if sample_interval_ms <= 0:
            raise ValueError("sample_interval_ms must be positive")
        if warmup_seconds < 0:
            raise ValueError("warmup_seconds must be non-negative")
        if cooldown_seconds < 0:
            raise ValueError("cooldown_seconds must be non-negative")
        self._sample_interval_ms = sample_interval_ms
        self._warmup_seconds = warmup_seconds
        self._cooldown_seconds = cooldown_seconds

    @property
    def sample_interval_ms(self) -> int:
        return self._sample_interval_ms

    @property
    def warmup_seconds(self) -> int:
        return self._warmup_seconds

    @property
    def cooldown_seconds(self) -> int:
        return self._cooldown_seconds

    def build_plan(self, scenario_type: ScenarioType) -> ScenarioPlan:
        steady_state_seconds = self.STEADY_STATE_DURATIONS[scenario_type]
        startup_phase = self.startup_phase_for(scenario_type)
        phases = (
            ScenarioPhase(name="preflight", duration_seconds=0, sample_count=0),
            ScenarioPhase(name=startup_phase, duration_seconds=0, sample_count=0),
            ScenarioPhase(name="dut_prepare", duration_seconds=0, sample_count=0),
            ScenarioPhase(
                name="warmup",
                duration_seconds=self._warmup_seconds,
                sample_count=self._samples_for_seconds(self._warmup_seconds),
            ),
            ScenarioPhase(
                name="steady_state",
                duration_seconds=steady_state_seconds,
                sample_count=self._samples_for_seconds(steady_state_seconds),
            ),
            ScenarioPhase(
                name="cooldown",
                duration_seconds=self._cooldown_seconds,
                sample_count=self._samples_for_seconds(self._cooldown_seconds),
            ),
            ScenarioPhase(name="teardown", duration_seconds=0, sample_count=0),
            ScenarioPhase(name="reporting", duration_seconds=0, sample_count=0),
        )
        return ScenarioPlan(
            scenario_type=scenario_type,
            startup_phase=startup_phase,
            sample_interval_ms=self._sample_interval_ms,
            warmup_seconds=self._warmup_seconds,
            steady_state_seconds=steady_state_seconds,
            cooldown_seconds=self._cooldown_seconds,
            phases=phases,
        )

    @staticmethod
    def startup_phase_for(scenario_type: ScenarioType) -> str:
        if scenario_type is ScenarioType.PKTGEN_BASELINE:
            return "pktgen_prepare"
        return "fakecam_up"

    def _samples_for_seconds(self, duration_seconds: int) -> int:
        if duration_seconds == 0:
            return 0
        interval_seconds = self._sample_interval_ms / 1000
        samples = duration_seconds / interval_seconds
        if int(samples) != samples:
            raise ValueError(
                "scenario durations must align to the fixed sample interval in V1"
            )
        return int(samples)
