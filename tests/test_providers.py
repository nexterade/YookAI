import json
import unittest
from unittest.mock import Mock, patch

from providers.base import BaseProvider
from providers.openrouter import OpenRouterProvider
from providers.registry import PROVIDER_REGISTRY, get_provider, list_providers
from app.sse import format_sse, normalize_chunk


class BaseProviderTests(unittest.TestCase):
    def test_abstract_provider_cannot_be_instantiated(self):
        with self.assertRaises(TypeError):
            BaseProvider()


class OpenRouterTests(unittest.TestCase):
    def setUp(self):
        self.provider = OpenRouterProvider("test-key")

    def test_init(self):
        self.assertEqual(self.provider.name, "openrouter")
        self.assertEqual(self.provider.api_key, "test-key")
        self.assertEqual(self.provider.base_url, "https://openrouter.ai/api/v1")

    @patch("providers.openrouter.requests.get")
    def test_list_models(self, mock_get):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "data": [
                {
                    "id": "deepseek/deepseek-r1",
                    "name": "DeepSeek R1",
                    "context_length": 16384,
                }
            ]
        }
        mock_get.return_value = response

        models = self.provider.list_models()

        self.assertEqual(models[0]["id"], "deepseek/deepseek-r1")
        self.assertEqual(models[0]["name"], "DeepSeek R1")
        mock_get.assert_called_once()

        # Cached within the one-hour TTL.
        self.provider.list_models()
        mock_get.assert_called_once()

    @patch("providers.openrouter.requests.post")
    def test_stream_chat_sse(self, mock_post):
        response = Mock()
        response.status_code = 200
        response.iter_lines.return_value = [
            'data: {"choices":[{"delta":{"reasoning":"think"}}]}',
            'data: {"choices":[{"delta":{"content":"hello"}}]}',
            "data: [DONE]",
        ]
        mock_post.return_value = response

        chunks = list(self.provider.stream_chat([], "deepseek/deepseek-r1"))

        self.assertEqual(
            chunks,
            [
                {"type": "reasoning", "content": "think"},
                {"type": "content", "content": "hello"},
                {"type": "done"},
            ],
        )
        mock_post.assert_called_once()
        self.assertEqual(mock_post.call_args.kwargs["headers"]["Accept"], "text/event-stream")
        response.iter_lines.assert_called_once_with(chunk_size=1, decode_unicode=True)

    def test_stop_chat_signal(self):
        request_id = "request-1"
        self.provider._stop_events[request_id] = __import__("threading").Event()
        self.assertTrue(self.provider.stop_chat(request_id))
        self.assertTrue(self.provider._stop_events[request_id].is_set())
        self.assertFalse(self.provider.stop_chat("missing"))

    @patch("providers.openrouter.requests.get")
    def test_auth_error(self, mock_get):
        response = Mock()
        response.status_code = 401
        mock_get.return_value = response
        with self.assertRaises(Exception) as context:
            self.provider.list_models()
        self.assertIn("authentication", str(context.exception).lower())


class RegistryTests(unittest.TestCase):
    def test_openrouter_is_registered(self):
        self.assertIn("openrouter", PROVIDER_REGISTRY)
        self.assertIn("openrouter", list_providers())

    def test_get_provider_with_explicit_configuration(self):
        provider = get_provider("openrouter", api_key="test", base_url="https://example.test")
        self.assertIsInstance(provider, OpenRouterProvider)
        self.assertEqual(provider.api_key, "test")


class SSENormalizationTests(unittest.TestCase):
    def test_normalize_supported_chunks(self):
        self.assertEqual(normalize_chunk({"type": "reasoning", "content": "x"}), {"type": "reasoning", "content": "x"})
        self.assertEqual(normalize_chunk({"type": "content", "content": "y"}), {"type": "content", "content": "y"})
        self.assertEqual(normalize_chunk({"type": "done"}), {"type": "done"})
        self.assertEqual(normalize_chunk({"type": "error", "message": "bad"}), {"type": "error", "message": "bad"})

    def test_normalize_invalid_chunk(self):
        self.assertEqual(normalize_chunk({"type": "wat"})["type"], "error")
        self.assertEqual(normalize_chunk(None)["type"], "error")

    def test_format_sse(self):
        event = format_sse({"type": "content", "content": "hello"})
        self.assertTrue(event.startswith("data: "))
        self.assertTrue(event.endswith("\n\n"))
        self.assertIn('"type": "content"', event)

class UTF8RegressionTests(unittest.TestCase):
    def setUp(self):
        self.provider = OpenRouterProvider("test-key")

    @patch("providers.openrouter.requests.post")
    def test_stream_forces_utf8_and_repairs_double_encoded_text(self, mock_post):
        response = Mock()
        response.status_code = 200
        response.iter_lines.return_value = [
            'data: {"choices":[{"delta":{"content":"Ã¢ÂÂ"}}]}',
            'data: [DONE]',
        ]
        mock_post.return_value = response
        chunks = list(self.provider.stream_chat([], "test/model"))
        self.assertEqual(chunks[0], {"type": "content", "content": "—"})
        self.assertEqual(response.encoding, "utf-8")

class LatencyBenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.provider = OpenRouterProvider("test-key")

    @patch("providers.openrouter.requests.post")
    def test_benchmark_only_free_models_and_returns_ttft(self, mock_post):
        response = Mock()
        response.status_code = 200
        response.iter_lines.return_value = ['data: {"choices":[{"delta":{"content":"ok"}}]}']
        mock_post.return_value = response
        models = [
            {"id": "free/fast", "name": "Fast", "pricing": {"prompt": "0", "completion": "0"}},
            {"id": "paid/skip", "name": "Paid", "pricing": {"prompt": "0.1", "completion": "0.2"}},
        ]
        result = self.provider.benchmark_models(models)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['id'], 'free/fast')
        self.assertIsNotNone(result[0]['ttft_ms'])
        self.assertEqual(mock_post.call_count, 1)
