"""HTTP transport and route dispatch for YookAI."""

import json
import uuid
from email.parser import BytesParser
from email.policy import default as email_default
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

from jinja2 import Environment, FileSystemLoader, select_autoescape

from core.log import setup_logger
from core.paths import get_project_root
from providers.registry import list_providers

from .routes import APIHandler, HTTPError
from .sse import SSEStreamer

LOGGER = setup_logger("yookai.server")


class YookAIServer:
    """Own the threaded HTTP server and application API handler."""

    def __init__(self, host, port, config):
        self.host = host
        self.port = port
        self.config = config
        self.api = APIHandler(config)
        self.instance_id = uuid.uuid4().hex
        self.httpd = None
        templates_root = get_project_root() / "templates"
        self.template_env = Environment(
            loader=FileSystemLoader([str(templates_root), str(templates_root / "_shared")]),
            comment_start_string="{##",
            comment_end_string="##}",
            autoescape=select_autoescape(["html", "xml"]),
        )

    def setup_routes(self):
        """Return the documented API route table."""
        return {
            "GET /api/providers": "providers",
            "GET /api/providers/{name}/models": "models",
            "POST /api/chat": "chat",
            "POST /api/attachments": "attachment_upload",
            "GET /api/attachments": "attachment_list",
            "DELETE /api/attachments/{id}": "attachment_delete",
            "POST /api/attachments/cleanup": "attachment_cleanup",
            "GET /api/memory": "memory_list",
            "DELETE /api/memory/{id}": "memory_delete",
            "POST /api/memory/clear": "memory_clear",
            "GET /api/session/{id}/stats": "session_stats",
            "POST /api/chat/stop": "chat_stop",
            "GET /api/session/list": "session_list",
            "POST /api/session/save": "session_save",
            "GET /api/session/{id}": "session_get",
            "DELETE /api/session/{id}": "session_delete",
            "GET /api/session/{id}/export": "session_export",
            "POST /api/session/import": "session_import",
            "GET /api/config": "config_get",
            "POST /api/config": "config_save",
        }

    def run(self):
        """Start serving requests until shutdown."""
        owner = self

        class BoundHandler(YookAIRequestHandler):
            yookai_server = owner

        self.httpd = ThreadingHTTPServer((self.host, self.port), BoundHandler)
        LOGGER.info("Listening on http://%s:%s/", self.host, self.httpd.server_address[1])
        try:
            self.httpd.serve_forever()
        finally:
            self.httpd.server_close()

    def stop(self):
        """Shutdown the server if running."""
        if self.httpd is not None:
            self.httpd.shutdown()


