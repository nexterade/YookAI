import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app.routes import APIHandler, HTTPError
from app.session import SessionManager
from providers.openrouter import AuthError, PaymentError, RateLimitError


class APIEndpointTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.sessions = SessionManager(Path(self.tmp.name))
        self.config = {
            "version": "0.1.0",
            "provider": {
                "default": "openrouter",
                "openrouter": {"api_key": "sk-or-v1-secret", "base_url": "https://example.test"},
            },
            "chat": {"default_model": "deepseek/deepseek-r1"},
            "ui": {"theme": "dark"},
            "server": {"host": "127.0.0.1", "port": 8000},
        }
        self.api = APIHandler(self.config, self.sessions)
        self.provider = Mock()
        self.provider.list_models.return_value = [{"id": "test/model", "name": "Test"}]
        self.provider.stream_chat.return_value = iter([
            {"type": "content", "content": "hello"},
            {"type": "done"},
        ])
        self.provider.stop_chat.return_value = True

    def tearDown(self):
        self.tmp.cleanup()

    @patch("app.routes.get_provider")
    def test_get_providers_models(self, get_provider):
        get_provider.return_value = self.provider
        result = self.api.handle_models("openrouter")
        self.assertEqual(result["models"][0]["id"], "test/model")
        get_provider.assert_called_once_with("openrouter", api_key="sk-or-v1-secret", base_url="https://example.test")

    @patch("app.routes.get_provider")
    def test_post_chat_stream(self, get_provider):
        get_provider.return_value = self.provider
        chunks = list(self.api.handle_chat({"model": "test/model", "messages": [{"role": "user", "content": "hi"}]}))
        self.assertEqual(chunks[-1]["type"], "done")
        self.provider.stream_chat.assert_called_once()

    @patch("app.routes.get_provider")
    def test_post_chat_stop(self, get_provider):
        get_provider.return_value = self.provider
        self.assertEqual(self.api.handle_chat_stop({"request_id": "r1"}), {"ok": True, "stopped": True})

    @patch("app.routes.get_provider")
    def test_provider_instance_refreshes_after_config_save(self, get_provider):
        first = Mock()
        first.list_models.return_value = [{"id": "old", "name": "Old"}]
        second = Mock()
        second.list_models.return_value = [{"id": "new", "name": "New"}]
        get_provider.side_effect = [first, second]
        self.api.handle_models("openrouter")
        self.api.handle_config_save({
            "version": "0.1.0",
            "provider": {"default": "openrouter", "openrouter": {"api_key": "new-key", "base_url": "https://new.example"}},
            "chat": {"default_model": "deepseek/deepseek-r1"},
            "ui": {"theme": "dark"},
            "server": {"host": "127.0.0.1", "port": 8000},
        })
        result = self.api.handle_models("openrouter")
        self.assertEqual(result["models"][0]["id"], "new")
        self.assertEqual(get_provider.call_count, 2)

    def test_config_get_masks_server_api_key(self):
        self.api.config["server"]["api_key"] = "server-secret"
        result = self.api.handle_config_get()
        self.assertNotEqual(result["server"]["api_key"], "server-secret")
        self.assertIn("***", result["server"]["api_key"])

    @patch("app.routes.save_config")
    def test_config_save_preserves_server_masked_key(self, save_config):
        self.api.config["server"]["api_key"] = "server-secret"
        incoming = json.loads(json.dumps(self.api.config))
        incoming["server"]["api_key"] = "server***cret"
        self.api.handle_config_save(incoming)
        self.assertEqual(save_config.call_args.args[0]["server"]["api_key"], "server-secret")

    def test_session_save_and_list(self):
        result = self.api.handle_session_save({"title": "Test", "messages": [{"role": "user", "content": "hi"}]})
        self.assertTrue(result["ok"])
        listed = self.api.handle_session_list()
        self.assertEqual(listed["sessions"][0]["id"], result["id"])

    def test_session_get_and_delete(self):
        saved = self.api.handle_session_save({"messages": []})
        loaded = self.api.handle_session_get(saved["id"])
        self.assertEqual(loaded["id"], saved["id"])
        self.assertEqual(self.api.handle_session_delete(saved["id"]), {"ok": True})

    def test_session_not_found_is_404(self):
        with self.assertRaises(HTTPError) as ctx:
            self.api.handle_session_get("2026-10-02-999")
        self.assertEqual(ctx.exception.status, 404)

    def test_config_masks_api_key(self):
        result = self.api.handle_config_get()
        key = result["provider"]["openrouter"]["api_key"]
        self.assertNotEqual(key, "sk-or-v1-secret")
        self.assertIn("***", key)

    @patch("app.routes.save_config")
    def test_config_save_preserves_masked_key(self, save_config):
        incoming = {"provider": {"default": "openrouter", "openrouter": {"api_key": "sk-or-***cret"}}, "chat": {"default_model": "x"}, "ui": {}, "server": {"host": "127.0.0.1", "port": 8000}}
        self.api.handle_config_save(incoming)
        self.assertEqual(self.api.config["provider"]["openrouter"]["api_key"], "sk-or-v1-secret")
        save_config.assert_called_once()

    def test_invalid_chat_messages(self):
        with self.assertRaises(HTTPError) as ctx:
            self.api.handle_chat({"model": "x", "messages": "bad"})
        self.assertEqual(ctx.exception.status, 400)

    def test_invalid_chat_model(self):
        with self.assertRaises(HTTPError) as ctx:
            self.api.handle_chat({"model": "", "messages": []})
        self.assertEqual(ctx.exception.status, 400)

    def test_missing_openrouter_key_is_503(self):
        config = dict(self.config)
        config["provider"] = {"default": "openrouter", "openrouter": {"api_key": ""}}
        api = APIHandler(config, self.sessions)
        with self.assertRaises(HTTPError) as ctx:
            api.handle_chat({"model": "x", "messages": []})
        self.assertEqual(ctx.exception.status, 503)

    @patch("app.routes.get_provider")
    def test_provider_401_maps_to_http_401(self, get_provider):
        self.provider.list_models.side_effect = AuthError("bad key")
        get_provider.return_value = self.provider
        with self.assertRaises(HTTPError) as ctx:
            self.api.handle_models("openrouter")
        self.assertEqual(ctx.exception.status, 401)

    @patch("app.routes.get_provider")
    def test_provider_402_maps_to_http_402(self, get_provider):
        self.provider.list_models.side_effect = PaymentError("credit")
        get_provider.return_value = self.provider
        with self.assertRaises(HTTPError) as ctx:
            self.api.handle_models("openrouter")
        self.assertEqual(ctx.exception.status, 402)

    @patch("app.routes.get_provider")
    def test_provider_429_maps_to_http_429(self, get_provider):
        self.provider.list_models.side_effect = RateLimitError("slow down")
        get_provider.return_value = self.provider
        with self.assertRaises(HTTPError) as ctx:
            self.api.handle_models("openrouter")
        self.assertEqual(ctx.exception.status, 429)

    def test_unknown_provider_is_404(self):
        with self.assertRaises(HTTPError) as ctx:
            self.api.handle_models("missing")
        self.assertEqual(ctx.exception.status, 404)

    def test_invalid_stop_request_is_400(self):
        with self.assertRaises(HTTPError) as ctx:
            self.api.handle_chat_stop({})
        self.assertEqual(ctx.exception.status, 400)


if __name__ == "__main__":
    unittest.main()
