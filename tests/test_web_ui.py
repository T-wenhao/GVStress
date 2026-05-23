# pyright: reportMissingImports=false, reportMissingTypeStubs=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnannotatedClassAttribute=false, reportReturnType=false, reportIndexIssue=false, reportArgumentType=false, reportAny=false

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest

from gvstress.web.server import create_handler, create_server, run_server, WebAPIHandler


@pytest.fixture
def web_test_env(tmp_path: Path) -> tuple[Path, Path, Path]:
    data_dir = tmp_path / "data"
    artifacts_dir = tmp_path / "artifacts"
    web_dir = tmp_path / "web"
    data_dir.mkdir()
    artifacts_dir.mkdir()
    web_dir.mkdir()
    static_dir = web_dir / "static"
    static_dir.mkdir()
    css_dir = static_dir / "css"
    js_dir = static_dir / "js"
    css_dir.mkdir()
    js_dir.mkdir()
    index_html = web_dir / "index.html"
    index_html.write_text("<html><body>GVStress</body></html>")
    style_css = css_dir / "style.css"
    style_css.write_text(":root { --bg: #000; }")
    app_js = js_dir / "app.js"
    app_js.write_text("function init() {}")
    return data_dir, artifacts_dir, web_dir


def make_server(handler):
    from http.server import HTTPServer

    try:
        return HTTPServer(("localhost", 0), handler)
    except PermissionError as exc:
        pytest.skip(f"Local socket binding is not permitted: {exc}")


def test_create_handler_returns_callable(web_test_env: tuple[Path, Path, Path]) -> None:
    data_dir, artifacts_dir, web_dir = web_test_env
    handler = create_handler(data_dir, artifacts_dir, web_dir)
    assert callable(handler)


def test_handler_serves_index_html(web_test_env: tuple[Path, Path, Path]) -> None:
    data_dir, artifacts_dir, web_dir = web_test_env

    handler = create_handler(data_dir, artifacts_dir, web_dir)
    server = make_server(handler)
    port = server.server_port
    thread = threading.Thread(target=server.handle_request)
    thread.start()
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("localhost", port))
    sock.sendall(b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n")
    response = sock.recv(4096).decode("utf-8")
    sock.close()
    server.server_close()
    assert "GVStress" in response


def test_api_nodes_endpoint(web_test_env: tuple[Path, Path, Path]) -> None:
    data_dir, artifacts_dir, web_dir = web_test_env

    handler = create_handler(data_dir, artifacts_dir, web_dir)
    server = make_server(handler)
    port = server.server_port
    thread = threading.Thread(target=server.handle_request)
    thread.start()
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("localhost", port))
    sock.sendall(b"GET /api/nodes HTTP/1.1\r\nHost: localhost\r\n\r\n")
    response = sock.recv(4096).decode("utf-8")
    sock.close()
    server.server_close()
    assert "application/json" in response
    body_start = response.find("\r\n\r\n") + 4
    body = response[body_start:]
    data = json.loads(body)
    assert "nodes" in data
    assert len(data["nodes"]) >= 1
    assert data["nodes"][0]["id"] == "local-node"


def test_api_tasks_endpoint_empty(web_test_env: tuple[Path, Path, Path]) -> None:
    data_dir, artifacts_dir, web_dir = web_test_env

    handler = create_handler(data_dir, artifacts_dir, web_dir)
    server = make_server(handler)
    port = server.server_port
    thread = threading.Thread(target=server.handle_request)
    thread.start()
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("localhost", port))
    sock.sendall(b"GET /api/tasks HTTP/1.1\r\nHost: localhost\r\n\r\n")
    response = sock.recv(4096).decode("utf-8")
    sock.close()
    server.server_close()
    assert "application/json" in response
    body_start = response.find("\r\n\r\n") + 4
    body = response[body_start:]
    data = json.loads(body)
    assert "tasks" in data
    assert data["tasks"] == []


def test_api_tasks_create(web_test_env: tuple[Path, Path, Path]) -> None:
    data_dir, artifacts_dir, web_dir = web_test_env

    handler = create_handler(data_dir, artifacts_dir, web_dir)
    server = make_server(handler)
    port = server.server_port
    thread = threading.Thread(target=server.handle_request)
    thread.start()
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("localhost", port))
    body = json.dumps({"name": "test-task", "scenario": "smoke", "node_id": "local-node"})
    request = f"POST /api/tasks HTTP/1.1\r\nHost: localhost\r\nContent-Type: application/json\r\nContent-Length: {len(body)}\r\n\r\n{body}"
    sock.sendall(request.encode("utf-8"))
    response = sock.recv(4096).decode("utf-8")
    sock.close()
    server.server_close()
    assert "201" in response or "200" in response
    body_start = response.find("\r\n\r\n") + 4
    resp_body = response[body_start:]
    data = json.loads(resp_body)
    assert data["name"] == "test-task"
    assert data["status"] == "pending"


