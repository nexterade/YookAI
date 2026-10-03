import tempfile
import unittest
from pathlib import Path

from core.memory import MemoryStore


class MemoryStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = MemoryStore(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_default_memory_is_shared(self):
        self.store.upsert_session("s1", [{"role": "user", "content": "Saya suka kopi"}], "default", "project-a")
        self.store.upsert_session("s2", [{"role": "user", "content": "Bahas kopi lagi"}], "default", "project-b")
        result = self.store.search("kopi", "default", "project-b")
        self.assertEqual({r["session_id"] for r in result}, {"s1", "s2"})

    def test_project_only_isolated(self):
        self.store.upsert_session("s1", [{"role": "user", "content": "rahasia project alpha"}], "project-only", "alpha")
        self.store.upsert_session("s2", [{"role": "user", "content": "project beta"}], "project-only", "beta")
        self.assertEqual([r["session_id"] for r in self.store.search("rahasia", "project-only", "beta")], [])
        self.assertEqual([r["session_id"] for r in self.store.search("rahasia", "project-only", "alpha")], ["s1"])

    def test_context_excludes_current_session(self):
        self.store.upsert_session("s1", [{"role": "user", "content": "current context"}], "default")
        self.store.upsert_session("s2", [{"role": "assistant", "content": "older context"}], "default")
        context = self.store.build_context("context", "default", "default", "s1")
        self.assertIn("older context", context)
        self.assertNotIn("current context", context)


if __name__ == "__main__":
    unittest.main()
