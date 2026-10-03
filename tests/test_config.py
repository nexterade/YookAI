import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import config, paths

DEFAULT_CONFIG={"provider":{"default":"openrouter","openrouter":{"api_key":"","base_url":"https://openrouter.ai/api/v1"}},"chat":{"default_model":"deepseek/deepseek-r1","stream":True,"show_reasoning":True,"auto_title":True},"ui":{"theme":"dark","sidebar_default":"open"},"server":{"host":"127.0.0.1","port":8000}}

class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        base=Path(self.temp.name)
        self.config_dir=base/"config"
        self.settings_file=self.config_dir/"settings.json"
        self.providers_file=self.config_dir/"providers.json"
        self.patch_paths=patch.multiple(paths, ROOT=base, CONFIG_DIR=self.config_dir, SESSIONS_DIR=base/"sessions", PROMPTS_DIR=base/"prompts", CACHE_DIR=base/"cache", SETTINGS_FILE=self.settings_file, PROVIDERS_FILE=self.providers_file)
        self.patch_paths.start()
        self.template=Path(config.__file__).resolve().parent.parent/"config.example.json"

    def tearDown(self):
        self.patch_paths.stop()
        self.temp.cleanup()

    def test_validate_memory_modes(self):
        config.validate_config(DEFAULT_CONFIG)
        bad = json.loads(json.dumps(DEFAULT_CONFIG))
        bad["memory"] = {"mode": "invalid", "project_id": "default"}
        with self.assertRaises(ValueError):
            config.validate_config(bad)
        good = json.loads(json.dumps(DEFAULT_CONFIG))
        good["memory"] = {"mode": "project-only", "project_id": "alpha"}
        self.assertEqual(config.validate_config(good)["memory"]["mode"], "project-only")

    def test_validate_config_rejects_invalid_port(self):
        bad = json.loads(json.dumps(DEFAULT_CONFIG))
        bad["server"]["port"] = 70000
        with self.assertRaises(ValueError):
            config.validate_config(bad)

    def test_validate_config_rejects_empty_host(self):
        bad = json.loads(json.dumps(DEFAULT_CONFIG))
        bad["server"]["host"] = ""
        with self.assertRaises(ValueError):
            config.validate_config(bad)

    def test_load_config_with_default_config(self):
        paths.ensure_layout()
        self.settings_file.write_text(json.dumps(DEFAULT_CONFIG), encoding="utf-8")
        loaded=config.load_config()
        self.assertEqual(loaded["provider"]["default"], "openrouter")
        self.assertEqual(loaded["chat"]["default_model"], "deepseek/deepseek-r1")

    def test_save_config_writes_file(self):
        saved=config.save_config(DEFAULT_CONFIG)
        self.assertEqual(saved, self.settings_file)
        loaded=json.loads(self.settings_file.read_text(encoding="utf-8"))
        self.assertEqual(loaded, DEFAULT_CONFIG)

    def test_ensure_config_creates_missing_file(self):
        self.assertFalse(self.settings_file.exists())
        created=config.ensure_config()
        self.assertEqual(created, self.settings_file)
        self.assertEqual(json.loads(created.read_text(encoding="utf-8")), json.loads(self.template.read_text(encoding="utf-8")))

if __name__ == "__main__":
    unittest.main()
