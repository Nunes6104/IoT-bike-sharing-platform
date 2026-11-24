"""HTTPS analytics API for the Node-RED operator dashboard."""

import hmac
import json
import logging
import ssl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Event
from urllib.parse import parse_qs, urlsplit

from sqlalchemy import Engine, text

from processor.analytics import AnalyticsService


LOGGER = logging.getLogger("processor.api")


class ReadyHTTPServer(ThreadingHTTPServer):
    """Threading HTTP server that signals after its serving loop is active."""

    def __init__(self, server_address, request_handler):
        super().__init__(server_address, request_handler)
        self.ready_event = Event()
        self.is_serving = False

    def service_actions(self) -> None:
        self.is_serving = True
        self.ready_event.set()

    def server_close(self) -> None:
        self.is_serving = False
        super().server_close()


def create_handler(engine: Engine, token: str) -> type[BaseHTTPRequestHandler]:
    """Create a request handler bound to the engine and bearer token."""
    analytics = AnalyticsService(engine)

    class Handler(BaseHTTPRequestHandler):
        server_version = "BikeSharingAnalytics/1.0"

        def do_GET(self) -> None:
            path = urlsplit(self.path)
            if path.path == "/healthz":
                self._health()
                return
            supplied = self.headers.get("Authorization", "")
            expected = f"Bearer {token}"
            if not hmac.compare_digest(supplied, expected):
                self._send_json(401, {"error": "unauthorized"})
                return
            if path.path != "/api/analytics":
                self._send_json(404, {"error": "not found"})
                return
            try:
                query = parse_qs(path.query, strict_parsing=True)
                if set(query) - {"start", "end", "bucket"}:
                    raise ValueError("unsupported query parameter")
                if "start" not in query or "end" not in query:
                    raise ValueError("start and end parameters are required")
                if any(len(values) != 1 for values in query.values()):
                    raise ValueError("query parameters must not be repeated")
                result = analytics.summarize(
                    query["start"][0],
                    query["end"][0],
                    query.get("bucket", ["day"])[0],
                )
            except ValueError as exc:
                self._send_json(400, {"error": str(exc)})
                return
            except Exception:
                LOGGER.exception("Analytics request failed")
                self._send_json(500, {"error": "analytics request failed"})
                return
            self._send_json(200, result)

        def do_POST(self) -> None:
            self._send_json(405, {"error": "method not allowed"})

        def log_message(self, format_string: str, *args: object) -> None:
            LOGGER.info("%s - %s", self.address_string(), format_string % args)

        def _health(self) -> None:
            try:
                with engine.connect() as connection:
                    connection.execute(text("SELECT 1"))
            except Exception:
                LOGGER.exception("Analytics API health check failed")
                self._send_json(503, {"status": "unavailable"})
                return
            self._send_json(200, {"status": "ok"})

        def _send_json(self, status: int, payload: dict) -> None:
            body = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

    return Handler


def create_server(
    engine: Engine,
    token_file: Path,
    certificate_file: Path,
    private_key_file: Path,
    host: str = "0.0.0.0",
    port: int = 8443,
) -> ReadyHTTPServer:
    """Create an HTTPS-only analytics server."""
    token = token_file.read_text(encoding="utf-8").strip()
    if not token:
        raise ValueError("analytics API token is empty")
    server = ReadyHTTPServer((host, port), create_handler(engine, token))
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(certfile=str(certificate_file), keyfile=str(private_key_file))
    server.socket = context.wrap_socket(server.socket, server_side=True)
    return server


def serve(
    engine: Engine,
    token_file: Path,
    certificate_file: Path,
    private_key_file: Path,
    host: str = "0.0.0.0",
    port: int = 8443,
) -> None:
    """Serve the analytics API over HTTPS only."""
    server = create_server(
        engine, token_file, certificate_file, private_key_file, host, port
    )
    LOGGER.info("Analytics HTTPS API listening on %s:%s", host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOGGER.info("Analytics API shutdown requested")
    finally:
        server.server_close()

