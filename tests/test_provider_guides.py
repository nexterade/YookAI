import io
import unittest
from unittest.mock import patch

from tools.configure import PROVIDER_GUIDES, _show_provider_guide, _provider_menu, _credentials_menu, _model_menu


class ProviderGuideTests(unittest.TestCase):
    def test_all_supported_providers_have_guides(self):
        self.assertEqual(set(PROVIDER_GUIDES), {"openrouter", "openai", "anthropic", "gemini", "ollama"})

    def test_guide_shows_setup_and_provider_specific_details(self):
        for name, expected in {
            "openrouter": "openrouter.ai/keys",
            "openai": "platform.openai.com/api-keys",
            "anthropic": "console.anthropic.com",
            "gemini": "aistudio.google.com/app/apikey",
            "ollama": "ollama pull llama3.2",
        }.items():
            output = io.StringIO()
            with patch("sys.stdout", output):
                _show_provider_guide(name)
            self.assertIn(expected, output.getvalue())

    def test_selecting_provider_displays_guide(self):
        config = {"provider": {"default": "openrouter"}}
        output = io.StringIO()
        with patch("builtins.input", return_value="4"), patch("sys.stdout", output):
            _provider_menu(config)
        self.assertEqual(config["provider"]["default"], "openai")
        self.assertIn("platform.openai.com/api-keys", output.getvalue())

    def test_provider_menu_marks_free_and_paid_tiers(self):
        config = {"provider": {"default": "openrouter"}}
        output = io.StringIO()
        with patch("builtins.input", return_value=""), patch("sys.stdout", output):
            _provider_menu(config)
        menu = output.getvalue()
        self.assertIn("OpenRouter [GRATIS*]", menu)
        self.assertIn("Ollama API [SELF-HOSTED]", menu)
        self.assertIn("Google Gemini [GRATIS*]", menu)
        self.assertIn("OpenAI [BAYAR]", menu)
        self.assertIn("Anthropic [BAYAR]", menu)

    def test_credentials_screen_displays_guide(self):
        config = {"provider": {"default": "gemini", "gemini": {}}}
        output = io.StringIO()
        with patch("builtins.input", side_effect=["", ""]), patch("getpass.getpass", return_value=""), patch("sys.stdout", output):
            _credentials_menu(config)
        self.assertNotIn("aistudio.google.com/app/apikey", output.getvalue())
        self.assertIn("Google Gemini configuration", output.getvalue())


if __name__ == "__main__":
    unittest.main()

class OllamaCliConfigTests(unittest.TestCase):
    def test_switching_to_ollama_uses_ollama_model_not_cloud_model(self):
        config = {"provider": {"default": "openrouter"}, "chat": {"default_model": "qwen/qwen3.8-27b:free"}}
        with patch("builtins.input", return_value="2"), patch("sys.stdout", io.StringIO()):
            _provider_menu(config)
        self.assertEqual(config["provider"]["default"], "ollama")
        self.assertEqual(config["chat"]["default_model"], "llama3.2")
        self.assertEqual(config["chat"]["provider_models"]["openrouter"], "qwen/qwen3.8-27b:free")

    def test_ollama_credentials_show_and_keep_default_url(self):
        config = {"provider": {"default": "ollama", "ollama": {}}, "chat": {"default_model": "llama3.2"}}
        output = io.StringIO()
        with patch("builtins.input", return_value="") as input_mock, patch("sys.stdout", output):
            _credentials_menu(config)
        self.assertEqual(config["provider"]["ollama"]["base_url"], "http://127.0.0.1:11434")
        self.assertEqual(input_mock.call_args.args[0], "Base URL [http://127.0.0.1:11434]: ")

    @patch("tools.configure.OllamaProvider.list_models", return_value=[{"id":"llama3.2"},{"id":"qwen2.5:3b"}])
    def test_ollama_model_menu_selects_server_model(self, list_models):
        config = {"provider": {"default": "ollama", "ollama": {"base_url":"http://192.168.1.10:11434"}}, "chat": {"default_model":"llama3.2"}}
        with patch("builtins.input", return_value="2"), patch("sys.stdout", io.StringIO()):
            _model_menu(config)
        self.assertEqual(config["chat"]["default_model"], "qwen2.5:3b")
        self.assertEqual(config["chat"]["model_strategy"], "manual")
        self.assertEqual(config["chat"]["provider_models"]["ollama"], "qwen2.5:3b")
        list_models.assert_called_once()

    @patch("tools.configure.OllamaProvider.list_models", side_effect=OSError("offline"))
    def test_ollama_model_menu_falls_back_to_manual_entry(self, list_models):
        config = {"provider": {"default": "ollama", "ollama": {}}, "chat": {"default_model":"llama3.2"}}
        with patch("builtins.input", return_value="custom-model:latest"), patch("sys.stdout", io.StringIO()):
            _model_menu(config)
        self.assertEqual(config["chat"]["default_model"], "custom-model:latest")

class ProviderModelIsolationTests(unittest.TestCase):
    def test_switching_to_gemini_uses_gemini_default_and_preserves_openrouter(self):
        config = {"provider": {"default": "openrouter"}, "chat": {"default_model": "qwen/qwen3.8-27b:free"}}
        with patch("builtins.input", return_value="3"), patch("sys.stdout", io.StringIO()):
            _provider_menu(config)
        self.assertEqual(config["chat"]["default_model"], "gemini-2.5-flash")
        self.assertEqual(config["chat"]["provider_models"]["openrouter"], "qwen/qwen3.8-27b:free")
        self.assertEqual(config["chat"]["model_strategy"], "manual")

    @patch("tools.configure.GeminiProvider.list_models", return_value=[{"id":"gemini-2.0-flash"},{"id":"gemini-2.5-flash"}])
    def test_gemini_auto_uses_provider_model_catalog_not_openrouter_latency(self, list_models):
        config = {"provider":{"default":"gemini","gemini":{"api_key":"test"}},"chat":{"default_model":"qwen/qwen3.8-27b:free","provider_models":{"openrouter":"qwen/qwen3.8-27b:free"}}}
        with patch("builtins.input", return_value="1"), patch("sys.stdout", io.StringIO()):
            _model_menu(config)
        self.assertEqual(config["chat"]["default_model"], "gemini-2.5-flash")
        self.assertEqual(config["chat"]["provider_models"]["gemini"], "gemini-2.5-flash")
        self.assertEqual(config["chat"]["model_strategy"], "provider-auto")
        list_models.assert_called_once()

    @patch("tools.configure.GeminiProvider.list_models", return_value=[{"id":"gemini-2.0-flash"}])
    def test_gemini_auto_falls_back_to_available_catalog_model(self, list_models):
        config = {"provider":{"default":"gemini","gemini":{"api_key":"test"}},"chat":{"default_model":"qwen/qwen3.8-27b:free"}}
        with patch("builtins.input", return_value="1"), patch("sys.stdout", io.StringIO()):
            _model_menu(config)
        self.assertEqual(config["chat"]["default_model"], "gemini-2.0-flash")

    def test_gemini_auto_without_credentials_uses_gemini_default_not_previous_cloud_model(self):
        config = {"provider":{"default":"gemini","gemini":{}},"chat":{"default_model":"qwen/qwen3.8-27b:free"}}
        with patch("builtins.input", return_value="1"), patch("sys.stdout", io.StringIO()):
            _model_menu(config)
        self.assertEqual(config["chat"]["default_model"], "gemini-2.5-flash")
        self.assertEqual(config["chat"]["model_strategy"], "manual")
