import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app.routes import APIHandler, HTTPError
from app.session import SessionManager


class RouteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.config = {
            "provider": {"default": "openrouter", "openrouter": {"api_key": "test-key", "base_url": "https://example.test/api/v1"}},
            "chat": {"default_model": "test-model", "auto_title": True},
            "ui": {"theme": "dark", "sidebar_default": "open"},
            "server": {"host": "127.0.0.1", "port": 0},
        }
        self.manager = SessionManager(Path(self.temp.name))
        self.api = APIHandler(self.config, self.manager)

    def tearDown(self):
        self.temp.cleanup()

    @patch("app.routes.get_provider")
    def test_handle_models(self, mock_get_provider):
        provider = Mock()
        provider.list_models.return_value = [{"id": "test-model", "name": "Test"}]
        mock_get_provider.return_value = provider
        self.assertEqual(self.api.handle_models("openrouter")["models"][0]["id"], "test-model")

    @patch("app.routes.get_provider")
    def test_handle_chat_returns_stream(self, mock_get_provider):
        provider = Mock()
        provider.stream_chat.return_value = iter([{"type": "content", "content": "hello"}, {"type": "done"}])
        mock_get_provider.return_value = provider
        chunks = list(self.api.handle_chat({"model": "test-model", "messages": [{"role": "user", "content": "hi"}]}))
        self.assertEqual(chunks[-1], {"type": "done"})
        provider.stream_chat.assert_called_once()

    def test_handle_chat_invalid_input(self):
        with self.assertRaises(HTTPError) as context:
            self.api.handle_chat({"model": "test-model"})
        self.assertEqual(context.exception.status, 400)

    def test_session_save_and_list(self):
        result = self.api.handle_session_save({"title": "Hello", "messages": [{"role": "user", "content": "hi"}]})
        self.assertTrue(result["ok"])
        self.assertEqual(self.api.handle_session_list()["sessions"][0]["title"], "Hello")

    def test_config_get_masks_api_key(self):
        result = self.api.handle_config_get()
        self.assertNotEqual(result["provider"]["openrouter"]["api_key"], "test-key")
        self.assertIn("***", result["provider"]["openrouter"]["api_key"])

    def test_config_save_preserves_masked_key(self):
        body = json.loads(json.dumps(self.config))
        body["provider"]["openrouter"]["api_key"] = "test-k***-key"
        body["chat"]["default_model"] = "new-model"
        with patch("app.routes.save_config") as mock_save:
            self.assertTrue(self.api.handle_config_save(body)["ok"])
        saved = mock_save.call_args.args[0]
        self.assertEqual(saved["provider"]["openrouter"]["api_key"], "test-key")
        self.assertEqual(saved["chat"]["default_model"], "new-model")


if __name__ == "__main__":
    unittest.main()