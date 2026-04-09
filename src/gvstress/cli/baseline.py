# pyright: reportMissingImports=false, reportMissingTypeStubs=false, reportAttributeAccessIssue=false

from __future__ import annotations

import getpass
import json
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Annotated, Any

import typer

from gvstress.baseline.pktgen_runner import PktgenRunner, write_jsonl
from gvstress.config import load_config
from gvstress.config.models import Config as RunConfig
from gvstress.config.models import FakeCameraConfig, ScenarioConfig
from gvstress.core.models import (
    PrimaryAttribution,
    RunValidity,
    ScenarioType,
    SecondaryAttribution,
    Verdict,
)
from gvstress.core.orchestrator import RunArtifactsLayout
from gvstress.core.preflight import (
    PreflightCheck,
    PreflightResult,
    missing_binary_reason,
)
from gvstress.core.runner import LocalRunner, SSHRunner
from gvstress.dut.environment import (
    EnvironmentSnapshot,
    collect_local_environment_snapshot,
)
from gvstress.dut.nic_probe import NICProbe
from gvstress.dut.system_probe import SystemProbe
from gvstress.report.models import (
    CompatibleBaselineReference,
    CPUContextSummary,
    IRQContextSummary,
    PktgenBaselineSummary,
    PktgenInterfaceSummary,
    PreflightSummary,
    RunArtifact,
    SamplesSummary,
    SummaryReport,
    VerdictSummary,
)
from gvstress.report.renderer import render_summary_to_markdown
from gvstress.report.writer import JSONWriter

app = typer.Typer(help="Run baseline benchmarks", no_args_is_help=True)


@app.command("pktgen")
def pktgen_command(
    config: Annotated[
        Path, typer.Option("--config", "-c", help="Path to configuration file.")
    ],
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Output directory.")
    ] = None,
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit JSON output.")
    ] = False,
) -> None:
    try:
        run_config = load_config(config)
        output_root = output or run_config.output.root
        payload = run_pktgen_baseline(run_config, output_root=output_root)
    except FileNotFoundError as exc:
        if exc.filename == str(config):
            typer.echo(f"Error: Config file not found: {config}", err=True)
            raise typer.Exit(code=1) from None
        payload = _emit_missing_binary_result(
            scenario="pktgen_baseline",
            output_root=output_root
            if "output_root" in dir()
            else (output or Path.cwd()),
            binary=_missing_binary_name(exc),
            json_output=json_output,
        )
        typer.echo(_format_baseline_error(payload, as_json=json_output))
        raise typer.Exit(code=1) from None
    except RuntimeError as exc:
        payload = _emit_runtime_error_result(
            scenario="pktgen_baseline",
            output_root=output_root
            if "output_root" in dir()
            else (output or Path.cwd()),
            reason=str(exc),
            json_output=json_output,
        )
        typer.echo(_format_baseline_error(payload, as_json=json_output))
        raise typer.Exit(code=1) from None

    if json_output:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
    else:
        typer.echo(f"run_id={payload['run_id']}")
        typer.echo(f"artifacts={payload['artifacts_root']}")
        typer.echo(f"baseline_only={payload['baseline_only']}")

    raise typer.Exit(code=0)


