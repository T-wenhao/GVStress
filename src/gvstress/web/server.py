"""Web UI server for GVStress monitoring."""

from __future__ import annotations

import json
import mimetypes
import socket
import socketserver
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any, Callable

from gvstress.controller.service import ControllerService
from gvstress.report.indexer import scan_reports


class WebAPIHandler(SimpleHTTPRequestHandler):
    """HTTP handler serving static files and API endpoints."""

    data_dir: Path
    artifacts_dir: Path
    web_dir: Path
    controller: ControllerService

    def __init__(
        self,
        request: socket.socket,
        client_address: tuple[str, int],
        server: HTTPServer,
    ) -> None:
        self.data_dir = getattr(server, "data_dir", Path.cwd() / "data")
        self.artifacts_dir = getattr(server, "artifacts_dir", Path.cwd() / "artifacts")
        self.web_dir = getattr(server, "web_dir", Path(__file__).parent.parent.parent.parent / "web")
        self.controller = ControllerService(self.data_dir)
        super().__init__(request, client_address, server, directory=str(self.web_dir))

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path.startswith("/api/"):
            self.handle_api_get(path[4:], query)
        elif path == "/" or path == "/index.html":
            self.serve_index()
        elif path.startswith("/static/"):
            self.serve_static(path[7:])
        elif path == "/metrics":
            self.serve_metrics()
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/"):
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            try:
                data = json.loads(body) if body else {}
            except json.JSONDecodeError:
                data = {}
            self.handle_api_post(path[4:], data)
        else:
            self.send_error(404)

    def handle_api_get(self, endpoint: str, query: dict[str, list[str]]) -> None:
        if endpoint == "nodes":
            self.send_json_response(self.get_nodes())
        elif endpoint == "tasks":
            self.send_json_response(self.get_tasks())
        elif endpoint == "reports":
            offset = int(query.get("offset", ["0"])[0])
            limit = int(query.get("limit", ["50"])[0])
            search = query.get("search", [""])[0]
            verdict = query.get("verdict", [""])[0]
            self.send_json_response(self.get_reports(offset, limit, search, verdict))
        elif endpoint == "reports/detail":
            path_param = query.get("path", [""])[0]
            self.send_json_response(self.get_report_detail(path_param))
        else:
            self.send_error(404)

    def handle_api_post(self, endpoint: str, data: dict[str, Any]) -> None:
        if endpoint == "tasks":
            result = self.create_task(data)
            self.send_json_response(result, status=201)
        else:
            self.send_error(404)

    def get_nodes(self) -> dict[str, Any]:
        return {
            "nodes": [
                {
                    "id": "local-node",
                    "url": "http://localhost:8080",
                    "role": "standalone",
                    "health_status": "ok",
                    "created_at": "2026-05-21T00:00:00Z",
                    "last_seen_at": "2026-05-21T00:00:00Z",
                }
            ],
            "metrics": {
                "node_up": 1,
                "test_running": 0,
                "job_state": "idle",
                "test_verdict": None,
            },
        }

    def get_tasks(self) -> dict[str, Any]:
        jobs = self.controller.list_jobs()
        return {
            "tasks": [
                {
                    "id": job.id,
                    "name": job.name,
                    "status": job.status.value,
                    "scenario": job.result.get("scenario") if job.result else None,
                    "created_at": job.created_at,
                }
                for job in jobs
            ]
        }

    def create_task(self, data: dict[str, Any]) -> dict[str, Any]:
        name = data.get("name", "unnamed-task")
        job = self.controller.create_job(name=name)
        return {
            "id": job.id,
            "name": job.name,
            "status": job.status.value,
            "created_at": job.created_at,
        }

    def get_reports(
        self, offset: int, limit: int, search: str, verdict: str
    ) -> dict[str, Any]:
        result = scan_reports(self.artifacts_dir, offset=offset, limit=limit)
        entries = result.entries
        if search:
            entries = [e for e in entries if search.lower() in e.run_id.lower()]
        if verdict:
            entries = [e for e in entries if e.verdict == verdict]
        return {
            "entries": [
                {
                    "run_id": e.run_id,
                    "timestamp": e.timestamp,
                    "verdict": e.verdict,
                    "path": e.path,
                }
                for e in entries
            ],
            "total": result.total,
            "offset": result.offset,
            "limit": result.limit,
        }

    def get_report_detail(self, path: str) -> dict[str, Any]:
        if not path:
            return {"error": "path parameter required"}
        try:
            file_path = Path(path)
            if not file_path.exists():
                return {"error": "file not found"}
            content = file_path.read_text(encoding="utf-8")
            return json.loads(content)
        except Exception as e:
            return {"error": str(e)}

    def serve_index(self) -> None:
        index_path = self.web_dir / "index.html"
        if index_path.exists():
            self.send_file(index_path, "text/html")
        else:
            self.send_error(404)

    def serve_static(self, relative_path: str) -> None:
        static_path = self.web_dir / "static" / relative_path
        if static_path.exists():
            mime_type, _ = mimetypes.guess_type(str(static_path))
            self.send_file(static_path, mime_type or "application/octet-stream")
        else:
            self.send_error(404)

    def serve_metrics(self) -> None:
        metrics_text = """# HELP gvstress_node_up Health indicator for the GVStress node
# TYPE gvstress_node_up gauge
gvstress_node_up 1

# HELP gvstress_test_running Indicates whether a test scenario is currently active
# TYPE gvstress_test_running gauge
gvstress_test_running{scenario="none"} 0

# HELP gvstress_job_state_info Current job state
# TYPE gvstress_job_state_info gauge
gvstress_job_state_info{state="idle"} 1
"""
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.end_headers()
        self.wfile.write(metrics_text.encode("utf-8"))

    def send_file(self, path: Path, content_type: str) -> None:
        try:
            content = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except Exception:
            self.send_error(500)

    def send_json_response(
        self, data: dict[str, Any] | list[Any], status: int = 200
    ) -> None:
        content = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format: str, *args: Any) -> None:
        pass


class ThreadedHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    """Threaded HTTP server for handling concurrent requests."""

    daemon_threads = True
    data_dir: Path
    artifacts_dir: Path
    web_dir: Path


def create_handler(
    data_dir: Path | None = None,
    artifacts_dir: Path | None = None,
    web_dir: Path | None = None,
) -> Callable[[socket.socket, tuple[str, int], HTTPServer], WebAPIHandler]:
    """Create a configured request handler class for tests or custom servers."""

    class ConfiguredWebAPIHandler(WebAPIHandler):
        def __init__(
            self,
            request: socket.socket,
            client_address: tuple[str, int],
            server: HTTPServer,
        ) -> None:
            server.data_dir = data_dir or Path.cwd() / "data"  # type: ignore[attr-defined]
            server.artifacts_dir = artifacts_dir or Path.cwd() / "artifacts"  # type: ignore[attr-defined]
            server.web_dir = web_dir or Path(__file__).parent.parent.parent.parent / "web"  # type: ignore[attr-defined]
            super().__init__(request, client_address, server)

    return ConfiguredWebAPIHandler


def create_server(
    host: str = "localhost",
    port: int = 8080,
    data_dir: Path | None = None,
    artifacts_dir: Path | None = None,
    web_dir: Path | None = None,
) -> ThreadedHTTPServer:
    """Create a configured HTTP server."""
    server = ThreadedHTTPServer(
        (host, port),
        create_handler(data_dir=data_dir, artifacts_dir=artifacts_dir, web_dir=web_dir),
    )
    server.data_dir = data_dir or Path.cwd() / "data"
    server.artifacts_dir = artifacts_dir or Path.cwd() / "artifacts"
    server.web_dir = web_dir or Path(__file__).parent.parent.parent.parent / "web"
    return server


def run_server(
    host: str = "localhost",
    port: int = 8080,
    data_dir: Path | None = None,
    artifacts_dir: Path | None = None,
    web_dir: Path | None = None,
) -> None:
    """Run the web UI server."""
    server = create_server(host, port, data_dir, artifacts_dir, web_dir)
    print(f"GVStress Web UI running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
