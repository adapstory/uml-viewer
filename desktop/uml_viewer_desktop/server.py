"""Local MCP tools and browser surface for the existing UML scene compiler."""

from __future__ import annotations

import json
import os
import secrets
import subprocess
import threading
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from mcp.server.fastmcp import FastMCP

ROOT = Path(__file__).resolve().parents[2]
PAGE = Path(__file__).with_name("viewer.html")
mcp = FastMCP("uml-viewer", instructions="Use show_diagram for an EDN diagram, then open its URL with the Codex open_in_codex browser tool. Use get_selection to read the human's selection, update_diagram after modifying the diagram, and close_diagram when it is no longer needed. Paths must be absolute.")


@dataclass
class Session:
    path: Path
    scene: dict
    version: int = 1
    selection: dict | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)


sessions: dict[str, Session] = {}
sessions_lock = threading.Lock()
server: ThreadingHTTPServer | None = None
server_lock = threading.Lock()


def compile_scene(path: Path) -> dict:
    if not path.is_absolute() or not path.is_file() or path.suffix != ".edn":
        raise ValueError("Expected an absolute path to an existing .edn file")
    command = ["clojure", "-Sdeps", '{:deps {org.clojure/data.json {:mvn/version "2.5.1"}}}',
               "-M", "-m", "uml-viewer.main.desktop-json", str(path)]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                            timeout=120, check=False, env=os.environ.copy())
    if result.returncode:
        raise RuntimeError(f"Diagram compilation failed: {result.stderr.strip()[-4000:]}")
    return json.loads(result.stdout)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass

    def reply(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; base-uri 'none'; frame-ancestors 'self'")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def route(self) -> tuple[Session | None, str]:
        if self.headers.get("Host") != f"127.0.0.1:{self.server.server_port}":
            return None, ""
        parts = urlparse(self.path).path.strip("/").split("/")
        if len(parts) not in (2, 3) or parts[0] != "session":
            return None, ""
        with sessions_lock:
            session = sessions.get(parts[1])
        return session, parts[2] if len(parts) == 3 else "page"

    def do_GET(self) -> None:
        session, action = self.route()
        if session is None:
            self.reply(HTTPStatus.NOT_FOUND, b"Not found", "text/plain")
        elif action == "page":
            self.reply(HTTPStatus.OK, PAGE.read_bytes(), "text/html; charset=utf-8")
        elif action == "scene":
            with session.lock:
                payload = json.dumps({"scene": session.scene, "version": session.version}).encode()
            self.reply(HTTPStatus.OK, payload, "application/json")
        else:
            self.reply(HTTPStatus.NOT_FOUND, b"Not found", "text/plain")

    def do_POST(self) -> None:
        session, action = self.route()
        origin = self.headers.get("Origin")
        expected = f"http://127.0.0.1:{self.server.server_port}"
        if session is None or action != "selection" or origin != expected:
            self.reply(HTTPStatus.FORBIDDEN, b"Forbidden", "text/plain")
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size <= 0 or size > 4096:
                raise ValueError("Invalid body length")
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise ValueError("Invalid selection")
            kind, item_id = data.get("kind"), data.get("id")
            if kind not in ("class", "package") or not isinstance(item_id, str):
                raise ValueError("Invalid selection")
            with session.lock:
                items = session.scene["classes" if kind == "class" else "packages"]
                item = next((item for item in items if str(item.get("id")) == item_id), None)
                if item is None:
                    raise ValueError("Selection is not in the current diagram")
                session.selection = {"kind": kind, "item": item}
            self.reply(HTTPStatus.OK, b'{"ok":true}', "application/json")
        except (ValueError, TypeError, json.JSONDecodeError):
            self.reply(HTTPStatus.BAD_REQUEST, b"Invalid selection", "text/plain")


def ensure_server() -> ThreadingHTTPServer:
    global server
    with server_lock:
        if server is None:
            server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            threading.Thread(target=server.serve_forever, daemon=True).start()
        return server


def find_session(session_id: str) -> Session:
    with sessions_lock:
        session = sessions.get(session_id)
    if session is None:
        raise ValueError("Unknown or expired diagram session")
    return session


@mcp.tool()
def show_diagram(path: str) -> dict:
    """Compile an existing UML viewer EDN diagram and return a URL for the Codex browser panel."""
    diagram = Path(path)
    scene = compile_scene(diagram)
    session_id = secrets.token_urlsafe(24)
    with sessions_lock:
        sessions[session_id] = Session(path=diagram.resolve(), scene=scene)
    port = ensure_server().server_port
    return {"session_id": session_id, "url": f"http://127.0.0.1:{port}/session/{session_id}",
            "title": scene.get("title"), "instruction": "Open url in the Codex browser panel; call get_selection after the human selects an element."}


@mcp.tool()
def update_diagram(session_id: str) -> dict:
    """Reload the original diagram in an existing browser panel after editing its EDN file."""
    session = find_session(session_id)
    scene = compile_scene(session.path)
    with session.lock:
        session.scene = scene
        session.version += 1
        session.selection = None
        version = session.version
    return {"version": version, "title": scene.get("title")}


@mcp.tool()
def get_selection(session_id: str) -> dict:
    """Read the latest element selected by the human in this diagram."""
    session = find_session(session_id)
    with session.lock:
        return {"path": str(session.path), "selection": session.selection, "version": session.version}


@mcp.tool()
def close_diagram(session_id: str) -> dict:
    """Close a diagram session when the human no longer needs it."""
    with sessions_lock:
        if sessions.pop(session_id, None) is None:
            raise ValueError("Unknown or expired diagram session")
    return {"closed": True}


def main() -> None:
    mcp.run(transport="stdio")