class YookAIRequestHandler(BaseHTTPRequestHandler):
    """Translate HTTP requests into APIHandler operations."""

    yookai_server = None
    server_version = "YookAI/0.3.0-final"

    def _api(self):
        return self.yookai_server.api

    def handle_one_request(self):
        try:
            return super().handle_one_request()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            self.close_connection = True
            LOGGER.debug("HTTP client disconnected before request completion")

    def _json_response(self, data, status=200):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        try:
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            self.close_connection = True

    def _sse_response(self, stream):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        sse = SSEStreamer(self.wfile)
        try:
            for chunk in stream:
                sse.send_event(chunk)
        except (BrokenPipeError, ConnectionResetError):
            LOGGER.info("SSE client disconnected")
        finally:
            sse.close()

    def _read_raw_body(self, max_length=25 * 1024 * 1024):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise HTTPError(400, "Invalid Content-Length") from exc
        if length < 0 or length > max_length:
            raise HTTPError(413, "Request body too large")
        return self.rfile.read(length)

    def _read_multipart_upload(self):
        content_type = self.headers.get("Content-Type", "")
        if not content_type.lower().startswith("multipart/form-data"):
            raise HTTPError(415, "Expected multipart/form-data")
        raw = self._read_raw_body()
        envelope = (f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n").encode("utf-8") + raw
        try:
            message = BytesParser(policy=email_default).parsebytes(envelope)
        except Exception as exc:
            raise HTTPError(400, "Invalid multipart body") from exc
        for part in message.walk():
            if part.is_multipart():
                continue
            filename = part.get_filename()
            if filename:
                return filename, part.get_content_type(), part.get_payload(decode=True) or b""
        raise HTTPError(400, "No file part found")

    def _read_body(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise HTTPError(400, "Invalid Content-Length") from exc
        if length < 0 or length > 10 * 1024 * 1024:
            raise HTTPError(413, "Request body too large")
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HTTPError(400, "Invalid JSON body") from exc

    def _check_auth(self):
        expected = self.yookai_server.config.get("server", {}).get("api_key")
        if not expected:
            return True
        if self.headers.get("Authorization", "") == f"Bearer {expected}":
            return True
        self._json_response({"error": "Unauthorized"}, 401)
        return False

    def _dispatch(self, method, path):
        if not self._check_auth():
            return
        api = self._api()
        if method == "GET" and path == "/api/providers":
            return self._json_response(api.handle_provider_specs())
        if method == "GET" and path == "/api/models":
            return self._json_response(api.handle_catalog())
        if method == "GET" and path == "/api/providers/health":
            return self._json_response(api.handle_provider_health())
        if method == "GET" and path.startswith("/api/providers/") and path.endswith("/health"):
            name = unquote(path[len("/api/providers/"):-len("/health")]).strip("/")
            return self._json_response(api.handle_provider_health(name))
        if method == "POST" and path.startswith("/api/providers/") and path.endswith("/benchmark"):
            name = unquote(path[len("/api/providers/"):-len("/benchmark")]).strip("/")
            return self._json_response(api.handle_benchmark(name))
        if method == "GET" and path.startswith("/api/providers/") and path.endswith("/models"):
            name = unquote(path[len("/api/providers/"):-len("/models")]).strip("/")
            return self._json_response(api.handle_models(name))
        if method == "GET" and path.startswith("/api/session/") and path.endswith("/export"):
            session_id = unquote(path[len("/api/session/"):-len("/export")]).strip("/")
            return self._json_response(api.handle_export_session(session_id))
        if method == "GET" and path.startswith("/api/session/") and path.endswith("/stats"):
            session_id = unquote(path[len("/api/session/"):-len("/stats")]).strip("/")
            return self._json_response(api.handle_session_stats(session_id))
        if method == "POST" and path == "/api/attachments":
            filename, mime, data = self._read_multipart_upload()
            return self._json_response(api.handle_attachment_upload(filename, mime, data), 201)
        if method == "GET" and path == "/api/attachments":
            return self._json_response(api.handle_attachment_list())
        if method == "POST" and path == "/api/attachments/cleanup":
            return self._json_response(api.handle_attachment_cleanup())
        if method == "DELETE" and path.startswith("/api/attachments/"):
            return self._json_response(api.handle_attachment_delete(unquote(path[len("/api/attachments/"):])) )
        if method == "GET" and path == "/api/memory":
            from urllib.parse import parse_qs
            qs=parse_qs(urlparse(self.path).query)
            return self._json_response(api.handle_memory_list(qs.get("q",[""])[0], qs.get("mode",[None])[0], qs.get("project_id",[None])[0]))
        if method == "DELETE" and path.startswith("/api/memory/"):
            return self._json_response(api.handle_memory_delete(unquote(path[len("/api/memory/"):])) )
        if method == "GET" and path == "/api/session/list":
            return self._json_response(api.handle_session_list())
        if method == "GET" and path.startswith("/api/session/"):
            return self._json_response(api.handle_session_get(unquote(path[len("/api/session/"):])) )
        if method == "DELETE" and path.startswith("/api/session/"):
            return self._json_response(api.handle_session_delete(unquote(path[len("/api/session/"):])) )
        if method == "GET" and path == "/api/config":
            payload = api.handle_config_get()
            payload["_server_instance_id"] = self.yookai_server.instance_id
            return self._json_response(payload)
        if method == "GET" and path == "/api/tools":
            return self._json_response(api.handle_tools())

        body = self._read_body()
        if method == "POST" and path == "/api/tools/execute":
            return self._json_response(api.handle_tool_execute(body))
        if method == "POST" and path == "/api/chat":
            return self._sse_response(api.handle_chat(body))
        if method == "POST" and path == "/api/chat/stop":
            return self._json_response(api.handle_chat_stop(body))
        if method == "POST" and path == "/api/session/import":
            return self._json_response(api.handle_import_session(body), 201)
        if method == "POST" and path == "/api/memory/clear":
            return self._json_response(api.handle_memory_clear(body.get("mode"), body.get("project_id")))
        if method == "POST" and path == "/api/session/save":
            return self._json_response(api.handle_session_save(body))
        if method == "POST" and path == "/api/config":
            return self._json_response(api.handle_config_save(body))
        raise HTTPError(404, "Route not found")

    def _handle(self, method):
        path = urlparse(self.path).path
        try:
            self._dispatch(method, path)
        except HTTPError as exc:
            self._json_response({"error": exc.message}, exc.status)
        except Exception as exc:
            LOGGER.exception("Unhandled request error")
            self._json_response({"error": str(exc)}, 500)

    def do_GET(self):
        path = urlparse(self.path).path
        if path.startswith("/api/"):
            self._handle("GET")
        elif path == "/":
            self._serve_placeholder()
        else:
            self._json_response({"error": "Route not found"}, 404)

    def do_POST(self):
        self._handle("POST")

    def do_DELETE(self):
        self._handle("DELETE")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def _serve_placeholder(self):
        try:
            html = self.yookai_server.template_env.get_template("index.html").render()
        except Exception as exc:
            LOGGER.exception("Frontend render failed")
            self._json_response({"error": f"Frontend render failed: {exc}"}, 500)
            return
        payload = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        try:
            self.wfile.write(payload)
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            # Client navigation/cancellation can close the socket before the
            # complete document is written. This is an expected disconnect.
            LOGGER.debug("HTTP client disconnected while serving frontend", exc_info=True)

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("Referrer-Policy", "no-referrer")
        super().end_headers()

    def log_message(self, fmt, *args):
        LOGGER.info("%s - %s", self.address_string(), fmt % args)