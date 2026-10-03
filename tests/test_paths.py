import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from core import paths


class PathTests(unittest.TestCase):
    def test_runtime_roots_are_absolute(self):
        for value in (paths.ROOT, paths.CONFIG_DIR, paths.SESSIONS_DIR, paths.PROMPTS_DIR, paths.CACHE_DIR):
            self.assertTrue(value.is_absolute())

    def test_child_directories_are_under_root(self):
        for value in (paths.CONFIG_DIR, paths.SESSIONS_DIR, paths.PROMPTS_DIR, paths.CACHE_DIR):
            self.assertTrue(paths.ROOT in value.parents)

    def test_project_root_is_repo_root(self):
        self.assertTrue((paths.get_project_root() / "server.py").exists())

    def test_ensure_layout_with_monkeypatched_paths(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / ".yookai"
            old = (paths.ROOT, paths.CONFIG_DIR, paths.SESSIONS_DIR, paths.PROMPTS_DIR, paths.CACHE_DIR)
            try:
                paths.ROOT = root
                paths.CONFIG_DIR = root / "config"
                paths.SESSIONS_DIR = root / "sessions"
                paths.PROMPTS_DIR = root / "prompts"
                paths.CACHE_DIR = root / "cache"
                self.assertEqual(paths.ensure_layout(), root)
                self.assertTrue((root / "config").is_dir())
                self.assertTrue((root / "sessions").is_dir())
                self.assertTrue((root / "prompts").is_dir())
                self.assertTrue((root / "cache").is_dir())
            finally:
                paths.ROOT, paths.CONFIG_DIR, paths.SESSIONS_DIR, paths.PROMPTS_DIR, paths.CACHE_DIR = old

    def test_source_does_not_use_getcwd(self):
        source = paths.get_project_root()
        offenders = []
        for file in source.rglob("*.py"):
            if ".venv" in file.parts:
                continue
            if file != Path(__file__) and "os.getcwd(" in file.read_text(encoding="utf-8"):
                offenders.append(str(file))
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
