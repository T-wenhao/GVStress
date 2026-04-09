# pyright: reportMissingImports=false, reportMissingTypeStubs=false, reportCallInDefaultInitializer=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false

from __future__ import annotations

import json
import platform
import socket
from collections.abc import Mapping
from typing import TypeAlias, cast

import typer
from pydantic import ValidationError

from gvstress.config.models import StreamConfig
from gvstress.dut.environment import collect_local_environment_snapshot
from gvstress.dut.stream_probe import StreamProbe, StreamTarget

app = typer.Typer(help="Remote DUT agent", no_args_is_help=True)

JSONScalar: TypeAlias = str | int | float | bool | None
JSONValue: TypeAlias = JSONScalar | list["JSONValue"] | dict[str, "JSONValue"]


def _emit(payload: Mapping[str, JSONValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(dict(payload), sort_keys=True))
        return

    for key, value in payload.items():
        typer.echo(f"{key}={value}")


@app.command()
def ping(
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    _emit({"status": "ok"}, as_json=json_output)


@app.command()
def inspect(
    ifaces: str = typer.Option("", "--ifaces", help="Comma-separated interfaces."),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    if ifaces:
        snapshot = collect_local_environment_snapshot(
            [iface.strip() for iface in ifaces.split(",") if iface.strip()]
        )
        payload = snapshot.to_dict()
    else:
        payload = {
            "hostname": socket.gethostname(),
            "platform": platform.system().lower(),
            "python_version": platform.python_version(),
        }
    _emit(cast(Mapping[str, JSONValue], payload), as_json=json_output)


@app.command("stream-runner")
def stream_runner(
    camera: list[str] = typer.Option(  # noqa: B008
        ..., "--camera", help="Repeat SERIAL@IP for each expected camera."
    ),
    sample_interval_ms: int = typer.Option(  # noqa: B008
        1000, "--sample-interval-ms", help="Statistics sample interval in milliseconds."
    ),
    duration: float | None = typer.Option(  # noqa: B008
        None, "--duration", help="Optional runtime in seconds."
    ),
    packet_resend: bool = typer.Option(  # noqa: B008
        True,
        "--packet-resend/--no-packet-resend",
        help="Enable or disable packet resend requests.",
    ),
    socket_buffer: bool = typer.Option(  # noqa: B008
        True,
        "--socket-buffer/--no-socket-buffer",
        help="Enable or disable Aravis auto socket buffer mode.",
    ),
    socket_buffer_size: int = typer.Option(  # noqa: B008
        1048576, "--socket-buffer-size", help="Socket buffer size to request."
    ),
    frame_retention: int = typer.Option(  # noqa: B008
        200000, "--frame-retention", help="Frame retention setting."
    ),
    initial_packet_timeout: int = typer.Option(  # noqa: B008
        1000, "--initial-packet-timeout", help="Initial packet timeout setting."
    ),
    packet_timeout: int = typer.Option(  # noqa: B008
        2000, "--packet-timeout", help="Packet timeout setting."
    ),
    packet_request_ratio: float = typer.Option(  # noqa: B008
        0.25,
        "--packet-request-ratio",
        help="Maximum resend request ratio per frame.",
    ),
    receiver_priority: int = typer.Option(  # noqa: B008
        0, "--receiver-priority", help="Configured receiver priority snapshot."
    ),
    buffer_count: int = typer.Option(  # noqa: B008
        16, "--buffer-count", help="Number of buffers to preallocate per stream."
    ),
    json_output: bool = typer.Option(  # noqa: B008
        False, "--json", help="Emit JSON output."
    ),
) -> None:
    if sample_interval_ms <= 0:
        raise typer.BadParameter("--sample-interval-ms must be positive")

    try:
        targets = [StreamTarget.from_selector(selector) for selector in camera]
        stream_config = StreamConfig(
            packet_resend=packet_resend,
            socket_buffer=socket_buffer,
            socket_buffer_size=socket_buffer_size,
            frame_retention=frame_retention,
            initial_packet_timeout=initial_packet_timeout,
            packet_timeout=packet_timeout,
            packet_request_ratio=packet_request_ratio,
            receiver_priority=receiver_priority,
            buffer_count=buffer_count,
        )
        probe = StreamProbe(
            targets,
            stream_config,
            sample_interval_s=sample_interval_ms / 1000.0,
        )
        for record in probe.run(duration=duration):
            _emit(cast(Mapping[str, JSONValue], record.to_dict()), as_json=json_output)
    except (ValidationError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    except RuntimeError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