def run_pktgen_baseline(
    config: RunConfig,
    *,
    output_root: Path,
    proc_root: str | Path = "/proc/net/pktgen",
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    run_id_factory: Callable[[], str] | None = None,
    pktgen_runner: PktgenRunner | None = None,
    nic_probe: Any | None = None,
    system_probe: Any | None = None,
) -> dict[str, Any]:
    run_id = (run_id_factory or (lambda: uuid.uuid4().hex))()
    artifacts = RunArtifactsLayout.create(output_root / run_id)
    environment = collect_local_environment_snapshot(config.pktgen.interfaces)
    known_interfaces = {interface.name for interface in environment.interfaces}
    missing = [
        name for name in config.pktgen.interfaces if name not in known_interfaces
    ]
    if missing:
        raise RuntimeError(f"missing pktgen interfaces: {', '.join(missing)}")

    preflight = _build_baseline_preflight(environment).write(
        artifacts.evidence_dir / "preflight"
    )
    runner = pktgen_runner or PktgenRunner(config.pktgen, proc_root=proc_root)
    resolved_nic_probe = nic_probe or _build_nic_probe(config)
    resolved_system_probe = system_probe or _build_system_probe(config)
    assignments, script_paths = runner.materialize_control_scripts(
        artifacts.evidence_dir / "pktgen"
    )
    runner.prepare()

    event_records: list[dict[str, Any]] = [
        {
            "record_type": "state_transition",
            "run_id": run_id,
            "to_state": "pktgen_prepare",
        }
    ]
    nic_records: list[dict[str, Any]] = []
    system_records: list[dict[str, Any]] = []

    started_at = clock()
    deadline = started_at + config.pktgen.duration
    sample_interval = config.dut.sample_interval_ms / 1000.0
    runner.start()
    event_records.append(
        {
            "record_type": "state_transition",
            "run_id": run_id,
            "to_state": "steady_state",
        }
    )
    try:
        next_sample_at = started_at
        sample_index = 0
        while True:
            now = clock()
            if now >= next_sample_at:
                if resolved_nic_probe is not None and config.dut.collect.nic:
                    nic_records.append(
                        {
                            "run_id": run_id,
                            "phase": "steady_state",
                            "sample_index": sample_index,
                            "payload": _serialize_value(resolved_nic_probe.collect()),
                        }
                    )
                if resolved_system_probe is not None and config.dut.collect.system:
                    system_records.append(
                        {
                            "run_id": run_id,
                            "phase": "steady_state",
                            "sample_index": sample_index,
                            "payload": _serialize_value(
                                resolved_system_probe.collect()
                            ),
                        }
                    )
                next_sample_at += sample_interval
                sample_index += 1
            if now >= deadline:
                break
            wait_seconds = min(max(0.0, next_sample_at - now), max(0.0, deadline - now))
            if wait_seconds > 0:
                sleep(wait_seconds)
    finally:
        runner.stop()

    event_records.extend(
        [
            {
                "record_type": "state_transition",
                "run_id": run_id,
                "to_state": "teardown",
            },
            {
                "record_type": "state_transition",
                "run_id": run_id,
                "to_state": "reporting",
            },
        ]
    )

    parsed_results = runner.collect_results(assignments)
    write_jsonl(artifacts.nic_path, nic_records)
    write_jsonl(artifacts.system_path, system_records)
    write_jsonl(artifacts.events_path, event_records)

    baseline_summary = _build_pktgen_baseline_summary(
        parsed_results=parsed_results,
        nic_records=nic_records,
        system_records=system_records,
        script_paths=script_paths,
    )
    artifact = RunArtifact(
        run_id=run_id,
        run_validity=RunValidity.VALID,
        scenario=ScenarioConfig(
            name=ScenarioType.PKTGEN_BASELINE,
            duration=300,
            warmup=10,
            cooldown=5,
        ),
        fake_camera_config=_placeholder_camera_config(),
        dut_config=config.dut,
        stream_config=config.stream,
        preflight=preflight,
        samples={
            "nic": artifacts.nic_path,
            "system": artifacts.system_path,
            "events": artifacts.events_path,
        },
        verdict=Verdict.NOT_APPLICABLE,
        primary_attribution=PrimaryAttribution.UNKNOWN,
        secondary_attribution=SecondaryAttribution.PKTGEN_BASELINE,
        recommended_actions=[],
        baseline_only=True,
        pktgen_baseline=baseline_summary,
        compatible_baseline=None,
        run_config=config,
        notes="Pktgen baseline only. This report does not claim GigE Vision equivalence.",
    )
    JSONWriter().write(artifact, artifacts.run_json_path)

    checks_passed = sum(1 for check in preflight.checks if check.passed)
    summary = SummaryReport(
        run_id=run_id,
        timestamp=artifact.timestamp,
        scenario_name=ScenarioType.PKTGEN_BASELINE,
        scenario_duration=config.pktgen.duration,
        preflight=PreflightSummary(
            run_validity=preflight.run_validity,
            checks_passed=checks_passed,
            checks_failed=len(preflight.checks) - checks_passed,
            generator_environment_path=str(preflight.generator_environment_path)
            if preflight.generator_environment_path is not None
            else None,
            dut_environment_path=str(preflight.dut_environment_path)
            if preflight.dut_environment_path is not None
            else None,
            preflight_path=str(preflight.preflight_path)
            if preflight.preflight_path is not None
            else None,
            reasons=list(preflight.reasons),
        ),
        samples=SamplesSummary(
            nic_samples=len(nic_records),
            stream_samples=0,
            system_samples=len(system_records),
            events_samples=len(event_records),
            nic_path=str(artifacts.nic_path),
            system_path=str(artifacts.system_path),
            events_path=str(artifacts.events_path),
        ),
        verdict=VerdictSummary(
            verdict=Verdict.NOT_APPLICABLE,
            primary_attribution=PrimaryAttribution.UNKNOWN,
            secondary_attribution=SecondaryAttribution.PKTGEN_BASELINE,
            affected_ports=list(config.dut.ifaces),
            likely_fault_domain="Pktgen baseline context",
        ),
        recommended_actions=[],
        baseline_only=True,
        pktgen_baseline=baseline_summary,
        compatible_baseline=None,
        notes=artifact.notes,
    )
    render_summary_to_markdown(summary, artifacts.summary_md_path)

    return {
        "run_id": run_id,
        "artifacts_root": str(artifacts.root),
        "baseline_only": True,
        "control_scripts": [str(path) for path in script_paths.values()],
        "results": [result.to_dict() for result in parsed_results],
    }


