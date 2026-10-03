import json
import threading
import time
import unittest
from http.client import HTTPConnection
from pathlib import Path
from tempfile import TemporaryDirectory

from app.server import YookAIServer
from app.session import SessionManager
from core.attachments import AttachmentStore


class ServerIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        config = {
            "version": "0.1.0",
            "provider": {"default": "openrouter", "openrouter": {"api_key": ""}},
            "chat": {"default_model": "deepseek/deepseek-r1"},
            "ui": {"theme": "dark"},
            "server": {"host": "127.0.0.1", "port": 0},
        }
        self.server = YookAIServer("127.0.0.1", 0, config)
        self.server.api.sessions = SessionManager(Path(self.tmp.name))
        self.server.api.attachments = AttachmentStore(Path(self.tmp.name) / "attachments")
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.thread.start()
        deadline = time.time() + 3
        while self.server.httpd is None and time.time() < deadline:
            time.sleep(0.01)
        self.assertIsNotNone(self.server.httpd)
        self.port = self.server.httpd.server_address[1]

    def tearDown(self):
        self.server.stop()
        self.thread.join(timeout=3)
        self.tmp.cleanup()

    def request(self, method, path, body=None):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=3)
        payload = None
        headers = {}
        if body is not None:
            payload = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        conn.request(method, path, body=payload, headers=headers)
        response = conn.getresponse()
        data = response.read()
        return response, data

    def test_root_renders_frontend(self):
        response, data = self.request("GET", "/")
        text = data.decode()
        self.assertEqual(response.status, 200)
        self.assertIn("YookAI", text)
        self.assertIn('application-version" content="0.3.8"', text)
        self.assertNotIn("cdnjs", text)
        self.assertNotIn("jsdelivr", text)
        self.assertNotIn("unpkg", text)

    def test_attachment_upload_multipart(self):
        boundary = "----YookAI-Test"
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="note.txt"\r\n'
            "Content-Type: text/plain\r\n\r\n"
            "hello attachment\r\n"
            f"--{boundary}--\r\n"
        ).encode()
        conn = HTTPConnection("127.0.0.1", self.port, timeout=3)
        conn.request("POST", "/api/attachments", body=body, headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(body)),
        })
        response = conn.getresponse()
        data = json.loads(response.read())
        self.assertEqual(response.status, 201)
        self.assertEqual(data["name"], "note.txt")

    def test_api_providers_and_unknown_route(self):
        response, data = self.request("GET", "/api/providers")
        self.assertEqual(response.status, 200)
        self.assertEqual(json.loads(data)["providers"][0]["name"], "openrouter")
        missing, _ = self.request("GET", "/not-found")
        self.assertEqual(missing.status, 404)

    def test_security_headers_and_no_wildcard_cors(self):
        response, _ = self.request("GET", "/api/providers")
        self.assertEqual(response.getheader("X-Content-Type-Options"), "nosniff")
        self.assertEqual(response.getheader("X-Frame-Options"), "SAMEORIGIN")
        self.assertIsNone(response.getheader("Access-Control-Allow-Origin"))

    def test_config_response_does_not_expose_credentials(self):
        self.server.config["provider"]["openrouter"]["api_key"] = "sk-or-v1-secret"
        response, data = self.request("GET", "/api/config")
        self.assertEqual(response.status, 200)
        result = json.loads(data)
        self.assertNotEqual(result["provider"]["openrouter"]["api_key"], "sk-or-v1-secret")
        self.assertEqual(result["_server_instance_id"], self.server.instance_id)

    def test_config_save_updates_server_runtime_config(self):
        body = {
            "version": "0.1.0",
            "provider": {"default": "openrouter", "openrouter": {"api_key": ""}},
            "chat": {"default_model": "deepseek/deepseek-r1"},
            "ui": {"theme": "dark"},
            "server": {"host": "127.0.0.1", "port": 8000, "api_key": "new-server-secret"},
        }
        response, _ = self.request("POST", "/api/config", body)
        self.assertEqual(response.status, 200)
        unauthorized, _ = self.request("GET", "/api/providers")
        self.assertEqual(unauthorized.status, 401)
        conn = HTTPConnection("127.0.0.1", self.port, timeout=3)
        conn.request("GET", "/api/providers", headers={"Authorization": "Bearer new-server-secret"})
        authorized = conn.getresponse()
        authorized.read()
        self.assertEqual(authorized.status, 200)

    def test_auth_protects_api_when_server_key_configured(self):
        self.server.config["server"]["api_key"] = "server-secret"
        unauthorized, _ = self.request("GET", "/api/providers")
        self.assertEqual(unauthorized.status, 401)
        conn = HTTPConnection("127.0.0.1", self.port, timeout=3)
        conn.request("GET", "/api/providers", headers={"Authorization": "Bearer server-secret"})
        authorized = conn.getresponse()
        authorized.read()
        self.assertEqual(authorized.status, 200)


if __name__ == "__main__":
    unittest.main()