def test_api_reports_endpoint_empty(web_test_env: tuple[Path, Path, Path]) -> None:
    data_dir, artifacts_dir, web_dir = web_test_env

    handler = create_handler(data_dir, artifacts_dir, web_dir)
    server = make_server(handler)
    port = server.server_port
    thread = threading.Thread(target=server.handle_request)
    thread.start()
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("localhost", port))
    sock.sendall(b"GET /api/reports HTTP/1.1\r\nHost: localhost\r\n\r\n")
    response = sock.recv(4096).decode("utf-8")
    sock.close()
    server.server_close()
    assert "application/json" in response
    body_start = response.find("\r\n\r\n") + 4
    body = response[body_start:]
    data = json.loads(body)
    assert "entries" in data
    assert data["entries"] == []


def test_api_reports_with_data(web_test_env: tuple[Path, Path, Path]) -> None:
    data_dir, artifacts_dir, web_dir = web_test_env
    run_dir = artifacts_dir / "smoke" / "runs" / "run-001" / "reports"
    run_dir.mkdir(parents=True)
    run_json = run_dir / "run.json"
    run_json.write_text(json.dumps({"run_id": "run-001", "timestamp": "2026-05-21T10:00:00Z", "verdict": "pass"}))

    handler = create_handler(data_dir, artifacts_dir, web_dir)
    server = make_server(handler)
    port = server.server_port
    thread = threading.Thread(target=server.handle_request)
    thread.start()
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("localhost", port))
    sock.sendall(b"GET /api/reports HTTP/1.1\r\nHost: localhost\r\n\r\n")
    response = sock.recv(4096).decode("utf-8")
    sock.close()
    server.server_close()
    assert "application/json" in response
    body_start = response.find("\r\n\r\n") + 4
    body = response[body_start:]
    data = json.loads(body)
    assert "entries" in data
    assert len(data["entries"]) == 1
    assert data["entries"][0]["run_id"] == "run-001"
    assert data["entries"][0]["verdict"] == "pass"


def test_metrics_endpoint(web_test_env: tuple[Path, Path, Path]) -> None:
    data_dir, artifacts_dir, web_dir = web_test_env

    handler = create_handler(data_dir, artifacts_dir, web_dir)
    server = make_server(handler)
    port = server.server_port
    thread = threading.Thread(target=server.handle_request)
    thread.start()
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("localhost", port))
    sock.sendall(b"GET /metrics HTTP/1.1\r\nHost: localhost\r\n\r\n")
    response = sock.recv(4096).decode("utf-8")
    sock.close()
    server.server_close()
    assert "text/plain" in response
    assert "gvstress_node_up" in response
    assert "gvstress_test_running" in response


def test_static_css_served(web_test_env: tuple[Path, Path, Path]) -> None:
    data_dir, artifacts_dir, web_dir = web_test_env

    handler = create_handler(data_dir, artifacts_dir, web_dir)
    server = make_server(handler)
    port = server.server_port
    thread = threading.Thread(target=server.handle_request)
    thread.start()
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("localhost", port))
    sock.sendall(b"GET /static/css/style.css HTTP/1.1\r\nHost: localhost\r\n\r\n")
    response = sock.recv(4096).decode("utf-8")
    sock.close()
    server.server_close()
    assert "text/css" in response or ":root" in response


def test_static_js_served(web_test_env: tuple[Path, Path, Path]) -> None:
    data_dir, artifacts_dir, web_dir = web_test_env

    handler = create_handler(data_dir, artifacts_dir, web_dir)
    server = make_server(handler)
    port = server.server_port
    thread = threading.Thread(target=server.handle_request)
    thread.start()
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("localhost", port))
    sock.sendall(b"GET /static/js/app.js HTTP/1.1\r\nHost: localhost\r\n\r\n")
    response = sock.recv(4096).decode("utf-8")
    sock.close()
    server.server_close()
    assert "application/javascript" in response or "text/javascript" in response or "function init" in response


def test_run_server_function_exists() -> None:
    assert callable(run_server)