def find_latest_compatible_baseline(
    search_root: Path,
    *,
    interface_names: list[str],
    exclude_run_id: str | None = None,
) -> CompatibleBaselineReference | None:
    candidates: list[tuple[str, dict[str, Any]]] = []
    for report_path in search_root.rglob("run.json"):
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        if not payload.get("baseline_only"):
            continue
        if exclude_run_id is not None and payload.get("run_id") == exclude_run_id:
            continue
        baseline = payload.get("pktgen_baseline") or {}
        baseline_interfaces = sorted(
            interface.get("interface")
            for interface in baseline.get("interfaces", [])
            if interface.get("interface")
        )
        if baseline_interfaces != sorted(interface_names):
            continue
        candidates.append((str(payload.get("timestamp", "")), payload))

    if not candidates:
        return None
    payload = sorted(candidates, key=lambda item: item[0], reverse=True)[0][1]
    baseline = payload["pktgen_baseline"]
    return CompatibleBaselineReference(
        run_id=str(payload["run_id"]),
        interface_names=sorted(interface_names),
        packet_size=next(
            (
                interface.get("packet_size")
                for interface in baseline.get("interfaces", [])
                if interface.get("packet_size") is not None
            ),
            None,
        ),
        duration_seconds=payload.get("scenario", {}).get("duration"),
        per_interface_mbps={
            interface["interface"]: int(interface.get("mbps", 0))
            for interface in baseline.get("interfaces", [])
            if interface.get("interface")
        },
    )


