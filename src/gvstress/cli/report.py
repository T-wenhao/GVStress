from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, cast

import typer

app = typer.Typer(help="View and export test reports", no_args_is_help=True)


def _load_report_json(run_json_path: Path) -> dict[str, object]:
    with run_json_path.open(encoding="utf-8") as handle:
        return cast(dict[str, object], json.load(handle))


@app.command("show")
def show_command(
    latest: Annotated[
        bool,
        typer.Option(
            "--latest",
            help="Show the most recent run report from the artifact root.",
        ),
    ] = False,
    run_id: Annotated[
        str | None,
        typer.Option("--run-id", help="Show report for specific run ID."),
    ] = None,
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit JSON output.")
    ] = False,
    source_dir: Annotated[
        Path | None,
        typer.Option(
            "--source",
            "-s",
            help="Artifact root containing run directories.",
        ),
    ] = None,
) -> None:
    if not latest and not run_id:
        raise typer.BadParameter("Must specify --latest or --run-id")

    src_dir = source_dir or Path("artifacts")

    if latest:
        if not src_dir.exists():
            typer.echo(f"Error: No artifact root found at {src_dir}", err=True)
            raise typer.Exit(code=1)

        run_dirs = sorted(
            [d for d in src_dir.iterdir() if d.is_dir()],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not run_dirs:
            typer.echo("Error: No runs found", err=True)
            raise typer.Exit(code=1)
        target_dir: Path = run_dirs[0]
    else:
        target_dir = src_dir / str(run_id)

    run_json_path = target_dir / "reports" / "run.json"
    summary_md_path = target_dir / "reports" / "summary.md"

    if not run_json_path.exists():
        typer.echo(f"Error: No run.json found at {run_json_path}", err=True)
        raise typer.Exit(code=1)

    if json_output:
        data = _load_report_json(run_json_path)
        typer.echo(json.dumps(data, indent=2, sort_keys=True))
    else:
        if summary_md_path.exists():
            with summary_md_path.open(encoding="utf-8") as f:
                typer.echo(f.read())
        else:
            data = _load_report_json(run_json_path)
            scenario = data.get("scenario")
            scenario_name = (
                cast(dict[str, object], scenario).get("name", "unknown")
                if isinstance(scenario, dict)
                else "unknown"
            )
            typer.echo(f"run_id={data.get('run_id', 'unknown')}")
            typer.echo(f"verdict={data.get('verdict', 'unknown')}")
            typer.echo(f"scenario={scenario_name}")


@app.command("export")
def export_command(
    run_id: Annotated[
        str,
        typer.Option("--run-id", help="Run ID to export."),
    ],
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Output path for exported file."),
    ],
    format: Annotated[
        str,
        typer.Option("--format", help="Export format (json)."),
    ] = "json",
    source_dir: Annotated[
        Path | None,
        typer.Option(
            "--source",
            "-s",
            help="Artifact root containing run directories.",
        ),
    ] = None,
) -> None:
    src_dir = source_dir or Path("artifacts")
    run_json_path = src_dir / run_id / "reports" / "run.json"

    if not run_json_path.exists():
        typer.echo(f"Error: No run.json found at {run_json_path}", err=True)
        raise typer.Exit(code=1)

    if format != "json":
        typer.echo(f"Error: Unsupported format '{format}'", err=True)
        raise typer.Exit(code=1)

    data = _load_report_json(run_json_path)

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)

    typer.echo(f"Exported {run_id} to {output}")
