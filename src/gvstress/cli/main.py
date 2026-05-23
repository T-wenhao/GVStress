# pyright: reportMissingImports=false

import typer

from gvstress import __version__

from gvstress.node.cli import app as node_app

from .baseline import app as baseline_app
from .controller import app as controller_app
from .dut import app as dut_app
from .dut_agent import app as dut_agent_app
from .fakecam import app as fakecam_app
from .report import app as report_app
from .test import app as test_app
from .web import app as web_app

app = typer.Typer(help="GigE Vision stress testing framework")
app.add_typer(baseline_app, name="baseline")
app.add_typer(controller_app, name="controller")
app.add_typer(dut_app, name="dut")
app.add_typer(dut_agent_app, name="dut-agent")
app.add_typer(fakecam_app, name="fakecam")
app.add_typer(node_app, name="node")
app.add_typer(report_app, name="report")
app.add_typer(test_app, name="test")
app.add_typer(web_app, name="web")


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"gvstress version {__version__}")
        raise typer.Exit()


@app.callback()
def common(
    _version: bool = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        help="Show version and exit.",
    ),
) -> None:
    pass


if __name__ == "__main__":
    app()
