# pyright: reportMissingImports=false, reportMissingTypeStubs=false, reportUnknownVariableType=false, reportUnknownMemberType=false

from __future__ import annotations

from gvstress.core.models import ScenarioType
from gvstress.core.scenario_engine import ScenarioEngine


def test_fixed_scenario_durations_and_phase_order() -> None:
    engine = ScenarioEngine()

    expected = {
        ScenarioType.SMOKE: ("fakecam_up", 60),
        ScenarioType.FOUR_STREAM: ("fakecam_up", 300),
        ScenarioType.SOAK: ("fakecam_up", 1800),
        ScenarioType.LOSS_INJECTION: ("fakecam_up", 300),
        ScenarioType.PKTGEN_BASELINE: ("pktgen_prepare", 300),
    }

    for scenario_type, (startup_phase, steady_seconds) in expected.items():
        plan = engine.build_plan(scenario_type)

        assert plan.sample_interval_ms == 1000
        assert plan.warmup_seconds == 10
        assert plan.cooldown_seconds == 5
        assert plan.steady_state_seconds == steady_seconds
        assert plan.lifecycle == (
            "preflight",
            startup_phase,
            "dut_prepare",
            "warmup",
            "steady_state",
            "cooldown",
            "teardown",
            "reporting",
        )
        assert {phase.name: phase.sample_count for phase in plan.timed_phases} == {
            "warmup": 10,
            "steady_state": steady_seconds,
            "cooldown": 5,
        }
        assert plan.total_collection_seconds == steady_seconds + 15
        assert plan.total_sample_count == steady_seconds + 15
