# pyright: reportMissingImports=false, reportMissingTypeStubs=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportExplicitAny=false, reportAny=false, reportUnannotatedClassAttribute=false, reportUnusedCallResult=false, reportAttributeAccessIssue=false

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from gvstress.config.models import (
    DUTCollectOptions,
    DUTConfig,
    FakeCameraConfig,
    ScenarioConfig,
    StreamConfig,
)
from gvstress.core.models import RunValidity, ScenarioType
from gvstress.core.preflight import PreflightResult
from gvstress.core.scenario_engine import ScenarioEngine, ScenarioPlan
from gvstress.core.verdict import (
    VerdictContext,
    VerdictDecision,
    VerdictEngine,
    likely_fault_domain_for,
)
from gvstress.dut.nic_probe import NICSample
from gvstress.dut.stream_probe import StreamSample
from gvstress.dut.system_probe import SystemSample
from gvstress.report.models import (
    PreflightSummary,
    RunArtifact,
    SamplesSummary,
    SummaryReport,
    VerdictSummary,
)
from gvstress.report.renderer import render_summary_to_markdown
from gvstress.report.writer import JSONWriter


@dataclass(slots=True)
class RunArtifactsLayout:
    root: Path
    raw_dir: Path
    reports_dir: Path
    logs_dir: Path
    evidence_dir: Path
    nic_path: Path
    system_path: Path
    stream_path: Path
    events_path: Path
    run_json_path: Path
    summary_md_path: Path

    @classmethod
    def create(cls, root: str | Path) -> RunArtifactsLayout:
        root_path = Path(root)
        raw_dir = root_path / "raw"
        reports_dir = root_path / "reports"
        logs_dir = root_path / "logs"
        evidence_dir = root_path / "evidence"
        for directory in (root_path, raw_dir, reports_dir, logs_dir, evidence_dir):
            directory.mkdir(parents=True, exist_ok=True)
        return cls(
            root=root_path,
            raw_dir=raw_dir,
            reports_dir=reports_dir,
            logs_dir=logs_dir,
            evidence_dir=evidence_dir,
            nic_path=raw_dir / "nic_samples.jsonl",
            system_path=raw_dir / "system_samples.jsonl",
            stream_path=raw_dir / "stream_samples.jsonl",
            events_path=raw_dir / "events_samples.jsonl",
            run_json_path=reports_dir / "run.json",
            summary_md_path=reports_dir / "summary.md",
        )


@dataclass(slots=True)
class RunResult:
    run_id: str
    scenario_plan: ScenarioPlan
    run_validity: RunValidity
    aborted: bool
    abort_reason: str | None
    sample_counts: dict[str, int]
    artifacts: RunArtifactsLayout
    preflight: PreflightResult
    transitions: list[str]
    verdict: VerdictDecision | None = None


class _JsonlWriter:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._count = 0
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def count(self) -> int:
        return self._count

    def write(self, payload: dict[str, Any]) -> None:
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(_serialize_value(payload), sort_keys=True) + "\n")
        self._count += 1


