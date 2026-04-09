from __future__ import annotations

import getpass
import json
from pathlib import Path
from typing import Annotated

import typer

from gvstress.core.models import RunValidity
from gvstress.core.preflight import (
    PreflightResult,
    invalid_prereq_result_for_missing_binary,
    run_preflight,
)
from gvstress.core.runner import SSHRunner
from gvstress.dut.environment import collect_local_environment_snapshot

app = typer.Typer(help="DUT inspection commands", no_args_is_help=True)


@app.command("inspect")
def inspect_command(
    host: Annotated[str, typer.Option("--host", help="DUT SSH host.")],
    ifaces: Annotated[
        str, typer.Option("--ifaces", help="Comma-separated DUT interfaces.")
    ],
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit JSON output.")
    ] = False,
    out: Annotated[
        Path | None, typer.Option("--out", help="Output directory for snapshots.")
    ] = None,
    user: Annotated[
        str, typer.Option("--user", help="DUT SSH user.")
    ] = getpass.getuser(),
    port: Annotated[int, typer.Option("--port", help="DUT SSH port.")] = 22,
    ssh_python_bin: Annotated[
        str, typer.Option("--ssh-python-bin", help="Python executable on DUT.")
    ] = "python3",
) -> None:
    dut_ifaces = [iface.strip() for iface in ifaces.split(",") if iface.strip()]
    if not dut_ifaces:
        raise typer.BadParameter("--ifaces must include at least one interface")

    try:
        generator_ifaces = [
            interface.name
            for interface in collect_local_environment_snapshot().interfaces
        ]
        result = run_preflight(
            dut_host=host,
            dut_ifaces=dut_ifaces,
            generator_ifaces=generator_ifaces,
            ssh_runner=SSHRunner(host=host, user=user, port=port),
            out_dir=out,
            ssh_python_bin=ssh_python_bin,
        )
    except FileNotFoundError as exc:
        result = invalid_prereq_result_for_missing_binary(
            _missing_binary_name(exc),
            out_dir=out,
        )

    payload = _payload_for_output(result)
    if json_output:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
    else:
        typer.echo(f"run_validity={payload['run_validity']}")
        for reason in _reasons_from_payload(payload):
            typer.echo(f"reason={reason}")
    raise typer.Exit(code=_exit_code_for_validity(result.run_validity))


def _payload_for_output(result: PreflightResult) -> dict[str, object]:
    return result.to_dict()


def _reasons_from_payload(payload: dict[str, object]) -> list[str]:
    reasons = payload.get("reasons")
    if not isinstance(reasons, list):
        return []
    return [str(reason) for reason in reasons]


def _exit_code_for_validity(validity: RunValidity) -> int:
    if validity is RunValidity.VALID:
        return 0
    return 1


def _missing_binary_name(exc: FileNotFoundError) -> str:
    filename: object | None = exc.filename or (exc.args[0] if exc.args else None)
    return str(filename) if filename else "unknown"
