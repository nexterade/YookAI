import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT=Path(__file__).resolve().parents[1]

class V024FeatureTests(unittest.TestCase):
    def test_provider_registry_and_config(self):
        from providers.registry import list_providers
        providers=list_providers()
        for name in ('openrouter','openai','anthropic','gemini','ollama'):
            self.assertIn(name,providers)
        cfg=json.loads((ROOT/'config.example.json').read_text(encoding='utf-8'))
        for name in ('openrouter','openai','anthropic','gemini','ollama'):
            self.assertIn(name,cfg['provider'])
        self.assertIn('model_profiles',cfg['chat'])

    def test_retry_uses_clicked_user_message(self):
        app=(ROOT/'templates'/'app.js').read_text(encoding='utf-8')
        self.assertIn("target?.role==='user' ? target",app)
        self.assertIn('retryAttachments',app)

    def test_upload_does_not_show_completed_spinner_at_100_percent(self):
        app=(ROOT/'templates'/'app.js').read_text(encoding='utf-8')
        self.assertIn('Math.min(99, Number(progress || 0))',app)
        self.assertIn('temp.progress = 100; temp.uploading = false',app)

    def test_model_profile_and_session_snapshot(self):
        app=(ROOT/'templates'/'app.js').read_text(encoding='utf-8')
        index=(ROOT/'templates'/'index.html').read_text(encoding='utf-8')
        routes=(ROOT/'app'/'routes.py').read_text(encoding='utf-8')
        self.assertIn('model_profiles',app)
        self.assertIn('model-settings-modal',index)
        self.assertIn('model_config',routes)

    def test_startup_menu_has_provider_configuration(self):
        setup=(ROOT/'tools'/'configure.py').read_text(encoding='utf-8')
        for name in ('openrouter','openai','anthropic','gemini','ollama'):
            self.assertIn(name,setup)
        self.assertIn('Credentials / URL',setup)

    def test_stop_request_preserves_provider(self):
        api=(ROOT/'templates'/'api.js').read_text(encoding='utf-8')
        app=(ROOT/'templates'/'app.js').read_text(encoding='utf-8')
        self.assertIn('stopChat(requestId, provider)',api)
        self.assertIn('client.stopChat(requestId, state.currentProvider)',app)

class ProviderSmokeTests(unittest.TestCase):
    def test_openai_parses_sse(self):
        from providers.openai import OpenAIProvider
        p=OpenAIProvider('test')
        r=Mock(status_code=200)
        r.iter_lines.return_value=['data: {"choices":[{"delta":{"content":"hello"}}]}','data: [DONE]']
        with patch('providers.openai.requests.post',return_value=r):
            self.assertEqual(list(p.stream_chat([], 'gpt-test'))[0], {'type':'content','content':'hello'})

    def test_anthropic_parses_sse(self):
        from providers.anthropic import AnthropicProvider
        p=AnthropicProvider('test')
        r=Mock(status_code=200)
        r.iter_lines.return_value=['data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"hello"}}','data: {"type":"message_stop"}']
        with patch('providers.anthropic.requests.post',return_value=r):
            self.assertEqual(list(p.stream_chat([], 'claude-test'))[0], {'type':'content','content':'hello'})

    def test_gemini_parses_sse(self):
        from providers.gemini import GeminiProvider
        p=GeminiProvider('test')
        r=Mock(status_code=200)
        r.iter_lines.return_value=['data: {"candidates":[{"content":{"parts":[{"text":"hello"}]}}]}']
        with patch('providers.gemini.requests.post',return_value=r):
            chunks=list(p.stream_chat([], 'gemini-test'))
            self.assertEqual(chunks[0], {'type':'content','content':'hello'})
            self.assertEqual(chunks[-1], {'type':'done'})

    def test_ollama_parses_ndjson(self):
        from providers.ollama import OllamaProvider
        p=OllamaProvider()
        r=Mock(status_code=200)
        r.iter_lines.return_value=['{"message":{"content":"hello"},"done":false}','{"message":{"content":""},"done":true,"prompt_eval_count":2,"eval_count":3}']
        with patch('providers.ollama.requests.post',return_value=r):
            chunks=list(p.stream_chat([], 'llama3'))
            self.assertEqual(chunks[0], {'type':'content','content':'hello'})
            self.assertEqual(chunks[-1], {'type':'done'})

if __name__=='__main__': unittest.main()
