"""Controller service CLI commands."""

from __future__ import annotations

import json
import socket
import socketserver
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import typer
from typing_extensions import Annotated

from gvstress.controller.service import ControllerService

app = typer.Typer(help="GVStress controller service commands")


class ControllerAPIHandler(BaseHTTPRequestHandler):
    """Minimal HTTP API for controller job management."""

    data_dir: Path
    controller: ControllerService

    def __init__(
        self,
        request: socket.socket,
        client_address: tuple[str, int],
        server: HTTPServer,
    ) -> None:
        self.data_dir = getattr(server, "data_dir", Path.cwd() / "data")
        self.controller = ControllerService(self.data_dir)
        super().__init__(request, client_address, server)

    def do_GET(self) -> None:
        """Handle read-only controller endpoints."""
        if self.path == "/health":
            self._send_json({"status": "ok"})
            return
        if self.path == "/api/jobs":
            self._send_json(
                {
                    "jobs": [
                        job.model_dump(mode="json")
                        for job in self.controller.list_jobs()
                    ]
                }
            )
            return
        if self.path.startswith("/api/jobs/"):
            job_id = self.path.rsplit("/", 1)[-1]
            job = self.controller.get_job(job_id)
            if job is None:
                self._send_json({"error": "job not found"}, status=404)
            else:
                self._send_json(job.model_dump(mode="json"))
            return
        self.send_error(404)

    def do_POST(self) -> None:
        """Handle job creation."""
        if self.path != "/api/jobs":
            self.send_error(404)
            return
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        try:
            payload = json.loads(body) if body else {}
        except json.JSONDecodeError:
            payload = {}
        name = str(payload.get("name") or "unnamed-job")
        job = self.controller.create_job(name=name)
        self._send_json(job.model_dump(mode="json"), status=201)

    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        content = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format: str, *args: Any) -> None:
        pass


class ThreadedControllerServer(socketserver.ThreadingMixIn, HTTPServer):
    """Threaded HTTP server for the controller API."""

    daemon_threads = True
    data_dir: Path


def create_controller_server(
    host: str,
    port: int,
    data_dir: Path,
) -> ThreadedControllerServer:
    """Create the controller HTTP server."""
    server = ThreadedControllerServer((host, port), ControllerAPIHandler)
    server.data_dir = data_dir
    return server


@app.command("serve")
def serve_cmd(
    host: Annotated[str, typer.Option("--host")] = "localhost",
    port: Annotated[int, typer.Option("--port")] = 8079,
    data_dir: Annotated[Path, typer.Option("--data-dir")] = Path("data"),
) -> None:
    """Run the controller HTTP API service."""
    server = create_controller_server(host, port, data_dir)
    typer.echo(f"GVStress controller API running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