def attach_compatible_baseline_to_report(
    artifacts_root: Path,
    *,
    search_root: Path,
    interface_names: list[str],
    exclude_run_id: str | None = None,
) -> CompatibleBaselineReference | None:
    baseline_ref = find_latest_compatible_baseline(
        search_root,
        interface_names=interface_names,
        exclude_run_id=exclude_run_id,
    )
    if baseline_ref is None:
        return None

    run_json_path = artifacts_root / "reports" / "run.json"
    summary_path = artifacts_root / "reports" / "summary.md"
    payload = json.loads(run_json_path.read_text(encoding="utf-8"))
    payload["compatible_baseline"] = baseline_ref.model_dump(mode="json")
    run_artifact = RunArtifact.model_validate(payload)
    JSONWriter().write(run_artifact, run_json_path)

    summary_report = SummaryReport(
        run_id=run_artifact.run_id,
        timestamp=run_artifact.timestamp,
        scenario_name=run_artifact.scenario.name,
        scenario_duration=run_artifact.scenario.duration,
        preflight=PreflightSummary(
            run_validity=run_artifact.run_validity,
            checks_passed=_preflight_checks(run_artifact.preflight)[0],
            checks_failed=_preflight_checks(run_artifact.preflight)[1],
            generator_environment_path=_preflight_path(
                run_artifact.preflight, "generator_environment_path"
            ),
            dut_environment_path=_preflight_path(
                run_artifact.preflight, "dut_environment_path"
            ),
            preflight_path=_preflight_path(run_artifact.preflight, "preflight_path"),
            reasons=_preflight_reasons(run_artifact.preflight),
        ),
        samples=SamplesSummary(
            nic_samples=_count_jsonl_lines(run_artifact.samples.get("nic")),
            stream_samples=_count_jsonl_lines(run_artifact.samples.get("stream")),
            system_samples=_count_jsonl_lines(run_artifact.samples.get("system")),
            events_samples=_count_jsonl_lines(run_artifact.samples.get("events")),
            nic_path=str(run_artifact.samples.get("nic"))
            if run_artifact.samples.get("nic") is not None
            else None,
            stream_path=str(run_artifact.samples.get("stream"))
            if run_artifact.samples.get("stream") is not None
            else None,
            system_path=str(run_artifact.samples.get("system"))
            if run_artifact.samples.get("system") is not None
            else None,
            events_path=str(run_artifact.samples.get("events"))
            if run_artifact.samples.get("events") is not None
            else None,
        ),
        verdict=VerdictSummary(
            verdict=run_artifact.verdict,
            primary_attribution=run_artifact.primary_attribution,
            secondary_attribution=run_artifact.secondary_attribution,
            affected_ports=list(run_artifact.dut_config.ifaces),
            likely_fault_domain="Scenario orchestration",
        ),
        recommended_actions=list(run_artifact.recommended_actions),
        compatible_baseline=baseline_ref,
        notes=run_artifact.notes,
    )
    render_summary_to_markdown(summary_report, summary_path)
    return baseline_ref


def _missing_binary_name(exc: FileNotFoundError) -> str:
    """Extract missing binary name from FileNotFoundError."""
    if exc.filename:
        return Path(exc.filename).name
    return "unknown"


def _emit_missing_binary_result(
    scenario: str,
    *,
    output_root: Path,
    binary: str,
    json_output: bool,
) -> dict[str, object]:
    """Build structured missing-binary error payload for baseline CLI."""
    reason = missing_binary_reason(binary)
    return {
        "run_id": None,
        "scenario": scenario,
        "run_validity": "invalid_prereq",
        "aborted": True,
        "abort_reason": reason,
        "sample_counts": {"nic": 0, "system": 0, "stream": 0, "events": 0},
        "artifacts_root": str(output_root),
        "transitions": [],
        "baseline_only": True,
        "pktgen_baseline_summary": None,
    }


def _emit_runtime_error_result(
    scenario: str,
    *,
    output_root: Path,
    reason: str,
    json_output: bool,
) -> dict[str, object]:
    """Build structured runtime error payload for baseline CLI."""
    return {
        "run_id": None,
        "scenario": scenario,
        "run_validity": "invalid_prereq",
        "aborted": True,
        "abort_reason": f"runtime_error:{reason}",
        "sample_counts": {"nic": 0, "system": 0, "stream": 0, "events": 0},
        "artifacts_root": str(output_root),
        "transitions": [],
        "baseline_only": True,
        "pktgen_baseline_summary": None,
    }


def _format_baseline_error(payload: dict[str, object], *, as_json: bool) -> str:
    """Format baseline error payload for output."""
    if as_json:
        return json.dumps(payload, indent=2, sort_keys=True)
    return (
        f"run_validity={payload['run_validity']}\n"
        f"scenario={payload['scenario']}\n"
        f"abort_reason={payload['abort_reason']}"
    )


def _build_baseline_preflight(environment: EnvironmentSnapshot) -> PreflightResult:
    checks = [
        PreflightCheck(name="pktgen", passed=environment.pktgen_available, reasons=[]),
        PreflightCheck(name="interfaces", passed=True, reasons=[]),
        PreflightCheck(
            name="privileges", passed=environment.sudo_available, reasons=[]
        ),
    ]
    reasons: list[str] = []
    if not environment.pktgen_available:
        checks[0].reasons.append("generator.missing_binary:pktgen")
        reasons.append("generator.missing_binary:pktgen")
    if not environment.sudo_available:
        checks[2].reasons.append("generator.sudo_unavailable")
        reasons.append("generator.sudo_unavailable")
    result = PreflightResult(
        run_validity=RunValidity.VALID if not reasons else RunValidity.INVALID_PREREQ,
        reasons=reasons,
        checks=checks,
        generator_environment=environment,
        dut_environment=environment,
    )
    return result


