# pyright: reportMissingImports=false

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated

import typer

from gvstress.config import load_config
from gvstress.core.preflight import missing_binary_reason

from ..fakecam.manager import FakeCameraManager

app = typer.Typer(help="Fake camera lifecycle commands", no_args_is_help=True)


@app.command("up")
def up_command(
    config: Annotated[
        Path, typer.Option("--config", "-c", help="Path to configuration file.")
    ],
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit JSON output.")
    ] = False,
    out: Annotated[
        Path | None,
        typer.Option("--out", help="Runtime directory for fake camera state."),
    ] = None,
) -> None:
    try:
        manager = _manager_from_config(config, out=out)
        payload = manager.up()
    except FileNotFoundError as exc:
        if exc.filename == str(config):
            typer.echo(f"Error: Config file not found: {config}", err=True)
            raise typer.Exit(code=1) from None
        payload = _emit_error_result(
            scenario="fakecam_up",
            output_root=_output_root_from_config(config, out),
            binary=_missing_binary_name(exc),
            json_output=json_output,
        )
        typer.echo(_format_error_payload(payload, as_json=json_output))
        raise typer.Exit(code=1) from None
    except RuntimeError as exc:
        payload = _emit_error_result(
            scenario="fakecam_up",
            output_root=_output_root_from_config(config, out),
            reason=str(exc),
            json_output=json_output,
        )
        typer.echo(_format_error_payload(payload, as_json=json_output))
        raise typer.Exit(code=1) from None

    _emit(payload, as_json=json_output)
    raise typer.Exit(code=_exit_code_for_payload(payload))


@app.command("status")
def status_command(
    config: Annotated[
        Path, typer.Option("--config", "-c", help="Path to configuration file.")
    ],
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit JSON output.")
    ] = False,
    out: Annotated[
        Path | None,
        typer.Option("--out", help="Runtime directory for fake camera state."),
    ] = None,
) -> None:
    try:
        payload = _manager_from_config(config, out=out).status()
    except FileNotFoundError as exc:
        if exc.filename == str(config):
            typer.echo(f"Error: Config file not found: {config}", err=True)
            raise typer.Exit(code=1) from None
        payload = _emit_error_result(
            scenario="fakecam_status",
            output_root=_output_root_from_config(config, out),
            binary=_missing_binary_name(exc),
            json_output=json_output,
        )
        typer.echo(_format_error_payload(payload, as_json=json_output))
        raise typer.Exit(code=1) from None
    except RuntimeError as exc:
        payload = _emit_error_result(
            scenario="fakecam_status",
            output_root=_output_root_from_config(config, out),
            reason=str(exc),
            json_output=json_output,
        )
        typer.echo(_format_error_payload(payload, as_json=json_output))
        raise typer.Exit(code=1) from None

    _emit(payload, as_json=json_output)
    raise typer.Exit(code=_exit_code_for_payload(payload))


@app.command("down")
def down_command(
    config: Annotated[
        Path, typer.Option("--config", "-c", help="Path to configuration file.")
    ],
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit JSON output.")
    ] = False,
    out: Annotated[
        Path | None,
        typer.Option("--out", help="Runtime directory for fake camera state."),
    ] = None,
) -> None:
    try:
        payload = _manager_from_config(config, out=out).down()
    except FileNotFoundError as exc:
        if exc.filename == str(config):
            typer.echo(f"Error: Config file not found: {config}", err=True)
            raise typer.Exit(code=1) from None
        payload = _emit_error_result(
            scenario="fakecam_down",
            output_root=_output_root_from_config(config, out),
            binary=_missing_binary_name(exc),
            json_output=json_output,
        )
        typer.echo(_format_error_payload(payload, as_json=json_output))
        raise typer.Exit(code=1) from None
    except RuntimeError as exc:
        payload = _emit_error_result(
            scenario="fakecam_down",
            output_root=_output_root_from_config(config, out),
            reason=str(exc),
            json_output=json_output,
        )
        typer.echo(_format_error_payload(payload, as_json=json_output))
        raise typer.Exit(code=1) from None

    _emit(payload, as_json=json_output)
    raise typer.Exit(code=_exit_code_for_payload(payload))


def _manager_from_config(config_path: Path, *, out: Path | None) -> FakeCameraManager:
    config = load_config(config_path)
    runtime_dir = out or config.output.root
    manager = FakeCameraManager.from_generator_config(
        config.generator,
        runtime_dir=runtime_dir,
        python_bin=sys.executable,
    )
    manager.write_status()
    return manager


def _emit(payload: dict[str, object], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
        return
    typer.echo(
        f"running={payload.get('running_count', 0)}/{payload.get('camera_count', 0)}"
    )


def _exit_code_for_payload(payload: dict[str, object]) -> int:
    running = int(str(payload.get("running_count", 0)))
    total = int(str(payload.get("camera_count", 0)))
    if running == 0 and total > 0:
        return 3
    if running < total:
        return 2
    return 0


def _output_root_from_config(config_path: Path, out: Path | None) -> Path:
    """Determine output root from config or --out argument."""
    if out is not None:
        return out
    try:
        config = load_config(config_path)
        return config.output.root
    except Exception:
        return Path.cwd() / "artifacts" / "fakecam-error"


def _missing_binary_name(exc: FileNotFoundError) -> str:
    """Extract missing binary name from FileNotFoundError."""
    if exc.filename:
        return Path(exc.filename).name
    return "unknown"


def _emit_error_result(
    scenario: str,
    *,
    output_root: Path,
    binary: str | None = None,
    reason: str | None = None,
    json_output: bool,
) -> dict[str, object]:
    """Build structured error payload for CLI-level failures."""
    if binary:
        error_reason = missing_binary_reason(binary)
    elif reason:
        error_reason = f"runtime_error:{reason}"
    else:
        error_reason = "unknown_error"

    return {
        "run_id": None,
        "scenario": scenario,
        "run_validity": "invalid_prereq",
        "aborted": True,
        "abort_reason": error_reason,
        "sample_counts": {"nic": 0, "system": 0, "stream": 0, "events": 0},
        "artifacts_root": str(output_root),
        "transitions": [],
    }


def _format_error_payload(payload: dict[str, object], *, as_json: bool) -> str:
    """Format error payload for output."""
    if as_json:
        return json.dumps(payload, indent=2, sort_keys=True)
    return (
        f"run_validity={payload['run_validity']}\n"
        f"scenario={payload['scenario']}\n"
        f"abort_reason={payload['abort_reason']}"
    )