class RunOrchestrator:
    def __init__(
        self,
        *,
        scenario_type: ScenarioType,
        output_root: str | Path,
        preflight_runner: Any,
        scenario_engine: ScenarioEngine | None = None,
        fakecam_manager: Any | None = None,
        pktgen_preparer: Any | None = None,
        dut_prepare: Any | None = None,
        nic_probe: Any | None = None,
        system_probe: Any | None = None,
        stream_probe: Any | None = None,
        run_validity_evaluator: Any | None = None,
        verdict_engine: VerdictEngine | None = None,
        fake_camera_config: FakeCameraConfig | None = None,
        dut_config: DUTConfig | None = None,
        stream_config: StreamConfig | None = None,
        clock: Any = time.monotonic,
        sleep: Any = time.sleep,
        run_id_factory: Any | None = None,
    ) -> None:
        self._scenario_type = scenario_type
        self._output_root = Path(output_root)
        self._preflight_runner = preflight_runner
        self._scenario_engine = scenario_engine or ScenarioEngine()
        self._fakecam_manager = fakecam_manager
        self._pktgen_preparer = pktgen_preparer
        self._dut_prepare = dut_prepare
        self._nic_probe = nic_probe
        self._system_probe = system_probe
        self._stream_probe = stream_probe
        self._run_validity_evaluator = run_validity_evaluator
        self._verdict_engine = verdict_engine or VerdictEngine()
        self._fake_camera_config = fake_camera_config
        self._dut_config = dut_config
        self._stream_config = stream_config
        self._clock = clock
        self._sleep = sleep
        self._run_id_factory = run_id_factory or (lambda: uuid.uuid4().hex)
        self._last_event_timestamp: float | None = None

    def run(self) -> RunResult:
        plan = self._scenario_engine.build_plan(self._scenario_type)
        run_id = str(self._run_id_factory())
        artifacts = RunArtifactsLayout.create(self._output_root / run_id)
        writers = {
            "nic": _JsonlWriter(artifacts.nic_path),
            "system": _JsonlWriter(artifacts.system_path),
            "stream": _JsonlWriter(artifacts.stream_path),
            "events": _JsonlWriter(artifacts.events_path),
        }

        current_state: str | None = None
        transitions: list[str] = []
        run_validity = RunValidity.VALID
        aborted = False
        abort_reason: str | None = None
        consecutive_missing_camera_intervals = 0
        expected_camera_count: int | None = None
        fake_cameras_survived = True
        warmup_stream_samples: list[StreamSample] = []
        steady_state_stream_samples: list[StreamSample] = []
        steady_state_nic_samples: list[NICSample] = []
        steady_state_system_samples: list[SystemSample] = []

        self._record_transition(
            writers["events"],
            run_id=run_id,
            scenario_type=self._scenario_type,
            from_state=None,
            to_state="preflight",
        )
        transitions.append("preflight")
        current_state = "preflight"

        preflight = self._invoke_action(self._preflight_runner)
        if not isinstance(preflight, PreflightResult):
            raise TypeError("preflight_runner must return PreflightResult")
        if preflight.run_validity is not RunValidity.VALID:
            run_validity = preflight.run_validity
            aborted = True
            abort_reason = f"preflight:{preflight.run_validity.value}"
            self._record_event(
                writers["events"],
                run_id=run_id,
                event_type="abort_condition",
                payload={"reason": abort_reason, "state": current_state},
            )
        else:
            current_state = self._transition_and_execute(
                writers["events"],
                run_id=run_id,
                scenario_type=self._scenario_type,
                from_state=current_state,
                to_state=plan.startup_phase,
                action=(
                    self._fakecam_manager.up
                    if plan.startup_phase == "fakecam_up"
                    and self._fakecam_manager is not None
                    else getattr(
                        self._pktgen_preparer, "prepare", self._pktgen_preparer
                    )
                ),
                transitions=transitions,
            )

            current_state = self._transition_and_execute(
                writers["events"],
                run_id=run_id,
                scenario_type=self._scenario_type,
                from_state=current_state,
                to_state="dut_prepare",
                action=getattr(self._dut_prepare, "prepare", self._dut_prepare),
                transitions=transitions,
            )

            for phase in plan.timed_phases:
                current_state = self._transition_and_execute(
                    writers["events"],
                    run_id=run_id,
                    scenario_type=self._scenario_type,
                    from_state=current_state,
                    to_state=phase.name,
                    action=None,
                    transitions=transitions,
                )
                for sample_index in range(phase.sample_count):
                    sample_started_at = self._clock()
                    nic_sample = self._collect_probe_sample(self._nic_probe)
                    system_sample = self._collect_probe_sample(self._system_probe)
                    stream_records = self._collect_stream_records()

                    if nic_sample is not None:
                        writers["nic"].write(
                            {
                                "run_id": run_id,
                                "phase": phase.name,
                                "sample_index": sample_index,
                                "payload": nic_sample,
                            }
                        )
                    if system_sample is not None:
                        writers["system"].write(
                            {
                                "run_id": run_id,
                                "phase": phase.name,
                                "sample_index": sample_index,
                                "payload": system_sample,
                            }
                        )
                    for stream_record in stream_records:
                        writers["stream"].write(
                            {
                                "run_id": run_id,
                                "phase": phase.name,
                                "sample_index": sample_index,
                                "payload": stream_record,
                            }
                        )

                    if phase.name == "warmup":
                        warmup_stream_samples.extend(
                            sample
                            for sample in stream_records
                            if isinstance(sample, StreamSample)
                        )
                    if phase.name == "steady_state":
                        if isinstance(nic_sample, NICSample):
                            steady_state_nic_samples.append(nic_sample)
                        if isinstance(system_sample, SystemSample):
                            steady_state_system_samples.append(system_sample)
                        steady_state_stream_samples.extend(
                            sample
                            for sample in stream_records
                            if isinstance(sample, StreamSample)
                        )

                    camera_status = None
                    if (
                        self._fakecam_manager is not None
                        and plan.startup_phase == "fakecam_up"
                    ):
                        camera_status = self._fakecam_manager.status()
                        running_count = int(camera_status.get("running_count", 0))
                        reported_camera_count = int(
                            camera_status.get("camera_count", running_count)
                        )
                        if expected_camera_count is None and reported_camera_count > 0:
                            expected_camera_count = reported_camera_count
                        if running_count == 0 or (
                            expected_camera_count is not None
                            and running_count < expected_camera_count
                        ):
                            fake_cameras_survived = False
                        if running_count == 0:
                            consecutive_missing_camera_intervals += 1
                        else:
                            consecutive_missing_camera_intervals = 0

                    evaluated_validity = self._evaluate_run_validity(
                        run_id=run_id,
                        phase=phase.name,
                        sample_index=sample_index,
                        nic_sample=nic_sample,
                        system_sample=system_sample,
                        stream_records=stream_records,
                        camera_status=camera_status,
                    )
                    if evaluated_validity is not RunValidity.VALID:
                        run_validity = evaluated_validity
                        aborted = True
                        abort_reason = f"run_validity:{evaluated_validity.value}"
                    elif consecutive_missing_camera_intervals > 2:
                        run_validity = RunValidity.INTERRUPTED
                        aborted = True
                        abort_reason = "fakecam_disappeared"

                    if aborted:
                        self._record_event(
                            writers["events"],
                            run_id=run_id,
                            event_type="abort_condition",
                            payload={
                                "reason": abort_reason,
                                "phase": phase.name,
                                "sample_index": sample_index,
                            },
                        )
                        break

                    elapsed = self._clock() - sample_started_at
                    remaining = max(0.0, (plan.sample_interval_ms / 1000) - elapsed)
                    if remaining > 0:
                        self._sleep(remaining)
                if aborted:
                    break

        current_state = self._transition_and_execute(
            writers["events"],
            run_id=run_id,
            scenario_type=self._scenario_type,
            from_state=current_state,
            to_state="teardown",
            action=self._teardown_action(),
            transitions=transitions,
        )

        current_state = self._transition_and_execute(
            writers["events"],
            run_id=run_id,
            scenario_type=self._scenario_type,
            from_state=current_state,
            to_state="reporting",
            action=None,
            transitions=transitions,
        )

        verdict_decision = self._evaluate_verdict(
            plan=plan,
            run_validity=run_validity,
            fake_cameras_survived=fake_cameras_survived,
            warmup_stream_samples=warmup_stream_samples,
            steady_state_stream_samples=steady_state_stream_samples,
            steady_state_nic_samples=steady_state_nic_samples,
            steady_state_system_samples=steady_state_system_samples,
        )

        self._write_reports(
            run_id=run_id,
            plan=plan,
            preflight=preflight,
            run_validity=run_validity,
            verdict_decision=verdict_decision,
            writers=writers,
            artifacts=artifacts,
        )

        return RunResult(
            run_id=run_id,
            scenario_plan=plan,
            run_validity=run_validity,
            aborted=aborted,
            abort_reason=abort_reason,
            sample_counts={name: writer.count for name, writer in writers.items()},
            artifacts=artifacts,
            preflight=preflight,
            transitions=transitions,
            verdict=verdict_decision,
        )

    def _transition_and_execute(
        self,
        event_writer: _JsonlWriter,
        *,
        run_id: str,
        scenario_type: ScenarioType,
        from_state: str | None,
        to_state: str,
        action: Any,
        transitions: list[str],
    ) -> str:
        self._record_transition(
            event_writer,
            run_id=run_id,
            scenario_type=scenario_type,
            from_state=from_state,
            to_state=to_state,
        )
        transitions.append(to_state)
        self._invoke_action(action)
        return to_state

    def _collect_probe_sample(self, probe: Any | None) -> Any | None:
        if probe is None:
            return None
        return self._invoke_action(getattr(probe, "collect", probe))

    def _collect_stream_records(self) -> list[Any]:
        if self._stream_probe is None:
            return []
        collected = self._invoke_action(
            getattr(self._stream_probe, "collect", self._stream_probe)
        )
        if collected is None:
            return []
        if isinstance(collected, list):
            return collected
        if isinstance(collected, tuple):
            return list(collected)
        return [collected]

    def _evaluate_run_validity(self, **context: Any) -> RunValidity:
        if self._run_validity_evaluator is None:
            return RunValidity.VALID
        evaluated = self._run_validity_evaluator(context)
        if evaluated is None:
            return RunValidity.VALID
        if isinstance(evaluated, RunValidity):
            return evaluated
        return RunValidity(str(evaluated))

    def _evaluate_verdict(
        self,
        *,
        plan: ScenarioPlan,
        run_validity: RunValidity,
        fake_cameras_survived: bool,
        warmup_stream_samples: list[StreamSample],
        steady_state_stream_samples: list[StreamSample],
        steady_state_nic_samples: list[NICSample],
        steady_state_system_samples: list[SystemSample],
    ) -> VerdictDecision:
        expected_stream_keys = {
            self._stream_key(sample)
            for sample in [*warmup_stream_samples, *steady_state_stream_samples]
        }
        warmup_stream_keys = {
            self._stream_key(sample) for sample in warmup_stream_samples
        }
        return self._verdict_engine.evaluate(
            VerdictContext(
                scenario_type=plan.scenario_type,
                run_validity=run_validity,
                fake_cameras_survived=fake_cameras_survived,
                all_streams_established_within_warmup=(
                    not expected_stream_keys
                    or expected_stream_keys.issubset(warmup_stream_keys)
                ),
                expected_stream_count=len(expected_stream_keys),
                warmup_stream_samples=tuple(warmup_stream_samples),
                steady_state_stream_samples=tuple(steady_state_stream_samples),
                steady_state_nic_samples=tuple(steady_state_nic_samples),
                steady_state_system_samples=tuple(steady_state_system_samples),
                targeted_stream=self._targeted_stream(),
            )
        )

    def _targeted_stream(self) -> str | None:
        if self._scenario_type is not ScenarioType.LOSS_INJECTION:
            return None
        if self._fake_camera_config is None:
            return None
        if self._fake_camera_config.gvsp_lost_ratio <= 0:
            return None
        return self._stream_label(
            self._fake_camera_config.serial_number,
            self._fake_camera_config.ip_address,
        )

    @staticmethod
    def _stream_key(sample: StreamSample) -> str:
        return RunOrchestrator._stream_label(sample.serial_number, sample.ip_address)

    @staticmethod
    def _stream_label(serial_number: str, ip_address: str) -> str:
        return f"{serial_number}@{ip_address}"

    def _teardown_action(self) -> Any:
        def _run_teardown() -> None:
            if self._fakecam_manager is not None:
                self._fakecam_manager.down()
                archive_logs = getattr(self._fakecam_manager, "archive_logs", None)
                if archive_logs is not None:
                    archive_logs()

        return _run_teardown

    def _write_reports(
        self,
        *,
        run_id: str,
        plan: ScenarioPlan,
        preflight: PreflightResult,
        run_validity: RunValidity,
        verdict_decision: VerdictDecision,
        writers: dict[str, _JsonlWriter],
        artifacts: RunArtifactsLayout,
    ) -> None:
        fake_camera_config = self._fake_camera_config or FakeCameraConfig(
            ip_address="0.0.0.0",
            interface_name="unknown",
            serial_number="unknown",
            genicam_filename="unknown.xml",
            gvsp_lost_ratio=0.0,
        )
        dut_config = self._dut_config or DUTConfig(
            ifaces=[],
            sample_interval_ms=plan.sample_interval_ms,
            collect=DUTCollectOptions(
                nic=self._nic_probe is not None,
                stream=self._stream_probe is not None,
                system=self._system_probe is not None,
            ),
        )
        stream_config = self._stream_config or StreamConfig(
            packet_resend=False,
            socket_buffer=False,
            socket_buffer_size=0,
            frame_retention=0,
            initial_packet_timeout=0,
            packet_timeout=0,
            packet_request_ratio=0.0,
            receiver_priority=0,
            buffer_count=1,
        )

        artifact = RunArtifact(
            run_id=run_id,
            run_validity=run_validity,
            scenario=ScenarioConfig(
                name=plan.scenario_type,
                duration=plan.steady_state_seconds,
                warmup=plan.warmup_seconds,
                cooldown=plan.cooldown_seconds,
            ),
            fake_camera_config=fake_camera_config,
            dut_config=dut_config,
            stream_config=stream_config,
            preflight=preflight,
            samples={
                "nic": artifacts.nic_path,
                "stream": artifacts.stream_path,
                "system": artifacts.system_path,
                "events": artifacts.events_path,
            },
            verdict=verdict_decision.verdict,
            primary_attribution=verdict_decision.primary_attribution,
            secondary_attribution=verdict_decision.secondary_attribution,
            recommended_actions=list(verdict_decision.recommended_actions),
            baseline_only=False,
            pktgen_baseline=None,
            compatible_baseline=None,
            run_config=None,
            notes=None,
        )
        JSONWriter().write(artifact, artifacts.run_json_path)

        checks_passed = sum(1 for check in preflight.checks if check.passed)
        summary = SummaryReport(
            run_id=run_id,
            timestamp=artifact.timestamp,
            scenario_name=plan.scenario_type,
            scenario_duration=plan.steady_state_seconds,
            preflight=PreflightSummary(
                run_validity=run_validity,
                checks_passed=checks_passed,
                checks_failed=len(preflight.checks) - checks_passed,
                generator_environment_path=(
                    str(preflight.generator_environment_path)
                    if preflight.generator_environment_path is not None
                    else None
                ),
                dut_environment_path=(
                    str(preflight.dut_environment_path)
                    if preflight.dut_environment_path is not None
                    else None
                ),
                preflight_path=str(preflight.preflight_path)
                if preflight.preflight_path is not None
                else None,
                reasons=list(preflight.reasons),
            ),
            samples=SamplesSummary(
                nic_samples=writers["nic"].count,
                stream_samples=writers["stream"].count,
                system_samples=writers["system"].count,
                events_samples=writers["events"].count,
                nic_path=str(artifacts.nic_path),
                stream_path=str(artifacts.stream_path),
                system_path=str(artifacts.system_path),
                events_path=str(artifacts.events_path),
            ),
            verdict=VerdictSummary(
                verdict=artifact.verdict,
                primary_attribution=artifact.primary_attribution,
                secondary_attribution=artifact.secondary_attribution,
                affected_ports=list(dut_config.ifaces),
                likely_fault_domain=likely_fault_domain_for(
                    artifact.secondary_attribution
                ),
            ),
            recommended_actions=list(artifact.recommended_actions),
        )
        render_summary_to_markdown(summary, artifacts.summary_md_path)

    def _record_transition(
        self,
        writer: _JsonlWriter,
        *,
        run_id: str,
        scenario_type: ScenarioType,
        from_state: str | None,
        to_state: str,
    ) -> None:
        writer.write(
            {
                "record_type": "state_transition",
                "run_id": run_id,
                "timestamp": self._next_event_timestamp(),
                "scenario": scenario_type.value,
                "from_state": from_state,
                "to_state": to_state,
            }
        )

    def _record_event(
        self,
        writer: _JsonlWriter,
        *,
        run_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        writer.write(
            {
                "record_type": event_type,
                "run_id": run_id,
                "timestamp": self._next_event_timestamp(),
                **payload,
            }
        )

    def _next_event_timestamp(self) -> float:
        timestamp = float(self._clock())
        if self._last_event_timestamp is None or timestamp > self._last_event_timestamp:
            self._last_event_timestamp = timestamp
            return timestamp
        self._last_event_timestamp += 1e-6
        return self._last_event_timestamp

    @staticmethod
    def _invoke_action(action: Any) -> Any:
        if action is None:
            return None
        return action()


def _serialize_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value) and not isinstance(value, type):
        return {key: _serialize_value(item) for key, item in asdict(value).items()}
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): _serialize_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize_value(item) for item in value]
    return value
