# pyright: reportMissingImports=false, reportMissingTypeStubs=false, reportPrivateUsage=false, reportArgumentType=false, reportUnusedCallResult=false

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated

import typer

from gvstress.cli.baseline import (
    _build_nic_probe,
    _build_runner,
    _build_system_probe,
    attach_compatible_baseline_to_report,
)
from gvstress.config import load_config
from gvstress.config.models import Config as RunConfig
from gvstress.core.models import RunValidity, ScenarioType, Verdict
from gvstress.core.orchestrator import RunOrchestrator
from gvstress.core.preflight import missing_binary_reason, run_preflight
from gvstress.dut.environment import collect_local_environment_snapshot
from gvstress.dut.stream_probe import StreamProbe, StreamTarget
from gvstress.fakecam.manager import FakeCameraManager

app = typer.Typer(help="Run stress test scenarios", no_args_is_help=True)


def _exit_code_for_verdict(verdict: Verdict) -> int:
    return {
        Verdict.PASS: 0,
        Verdict.WARN: 2,
        Verdict.FAIL: 3,
        Verdict.NOT_APPLICABLE: 4,
    }.get(verdict, 1)


def _run_scenario(
    config: RunConfig,
    scenario_name: str,
    output_dir: Path | None = None,
    json_output: bool = False,
) -> None:
    try:
        scenario_type = ScenarioType(scenario_name)
    except ValueError:
        typer.echo(f"Error: Unknown scenario '{scenario_name}'", err=True)
        typer.echo(
            f"Available scenarios: {', '.join(s.value for s in ScenarioType)}", err=True
        )
        raise typer.Exit(code=1) from None

    output_root = output_dir or config.output.root
    try:
        generator_ifaces = [
            interface.name
            for interface in collect_local_environment_snapshot().interfaces
        ]
        dut_ifaces = config.dut.ifaces

        runner = _build_runner(config)
        preflight_result = run_preflight(
            dut_host=config.dut.host,
            dut_ifaces=dut_ifaces,
            generator_ifaces=generator_ifaces,
            ssh_runner=runner,
            out_dir=output_root / "preflight",
        )
    except FileNotFoundError as exc:
        _emit_missing_binary_result(
            scenario_name,
            output_root=output_root,
            binary=_missing_binary_name(exc),
            json_output=json_output,
        )
        raise typer.Exit(code=1) from None

    fakecam_manager = None
    if config.generator.cameras:
        fakecam_manager = FakeCameraManager.from_generator_config(
            config.generator,
            runtime_dir=output_root / "fakecam",
            python_bin=sys.executable,
        )

    nic_probe = _build_nic_probe(config)
    system_probe = _build_system_probe(config)
    stream_probe = (
        StreamProbe(
            [
                StreamTarget.from_camera_config(camera)
                for camera in config.generator.cameras
            ],
            config.stream,
            sample_interval_s=config.dut.sample_interval_ms / 1000.0,
        )
        if config.dut.collect.stream and config.generator.cameras
        else None
    )

    orchestrator = RunOrchestrator(
        scenario_type=scenario_type,
        output_root=output_root / "runs",
        preflight_runner=lambda: preflight_result,
        fakecam_manager=fakecam_manager,
        nic_probe=nic_probe,
        system_probe=system_probe,
        stream_probe=stream_probe,
        fake_camera_config=config.generator.cameras[0]
        if config.generator.cameras
        else None,
        dut_config=config.dut,
        stream_config=config.stream,
    )

    result = orchestrator.run()
    attach_compatible_baseline_to_report(
        result.artifacts.root,
        search_root=output_root.parent,
        interface_names=list(config.dut.ifaces),
        exclude_run_id=result.run_id,
    )

    if json_output:
        output = {
            "run_id": result.run_id,
            "scenario": scenario_name,
            "run_validity": result.run_validity.value,
            "aborted": result.aborted,
            "abort_reason": result.abort_reason,
            "sample_counts": result.sample_counts,
            "artifacts_root": str(result.artifacts.root),
            "transitions": result.transitions,
        }
        typer.echo(json.dumps(output, indent=2, sort_keys=True))
    else:
        typer.echo(f"run_id={result.run_id}")
        typer.echo(f"scenario={scenario_name}")
        typer.echo(f"run_validity={result.run_validity.value}")
        typer.echo(f"aborted={result.aborted}")
        if result.abort_reason:
            typer.echo(f"abort_reason={result.abort_reason}")
        typer.echo(f"sample_counts={result.sample_counts}")
        typer.echo(f"artifacts={result.artifacts.root}")

    exit_code = _exit_code_for_verdict(
        result.verdict.verdict
        if result.verdict
        else (
            Verdict.NOT_APPLICABLE
            if result.run_validity is not RunValidity.VALID
            else Verdict.PASS
        )
    )
    raise typer.Exit(code=exit_code)


def _emit_missing_binary_result(
    scenario_name: str,
    *,
    output_root: Path,
    binary: str,
    json_output: bool,
) -> None:
    reason = missing_binary_reason(binary)
    payload: dict[str, object] = {
        "run_id": None,
        "scenario": scenario_name,
        "run_validity": RunValidity.INVALID_PREREQ.value,
        "aborted": True,
        "abort_reason": reason,
        "sample_counts": {"nic": 0, "system": 0, "stream": 0},
        "artifacts_root": str(output_root / "runs"),
        "transitions": [],
    }
    if json_output:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
        return

    typer.echo(f"scenario={scenario_name}")
    typer.echo(f"run_validity={payload['run_validity']}")
    typer.echo("aborted=True")
    typer.echo(f"abort_reason={reason}")


def _missing_binary_name(exc: FileNotFoundError) -> str:
    filename: object | None = exc.filename or (exc.args[0] if exc.args else None)
    return str(filename) if filename else "unknown"


@app.command("smoke")
def smoke_command(
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
    run_config = load_config(config)
    _run_scenario(run_config, "smoke", output, json_output)


@app.command("four-stream")
def four_stream_command(
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
    run_config = load_config(config)
    _run_scenario(run_config, "four_stream", output, json_output)


@app.command("soak")
def soak_command(
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
    run_config = load_config(config)
    _run_scenario(run_config, "soak", output, json_output)


@app.command("loss-injection")
def loss_injection_command(
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
    run_config = load_config(config)
    _run_scenario(run_config, "loss_injection", output, json_output)