def _build_runner(config: RunConfig) -> SSHRunner | LocalRunner:
    """Build SSH runner if DUT host is configured, otherwise use local runner."""
    if config.dut.host:
        user = config.dut.user or getpass.getuser()
        return SSHRunner(
            host=config.dut.host,
            user=user,
            port=config.dut.port,
        )
    return LocalRunner()


def _build_nic_probe(config: RunConfig) -> NICProbe | None:
    if not config.dut.collect.nic:
        return None
    return NICProbe(_build_runner(config), config.dut.ifaces)


def _build_system_probe(config: RunConfig) -> SystemProbe | None:
    if not config.dut.collect.system:
        return None
    return SystemProbe(_build_runner(config), config.dut.ifaces)


def _build_pktgen_baseline_summary(
    *,
    parsed_results: list[Any],
    nic_records: list[dict[str, Any]],
    system_records: list[dict[str, Any]],
    script_paths: dict[str, Path],
) -> PktgenBaselineSummary:
    latest_system = system_records[-1]["payload"] if system_records else {}
    interfaces = [
        PktgenInterfaceSummary(
            interface=result.interface,
            device_name=result.device_name,
            thread_name=result.thread_name,
            packets=result.packets,
            packet_size=result.packet_size,
            errors=result.errors,
            duration_usec=result.duration_usec,
            pps=result.pps,
            mbps=result.mbps,
            bps=result.bps,
            rate=result.rate,
            ratep=result.ratep,
            xmit_mode=result.xmit_mode,
            result=result.result,
            source_path=result.source_path,
        )
        for result in parsed_results
    ]
    irq_context = [
        IRQContextSummary(
            interface=name,
            dominant_cpu=payload.get("dominant_cpu"),
            irq_descriptions=[
                irq.get("description", "") for irq in payload.get("irqs", [])
            ],
            total_counts=payload.get("total_counts", {}),
            delta_counts=payload.get("delta_counts") or {},
        )
        for name, payload in sorted(latest_system.get("interfaces", {}).items())
    ]
    cpu_context = [
        CPUContextSummary(cpu=name, usage_pct=payload.get("usage_pct"))
        for name, payload in sorted(latest_system.get("cpus", {}).items())
        if name != "cpu"
    ]
    return PktgenBaselineSummary(
        interfaces=interfaces,
        control_script_paths=[str(path) for path in script_paths.values()],
        nic_sample_count=len(nic_records),
        system_sample_count=len(system_records),
        irq_context=irq_context,
        cpu_context=cpu_context,
    )


def _placeholder_camera_config() -> FakeCameraConfig:
    return FakeCameraConfig(
        ip_address="0.0.0.0",
        interface_name="pktgen",
        serial_number="pktgen-baseline",
        genicam_filename="pktgen-baseline.xml",
        gvsp_lost_ratio=0.0,
    )


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


def _preflight_checks(preflight: Any) -> tuple[int, int]:
    if not isinstance(preflight, dict):
        return 0, 0
    checks = preflight.get("checks", [])
    if not isinstance(checks, list):
        return 0, 0
    passed = sum(
        1 for check in checks if isinstance(check, dict) and check.get("passed")
    )
    return passed, len(checks) - passed


def _preflight_reasons(preflight: Any) -> list[str]:
    if not isinstance(preflight, dict):
        return []
    reasons = preflight.get("reasons", [])
    return [str(reason) for reason in reasons] if isinstance(reasons, list) else []


def _preflight_path(preflight: Any, key: str) -> str | None:
    if not isinstance(preflight, dict):
        return None
    value = preflight.get(key)
    return str(value) if value is not None else None


def _count_jsonl_lines(path: Path | None) -> int:
    if path is None or not path.exists():
        return 0
    content = path.read_text(encoding="utf-8")
    return len(content.splitlines()) if content else 0
