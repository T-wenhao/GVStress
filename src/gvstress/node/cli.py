"""Node service CLI commands."""

import json
from pathlib import Path

import typer
from typing_extensions import Annotated

from .service import NodeService

app = typer.Typer(help="GVStress node service commands")


def get_service(config: Path | None = None) -> NodeService:
    """Get or create node service instance."""
    return NodeService(config_path=config)


@app.command("health")
def health_cmd(
    config: Annotated[Path | None, typer.Option("--config", "-c")] = None,
    json_output: Annotated[bool, typer.Option("--json", "-j")] = False,
) -> None:
    """Check node health status."""
    service = get_service(config)
    status = service.health()

    if json_output:
        typer.echo(json.dumps(status.dict(), indent=2))
    else:
        typer.echo(f"Status: {status.status}")
        typer.echo(f"PID: {status.pid}")
        typer.echo(f"Uptime: {status.uptime_seconds:.1f}s")


@app.command("capabilities")
def capabilities_cmd(
    config: Annotated[Path | None, typer.Option("--config", "-c")] = None,
    json_output: Annotated[bool, typer.Option("--json", "-j")] = False,
) -> None:
    """Show node capabilities."""
    service = get_service(config)
    caps = service.capabilities()

    if json_output:
        typer.echo(json.dumps(caps.dict(), indent=2))
    else:
        typer.echo(f"Version: {caps.version}")
        typer.echo(f"Pktgen available: {caps.pktgen_available}")
        typer.echo(f"Has NET_ADMIN: {caps.has_net_admin}")
        typer.echo(f"Interfaces: {', '.join(caps.interfaces) or 'none detected'}")


@app.command("status")
def status_cmd(
    config: Annotated[Path | None, typer.Option("--config", "-c")] = None,
    json_output: Annotated[bool, typer.Option("--json", "-j")] = False,
) -> None:
    """Show full node status."""
    service = get_service(config)
    status = service.get_status()

    if json_output:
        typer.echo(json.dumps(status, indent=2, default=str))
    else:
        typer.echo("=== Node Status ===")
        typer.echo(f"Health: {status['health']['status']}")
        typer.echo(f"Uptime: {status['health']['uptime_seconds']:.1f}s")
        typer.echo(f"\nCapabilities:")
        typer.echo(f"  Pktgen: {status['capabilities']['pktgen_available']}")
        typer.echo(f"  Interfaces: {len(status['capabilities']['interfaces'])}")
