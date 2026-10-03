import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class V022FeatureTests(unittest.TestCase):
    def test_history_is_persisted_before_upstream_streaming(self):
        app = (ROOT / 'templates' / 'app.js').read_text(encoding='utf-8')
        self.assertIn('async function ensureSessionPersisted()', app)
        self.assertIn('await ensureSessionPersisted();', app)
        self.assertIn('session_id: state.currentSessionId', app)

    def test_zip_is_selectable_from_attachment_input(self):
        composer = (ROOT / 'templates' / 'partials' / 'composer.html').read_text(encoding='utf-8')
        self.assertIn('.zip', composer)

    def test_low_latency_streaming_instrumentation_exists(self):
        provider = (ROOT / 'providers' / 'openrouter.py').read_text(encoding='utf-8')
        self.assertIn('iter_lines(chunk_size=1, decode_unicode=True)', provider)
        self.assertIn('first_event_ms', provider)
        self.assertIn('Accept": "text/event-stream"', provider)


if __name__ == '__main__':
    unittest.main()

class V023FeatureTests(unittest.TestCase):
    def test_startup_menu_and_latency_strategy(self):
        server = (ROOT / 'server.py').read_text(encoding='utf-8')
        setup = (ROOT / 'tools' / 'configure.py').read_text(encoding='utf-8')
        self.assertIn('--no-configure', server)
        self.assertIn('interactive_config', server)
        self.assertIn('latency-best-free', setup)
        self.assertIn('benchmark_models', setup)

    def test_upload_progress_uses_xhr_and_busy_state(self):
        api = (ROOT / 'templates' / 'api.js').read_text(encoding='utf-8')
        app = (ROOT / 'templates' / 'app.js').read_text(encoding='utf-8')
        css = (ROOT / 'templates' / 'style.css').read_text(encoding='utf-8')
        self.assertIn('xhr.upload', api)
        self.assertIn('uploadingCount', app)
        self.assertIn('attachment-uploading', app)
        self.assertIn('.upload-progress', css)

    def test_example_config_uses_latency_strategy(self):
        import json
        config = json.loads((ROOT / 'config.example.json').read_text(encoding='utf-8'))
        self.assertEqual(config['chat']['model_strategy'], 'latency-best-free')
