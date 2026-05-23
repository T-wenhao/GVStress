"""Web UI CLI commands."""

from __future__ import annotations

from pathlib import Path

import typer
from typing_extensions import Annotated

from gvstress.web.server import run_server

app = typer.Typer(help="GVStress Web UI commands")


@app.command("serve")
def serve_cmd(
    host: Annotated[str, typer.Option("--host")] = "localhost",
    port: Annotated[int, typer.Option("--port")] = 8080,
    data_dir: Annotated[Path, typer.Option("--data-dir")] = Path("data"),
    artifacts_dir: Annotated[Path, typer.Option("--artifacts-dir")] = Path("artifacts"),
    web_dir: Annotated[Path | None, typer.Option("--web-dir")] = None,
) -> None:
    """Run the Web monitoring UI."""
    run_server(
        host=host,
        port=port,
        data_dir=data_dir,
        artifacts_dir=artifacts_dir,
        web_dir=web_dir,
    )
